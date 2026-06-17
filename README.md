# Confluence 自动发布工具

将 `.html` 或 `.md` 文件自动发布到公司 Confluence wiki。

---

## 环境要求

- Python 3.8+
- 安装依赖：`pip install -r requirements.txt`

---

## 配置

编辑 `.env` 文件：

```env
CONFLUENCE_URL=https://konawiki.konai.com/
CONFLUENCE_USERNAME=mllee
CONFLUENCE_PASSWORD=你的密码
DEFAULT_SPACE=~mllee
DEFAULT_PARENT_ID=428695901
```

- `DEFAULT_SPACE` — 发布到哪个空间（个人空间用 `~用户名`）
- `DEFAULT_PARENT_ID` — 父页面 ID（新页面创建在这个页面下）

---

## 使用方法

### 发布单个文件

```bash
python publish.py "pages/报告.md"
python publish.py "pages/报告.html"
```

### 发布 pages/ 目录下所有文件

```bash
python publish.py
```

---

## 文件结构

```
confluence-publisher/
  pages/
    images/          ← 本地图片放这里
      图片1.png
      图片2.png
    报告.md           ← 写文档的地方
    报告.html         ← 或者直接放 HTML
  publish.py         ← 发布工具（不用修改）
  .env               ← 账号配置
  requirements.txt
```

---

## 写文档的方式

### 方式一：直接写 Markdown（推荐）

新建 `pages/새문서.md`，用标准 Markdown 语法写：

```markdown
# 文档标题

## 章节

普通段落文字。

| 列1 | 列2 | 列3 |
|-----|-----|-----|
| A   | B   | C   |

> 这里写注意事项，发布后会变成蓝色提示框。

![图片说明](images/图片文件名.png)

​```python
def hello():
    print("代码块")
​```
```

### 方式二：AI 生成 HTML 后发布

1. 让 AI（Claude 等）生成报告 HTML
2. 将 HTML 文件放到 `pages/` 目录
3. 运行发布命令

---

## 图片处理方式

工具自动处理三种图片，无需手动操作：

| 类型 | 写法 | 说明 |
|------|------|------|
| 本地文件 | `![说明](images/图片.png)` | 放在 `pages/images/` 目录 |
| 外部 URL | `![说明](https://example.com/图.png)` | 自动下载并上传 |
| base64 内嵌 | HTML 里的 `data:image/png;base64,...` | 自动提取并上传 |

三种方式发布时都会自动上传为 Confluence 附件。

---

## 逻辑说明

- **页面已存在** → 自动更新（根据标题匹配）
- **页面不存在** → 自动创建（在 `DEFAULT_PARENT_ID` 下）
- **发布失败** → 自动删除刚创建的空页面（不留垃圾页）
- **标题来源** → `<title>` 标签 → `<h1>` 标签 → 文件名（优先级顺序）

---

## 웹페이지 크롤링

MD 키워드 기반으로 웹페이지에서 관련 내용을 추출합니다.

**1단계 — `crawl_sources.txt` 편집:**
```
md: pages/내문서.md

https://참고할-사이트.com/page1
https://다른사이트.com/docs
```

**2단계 — 실행:**
```bash
python crawl.py               # crawl_sources.txt 자동 사용
python crawl.py --save-images # 이미지도 pages/images/ 에 저장
```

- 회사 내부 Confluence URL → `.env` 인증 정보로 자동 로그인
- 외부 URL → 인증 없이 접근

---

## 注意事项

- Confluence 6.x 不支持 emoji 表情符号，会自动过滤
- 公司内网 SSL 证书验证已关闭（适配内网环境）
- 文件名含空格时加引号：`python publish.py "pages/파일 이름.md"`
