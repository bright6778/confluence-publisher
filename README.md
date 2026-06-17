# Confluence 自动发布工具

将 `.md` 或 `.html` 文件自动发布到公司 Confluence wiki。

---

## 安装

```bash
pip install git+https://github.com/bright6778/confluence-publisher.git
```

安装一次后，在**任意项目目录**都能直接使用 `confluence-publish` 命令，无需每次复制脚本。

更新到最新版本：

```bash
pip install --upgrade git+https://github.com/bright6778/confluence-publisher.git
```

---

## 配置

在你的项目目录创建 `.env` 文件（参考 `.env.example`）：

```env
CONFLUENCE_URL=https://wiki.yourcompany.com/
CONFLUENCE_USERNAME=你的用户名
CONFLUENCE_PASSWORD=你的密码
DEFAULT_SPACE=~你的用户名
DEFAULT_PARENT_ID=父页面ID
```

- `DEFAULT_SPACE` — 发布到哪个空间（个人空间用 `~用户名`）
- `DEFAULT_PARENT_ID` — 父页面 ID（新页面创建在这个页面下）

> **重要**：`.env` 文件包含密码，务必加入 `.gitignore`，不要上传到 git。

---

## 文件结构

```
你的项目/
  pages/
    图片1.png
    图片2.png
    报告.md           ← 写文档的地方
    报告.html         ← 或者直接放 HTML
  .env               ← 账号配置（不要上传 git）
```

---

## 发布命令

```bash
# 发布单个文件
confluence-publish "pages/报告.md"
confluence-publish "pages/报告.html"

# 发布 pages/ 目录下所有文件
confluence-publish
```

---

## 写文档的方式

### 方式一：直接写 Markdown（推荐）

新建 `pages/报告.md`，用标准 Markdown 语法：

```markdown
# 文档标题

## 章节

普通段落文字。

| 列1 | 列2 | 列3 |
|-----|-----|-----|
| A   | B   | C   |

> 这里写注意事项，发布后会变成蓝色提示框。

![图片说明](图片文件名.png)

​```python
def hello():
    print("代码块")
​```
```

### 方式二：AI 生成 HTML 后发布

1. 让 AI（Claude 等）生成报告 HTML
2. 将 HTML 文件放到 `pages/` 目录
3. 运行 `confluence-publish`

---

## 图片处理

工具自动处理三种图片，无需手动操作：

| 类型 | 写法 | 说明 |
|------|------|------|
| 本地文件 | `![说明](图片.png)` | 放在 `pages/` 目录 |
| 外部 URL | `![说明](https://example.com/图.png)` | 自动下载并上传 |
| base64 内嵌 | HTML 里的 `data:image/png;base64,...` | 自动提取并上传 |

---

## 发布逻辑

- **页面已存在** → 自动更新（根据标题匹配）
- **页面不存在** → 自动创建（在 `DEFAULT_PARENT_ID` 下）
- **发布失败** → 自动删除刚创建的空页面（不留垃圾页）
- **标题来源** → `<title>` 标签 → `<h1>` 标签 → 文件名（优先级顺序）

---

## 网页内容抓取

根据关键词从网页中提取相关内容，辅助写文档。

**第一步 — 编辑 `crawl_sources.txt`：**

```
md: pages/我的文档.md

https://参考网站.com/page1
https://其他网站.com/docs
```

**第二步 — 运行：**

```bash
confluence-crawl                # 使用 crawl_sources.txt
confluence-crawl --save-images  # 同时保存图片到 pages/
```

---

## 注意事项

- Confluence 6.x 不支持 emoji，会自动过滤
- 公司内网 SSL 证书验证已关闭（适配内网环境）
- 文件名含空格时加引号：`confluence-publish "pages/文件 名称.md"`
