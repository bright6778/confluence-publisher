#!/usr/bin/env python3
"""
웹페이지 크롤러 — MD 파일 키워드 기반으로 관련 내용 추출
사용법:
  python crawl.py <URL> [--md pages/파일.md] [--save-images]
"""

import sys
import re
import ssl
import hashlib
import base64
import mimetypes
import urllib.request
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("pip install beautifulsoup4 를 먼저 실행하세요.")
    sys.exit(1)

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def fetch(url: str, username: str = None, password: str = None) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    if username and password:
        cred = base64.b64encode(f"{username}:{password}".encode()).decode()
        req.add_header("Authorization", f"Basic {cred}")
    with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def extract_md_keywords(md_path: Path) -> list[str]:
    """MD 파일에서 제목·굵은 글씨·중요 단어 추출"""
    text = md_path.read_text(encoding="utf-8")
    keywords = []
    # 제목 (#, ##, ###)
    for m in re.finditer(r'^#{1,3}\s+(.+)', text, re.MULTILINE):
        keywords += re.sub(r'[^\w가-힣ぁ-龯a-zA-Z0-9]', ' ', m.group(1)).split()
    # 굵은 글씨 (**text**)
    for m in re.finditer(r'\*\*(.+?)\*\*', text):
        keywords += re.sub(r'[^\w가-힣ぁ-龯a-zA-Z0-9]', ' ', m.group(1)).split()
    # 중복 제거, 2글자 이상만
    seen = set()
    result = []
    for k in keywords:
        k = k.strip()
        if len(k) >= 2 and k not in seen:
            seen.add(k)
            result.append(k)
    return result


def score_text(text: str, keywords: list[str]) -> int:
    """텍스트에 키워드가 몇 개 포함되는지 점수 계산"""
    text_lower = text.lower()
    return sum(1 for k in keywords if k.lower() in text_lower)


def clean_text(tag) -> str:
    return re.sub(r'\s+', ' ', tag.get_text(separator=' ')).strip()


def crawl(url: str, md_path: Path = None, save_images: bool = False,
          top_n: int = 20, min_score: int = 1):

    from confluence_publisher import config as _cfg
    conf_url = (_cfg.get("CONFLUENCE_URL") or "").rstrip("/")
    username = _cfg.get("CONFLUENCE_USERNAME") if conf_url and url.startswith(conf_url) else None
    password = _cfg.get("CONFLUENCE_PASSWORD") if conf_url and url.startswith(conf_url) else None

    print(f"\n[FETCH] {url}")
    html = fetch(url, username=username, password=password)
    soup = BeautifulSoup(html, "html.parser")

    # 불필요한 태그 제거
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "iframe", "noscript", "svg"]):
        tag.decompose()

    # 페이지 제목
    title = soup.title.get_text(strip=True) if soup.title else url
    print(f"[PAGE] {title}\n")

    keywords = []
    if md_path:
        keywords = extract_md_keywords(md_path)
        print(f"[MD 키워드] {len(keywords)}개: {', '.join(keywords[:15])}{'...' if len(keywords) > 15 else ''}\n")

    # ─── 텍스트 섹션 추출 ───
    results = []

    # h2/h3 제목 단위로 묶기
    sections = []
    current_title = title
    current_texts = []

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th"]):
        if tag.name in ("h1", "h2", "h3", "h4"):
            if current_texts:
                sections.append((current_title, " ".join(current_texts)))
            current_title = clean_text(tag)
            current_texts = []
        else:
            t = clean_text(tag)
            if len(t) > 20:
                current_texts.append(t)

    if current_texts:
        sections.append((current_title, " ".join(current_texts)))

    # 점수 계산 + 정렬
    if keywords:
        scored = [(score_text(title + " " + body, keywords), title, body)
                  for title, body in sections]
        scored.sort(key=lambda x: -x[0])
        top_sections = [(t, b) for s, t, b in scored if s >= min_score][:top_n]
    else:
        top_sections = sections[:top_n]

    print("=" * 60)
    print("관련 섹션")
    print("=" * 60)
    for i, (sec_title, body) in enumerate(top_sections, 1):
        # 본문 요약 (최대 300자)
        summary = body[:300] + ("..." if len(body) > 300 else "")
        print(f"\n[{i}] {sec_title}")
        print(f"    {summary}")

    # ─── 이미지 추출 ───
    imgs = soup.find_all("img")
    img_infos = []
    for img in imgs:
        src = img.get("src", "")
        alt = img.get("alt", "").strip()
        if not src or src.startswith("data:") or len(src) < 5:
            continue
        # 상대경로 → 절대경로
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(url)
            src = f"{parsed.scheme}://{parsed.netloc}{src}"
        elif not src.startswith("http"):
            base = url.rsplit("/", 1)[0]
            src = base + "/" + src
        img_infos.append((src, alt))

    if img_infos:
        print(f"\n{'=' * 60}")
        print(f"이미지 {len(img_infos)}개 발견")
        print("=" * 60)
        for i, (src, alt) in enumerate(img_infos, 1):
            print(f"  [{i}] {alt or '(no alt)'}  →  {src[:80]}")

    # ─── 이미지 저장 ───
    if save_images and img_infos:
        images_dir = Path("pages/images")
        images_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n[SAVE] pages/images/ 에 저장 중...")
        saved = 0
        for src, alt in img_infos:
            try:
                req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
                    data = resp.read()
                ext = src.split("?")[0].rsplit(".", 1)[-1][:5].lower()
                if ext not in ("png", "jpg", "jpeg", "gif", "svg", "webp"):
                    ext = "png"
                safe_alt = re.sub(r'[\\/:*?"<>|]', '_', alt)[:30] if alt else ""
                fname = f"web_{saved+1:02d}_{safe_alt}.{ext}" if safe_alt else f"web_{saved+1:02d}.{ext}"
                (images_dir / fname).write_bytes(data)
                print(f"  저장: {fname}  ({len(data)//1024}KB)")
                saved += 1
            except Exception as e:
                print(f"  [SKIP] {src[:60]}: {e}")
        print(f"총 {saved}장 저장 완료")

    # ─── 결과 반환 (MD 추가용 텍스트) ───
    print(f"\n{'=' * 60}")
    print("MD 파일에 추가할 내용 (복사해서 사용):")
    print("=" * 60)
    for sec_title, body in top_sections[:5]:
        print(f"\n### {sec_title}\n")
        print(body[:500])
        print()


def resolve_md(md_str: str) -> Path | None:
    p = Path(md_str.strip()).resolve()
    if p.exists():
        return p
    # Windows 인코딩 문제 대비 — pages/ 에서 파일명으로 재탐색
    name = Path(md_str.strip()).name
    match = next((c for c in Path("pages").glob("*.md") if c.name == name), None)
    if match:
        return match
    print(f"[WARN] MD 파일을 찾을 수 없음: {md_str}")
    return None


def read_sources_file(src_file: Path):
    """sources.txt 파싱 → (md_path, [url, ...]) 반환"""
    md_path = None
    urls = []
    for line in src_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("md:"):
            md_path = resolve_md(line[3:].strip())
        elif line.startswith("http://") or line.startswith("https://"):
            urls.append(line)
    return md_path, urls


def main():
    parser = argparse.ArgumentParser(description="웹페이지 크롤러")
    parser.add_argument("source", nargs="?",
                        help="crawl_sources.txt 파일 또는 URL (생략 시 crawl_sources.txt 자동 사용)")
    parser.add_argument("--md", help="키워드 추출용 MD 파일 경로", default=None)
    parser.add_argument("--save-images", action="store_true", help="이미지를 pages/images/ 에 저장")
    parser.add_argument("--top", type=int, default=20, help="최대 섹션 수 (기본 20)")
    args = parser.parse_args()

    # source 인자가 URL이면 직접 실행, 파일이면 파일에서 읽기
    source = args.source or "crawl_sources.txt"

    if source.startswith("http://") or source.startswith("https://"):
        urls = [source]
        md_path = resolve_md(args.md) if args.md else None
    else:
        src_file = Path(source)
        if not src_file.exists():
            print(f"파일이 없습니다: {src_file}")
            print("crawl_sources.txt 를 만들거나 URL을 직접 입력하세요.")
            sys.exit(1)
        md_path, urls = read_sources_file(src_file)
        if args.md:
            md_path = resolve_md(args.md)

    if not urls:
        print("크롤링할 URL이 없습니다. crawl_sources.txt 에 URL을 추가하세요.")
        sys.exit(1)

    for url in urls:
        crawl(url, md_path=md_path, save_images=args.save_images, top_n=args.top)
        if len(urls) > 1:
            print("\n" + "─" * 60 + "\n")


if __name__ == "__main__":
    main()
