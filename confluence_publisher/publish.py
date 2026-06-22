#!/usr/bin/env python3
"""Confluence HTML/Markdown Publisher — publish pages via REST API."""

import os
import sys
import re
import io
import json
import hashlib
import mimetypes
import ssl
import urllib.request
import base64
import html as html_module
import markdown as markdown_lib
import requests
from pathlib import Path
from dotenv import load_dotenv

# Windows 터미널 인코딩 강제 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# 모듈 수준 globals — main() 에서 _init() 호출 후 설정됨
CONFLUENCE_URL: str = ""
USERNAME: str = ""
PASSWORD: str = ""
DEFAULT_SPACE: str = ""
DEFAULT_PARENT_ID: str = ""
SESSION: requests.Session = None  # type: ignore
PAGES_DIR: Path = Path("pages")


def _find_dotenv() -> Path | None:
    for d in [Path.cwd(), *Path.cwd().parents]:
        p = d / ".env"
        if p.exists():
            return p
    return None


def _init():
    """환경변수 로드 및 전역 설정 초기화 (main() 진입 시 호출)"""
    global CONFLUENCE_URL, USERNAME, PASSWORD, DEFAULT_SPACE, DEFAULT_PARENT_ID, SESSION, PAGES_DIR
    dotenv_path = _find_dotenv()
    if dotenv_path:
        load_dotenv(dotenv_path)
    else:
        print(f"[WARN] 未找到 .env 文件（从 {Path.cwd()} 向上搜索）。请在项目目录创建 .env。")
    try:
        CONFLUENCE_URL    = os.environ["CONFLUENCE_URL"].rstrip("/")
        USERNAME          = os.environ["CONFLUENCE_USERNAME"]
        PASSWORD          = os.environ["CONFLUENCE_PASSWORD"]
    except KeyError as e:
        raise KeyError(f"{e} — 请在项目目录创建 .env 文件，参考 .env.example") from None
    DEFAULT_SPACE     = os.environ.get("DEFAULT_SPACE", "")
    DEFAULT_PARENT_ID = os.environ.get("DEFAULT_PARENT_ID", "")
    SESSION = requests.Session()
    SESSION.auth = (USERNAME, PASSWORD)
    SESSION.headers.update({"Content-Type": "application/json", "Accept": "application/json"})
    PAGES_DIR = Path.cwd() / "pages"

def extract_body(raw: str) -> str:
    """<body> 내용만 추출. <body> 태그 없으면 전체 반환."""
    m = re.search(r'<body[^>]*>(.*?)</body>', raw, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else raw.strip()


def extract_title(raw: str, fallback: str) -> str:
    """<title> → 첫 번째 <h1> → 파일명 순으로 제목 추출."""
    m = re.search(r'<title[^>]*>(.*?)</title>', raw, re.DOTALL | re.IGNORECASE)
    if m:
        return html_module.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip()
    m = re.search(r'<h1[^>]*>(.*?)</h1>', raw, re.DOTALL | re.IGNORECASE)
    if m:
        return re.sub(r'<[^>]+>', '', m.group(1)).strip()
    return fallback


_XML_ENTITIES = {'amp', 'lt', 'gt', 'quot', 'apos'}

def fix_html_entities(text: str) -> str:
    """HTML 명명 엔티티(&mdash; &nbsp; 등)를 유니코드 문자로 변환. XML 기본 5개는 유지."""
    def replace(m):
        name = m.group(1)
        if name in _XML_ENTITIES:
            return m.group(0)
        return html_module.unescape(m.group(0))
    return re.sub(r'&([a-zA-Z][a-zA-Z0-9]*);', replace, text)


def html_to_storage(body: str) -> str:
    """HTML → Confluence storage format (XML 호환 변환)"""
    # 1. <style>, <script> 제거 (Confluence 미지원)
    body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL | re.IGNORECASE)
    body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL | re.IGNORECASE)

    # 2. pre/code → Confluence code macro
    body = re.sub(
        r'<pre><code(?:\s+class="[^"]*?language-(\w+)[^"]*?")?>(.*?)</code></pre>',
        lambda m: (
            '<ac:structured-macro ac:name="code">'
            + (f'<ac:parameter ac:name="language">{m.group(1)}</ac:parameter>' if m.group(1) else "")
            + f'<ac:plain-text-body><![CDATA[{html_module.unescape(m.group(2))}]]></ac:plain-text-body>'
            + '</ac:structured-macro>'
        ),
        body,
        flags=re.DOTALL,
    )

    # 3. void 태그 → self-closing (Confluence storage format은 XML)
    body = re.sub(
        r'<(br|hr|input|meta|link)(\s[^>]*)?\s*/?>',
        lambda m: f'<{m.group(1)}{(m.group(2) or "").rstrip(" /")}/>',
        body,
        flags=re.IGNORECASE,
    )

    # 4. HTML 명명 엔티티 → 유니코드 변환 (&mdash; &nbsp; 등)
    body = fix_html_entities(body)
    # 4b. 남은 bare & (예: "A & B") → &amp;
    body = re.sub(r'&(?!(amp|lt|gt|quot|apos);)', '&amp;', body)

    # 5. <blockquote> → Confluence info panel
    body = re.sub(
        r'<blockquote>(.*?)</blockquote>',
        lambda m: (
            '<ac:structured-macro ac:name="info">'
            '<ac:rich-text-body>' + m.group(1).strip() + '</ac:rich-text-body>'
            '</ac:structured-macro>'
        ),
        body,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 6. Confluence 6.x + MySQL utf8 — 4바이트 유니코드(이모지) 제거
    body = re.sub(r'[\U00010000-\U0010FFFF]', '', body)

    return body


def get_page_by_title(space: str, title: str):
    url = f"{CONFLUENCE_URL}/rest/api/content"
    params = {"type": "page", "spaceKey": space, "title": title, "expand": "version"}
    r = SESSION.get(url, params=params)
    r.raise_for_status()
    results = r.json().get("results", [])
    return results[0] if results else None


def create_page(space: str, title: str, body: str, parent_id: str = None) -> dict:
    payload = {
        "type": "page",
        "title": title,
        "space": {"key": space},
        "body": {"storage": {"value": body, "representation": "storage"}},
    }
    if parent_id:
        payload["ancestors"] = [{"id": str(parent_id)}]
    r = SESSION.post(f"{CONFLUENCE_URL}/rest/api/content", data=json.dumps(payload))
    r.raise_for_status()
    return r.json()


def update_page(page_id: str, title: str, body: str, current_version: int) -> dict:
    payload = {
        "type": "page",
        "title": title,
        "version": {"number": current_version + 1},
        "body": {"storage": {"value": body, "representation": "storage"}},
    }
    r = SESSION.put(f"{CONFLUENCE_URL}/rest/api/content/{page_id}", data=json.dumps(payload))
    r.raise_for_status()
    return r.json()


def delete_page(page_id: str):
    r = SESSION.delete(f"{CONFLUENCE_URL}/rest/api/content/{page_id}")
    r.raise_for_status()


def get_existing_attachments(page_id: str) -> dict:
    url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}/child/attachment"
    r = SESSION.get(url, params={"limit": 200})
    r.raise_for_status()
    return {a["title"]: a["id"] for a in r.json().get("results", [])}


def upload_attachment(page_id: str, filename: str, data: bytes, existing: dict) -> str:
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    upload_headers = {"X-Atlassian-Token": "no-check", "Content-Type": None}
    files = {"file": (filename, io.BytesIO(data), content_type)}
    if filename in existing:
        url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}/child/attachment/{existing[filename]}/data"
    else:
        url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}/child/attachment"
    r = SESSION.post(url, files=files, headers=upload_headers)
    r.raise_for_status()
    result = r.json()
    results_list = result.get("results", [result] if "id" in result else [])
    if results_list:
        existing[filename] = results_list[0]["id"]
    return filename


def process_images(body: str, html_path: Path, page_id: str) -> str:
    """<img> 태그를 첨부파일로 업로드하고 ac:image 매크로로 교체"""
    existing = get_existing_attachments(page_id)

    def replace_img(m):
        img_tag = m.group(0)
        src_m = re.search(r'src=["\']([^"\']+)["\']', img_tag)
        alt_m = re.search(r'alt=["\']([^"\']*)["\']', img_tag)
        if not src_m:
            return '<br/>'
        src = html_module.unescape(src_m.group(1))
        alt = alt_m.group(1) if alt_m else ""
        try:
            if src.startswith("data:"):
                # base64 내장 이미지: data:image/png;base64,....
                m2 = re.match(r'data:([^;]+);base64,(.+)', src, re.DOTALL)
                if not m2:
                    return '<br/>'
                mime = m2.group(1).strip()
                data = base64.b64decode(m2.group(2).strip())
                ext = mime.split('/')[-1].split('+')[0].lower()
                if ext == 'jpeg':
                    ext = 'jpg'
                filename = hashlib.md5(data[:512]).hexdigest()[:12] + "." + ext
            elif src.startswith(("http://", "https://")):
                req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
                    data = resp.read()
                ext = src.split("?")[0].rsplit(".", 1)[-1][:5].lower()
                if ext not in ("png", "jpg", "jpeg", "gif", "svg", "webp"):
                    ext = "png"
                filename = hashlib.md5(src.encode()).hexdigest()[:12] + "." + ext
            else:
                src_clean = src.lstrip("./\\")
                img_path = (html_path.parent / src_clean).resolve()
                if not img_path.exists():
                    print(f"  [WARN] 이미지 없음: {img_path}")
                    return '<br/>'
                data = img_path.read_bytes()
                filename = img_path.name

            upload_attachment(page_id, filename, data, existing)
            ac = "<ac:image>"
            if alt:
                ac += f'<ac:parameter ac:name="alt">{html_module.escape(alt)}</ac:parameter>'
            ac += f'<ri:attachment ri:filename="{filename}"/></ac:image>'
            src_label = (src[:30] + "...(base64)") if src.startswith("data:") else src
            print(f"  [IMG] {src_label} → {filename}")
            return ac
        except Exception as e:
            print(f"  [WARN] 이미지 처리 실패: {src}: {e}")
            return '<br/>'

    return re.sub(r'<img\s[^>]*/?>', replace_img, body, flags=re.IGNORECASE)


def validate_xml(body: str) -> None:
    import xml.etree.ElementTree as ET
    wrapped = (
        '<root xmlns:ac="http://www.atlassian.com/schema/confluence/4/ac/"'
        ' xmlns:ri="http://www.atlassian.com/schema/confluence/4/ri/">'
        + body + '</root>'
    )
    try:
        ET.fromstring(wrapped.encode("utf-8"))
    except ET.ParseError as e:
        lines = wrapped.splitlines()
        row, col = e.position if hasattr(e, "position") else (0, 0)
        print(f"  [XML ERROR] {e}")
        if 0 < row <= len(lines):
            print(f"  [XML ERROR] 행 {row}: {lines[row - 1][max(0, col - 60):col + 60]!r}")
        Path("debug_storage.xml").write_text(wrapped, encoding="utf-8")
        print("  [XML ERROR] 完整内容已保存到 debug_storage.xml")
        raise


def md_to_html(md_path: Path) -> str:
    """마크다운 파일을 HTML로 변환 (전체 문서 형식)"""
    text = md_path.read_text(encoding="utf-8")
    body = markdown_lib.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    title_m = re.search(r'<h1[^>]*>(.*?)</h1>', body, re.IGNORECASE)
    title_tag = f"<title>{re.sub(r'<[^>]+>','',title_m.group(1))}</title>" if title_m else f"<title>{md_path.stem}</title>"
    return f"<html><head>{title_tag}</head><body>{body}</body></html>"


def publish_file(html_path: Path):
    suffix = html_path.suffix.lower()
    space     = DEFAULT_SPACE
    parent_id = DEFAULT_PARENT_ID

    if not space:
        print(f"[SKIP] {html_path.name}: .env에 DEFAULT_SPACE 설정 필요")
        return

    if suffix == ".md":
        raw = md_to_html(html_path)
        title = extract_title(raw, html_path.stem)
        body = extract_body(raw)
        body = html_to_storage(body)
    else:
        raw = html_path.read_text(encoding="utf-8")
        title = extract_title(raw, html_path.stem)
        body = extract_body(raw)
        body = html_to_storage(body)

    existing_page = get_page_by_title(space, title)

    if existing_page:
        page_id = existing_page["id"]
        version = existing_page["version"]["number"]
        body = process_images(body, html_path, page_id)
        validate_xml(body)
        update_page(page_id, title, body, version)
        page_url = f"{CONFLUENCE_URL}/pages/viewpage.action?pageId={page_id}"
        print(f"[UPDATE] {title}  →  {page_url}")
    else:
        result = create_page(space, title, "<p>...</p>", parent_id)
        page_id = result["id"]
        try:
            body = process_images(body, html_path, page_id)
            validate_xml(body)
            update_page(page_id, title, body, 1)
        except Exception:
            delete_page(page_id)
            raise
        page_url = f"{CONFLUENCE_URL}/pages/viewpage.action?pageId={page_id}"
        print(f"[CREATE] {title}  →  {page_url}")


def main():
    _init()
    targets = sys.argv[1:]
    if targets:
        files = [Path(t) for t in targets]
    else:
        files = sorted(PAGES_DIR.glob("*.html"))

    if not files:
        files = sorted(PAGES_DIR.glob("*.md"))
    if not files:
        print("발행할 파일이 없습니다. pages/ 폴더에 .html 또는 .md 파일을 추가하세요.")
        return

    for f in files:
        try:
            publish_file(f)
        except requests.HTTPError as e:
            body = e.response.text[:500] if e.response is not None else ""
            print(f"[ERROR] {f.name}: {e}\n  {body}")
        except Exception as e:
            print(f"[ERROR] {f.name}: {e}")


if __name__ == "__main__":
    main()
