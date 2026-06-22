# Confluence 自动发布工具

将 `.md` 或 `.html` 文件自动发布到公司 Confluence wiki。  
支持两种使用方式：**MCP（让 Claude 直接操作）** 和 **命令行**。

---

## 安装（一次性）

```powershell
pip install git+https://github.com/bright6778/confluence-publisher.git
```

这一条命令会同时安装 CLI 工具和 MCP server：

| 安装内容 | 用途 |
|---|---|
| `confluence-publish` | 命令行直接运行 |
| `confluence-crawl` | 命令行直接运行 |
| `confluence-mcp` | MCP server 本体（Claude Code 自动启动） |

更新到最新版本（如遇 `.env` 不生效或命令报错，先升级）：

```powershell
pip install --upgrade git+https://github.com/bright6778/confluence-publisher.git
```

---

## 配置（每个项目）

在项目目录创建 `.env` 文件（参考 `.env.example`）：

```env
CONFLUENCE_URL=https://wiki.yourcompany.com/
CONFLUENCE_USERNAME=你的用户名
CONFLUENCE_PASSWORD=你的密码
DEFAULT_SPACE=~你的用户名
DEFAULT_PARENT_ID=父页面ID
```

工具启动时会从**当前目录向上**自动查找 `.env`，找不到时会打印提示：

```
[WARN] 未找到 .env 文件（从 D:\你的项目 向上搜索）。请在项目目录创建 .env。
```

> **注意**：`.env` 包含密码，务必加入 `.gitignore`，不要上传到 git。

---

## 方式一：MCP — 让 Claude 直接操作（推荐）

MCP（Model Context Protocol）让 Claude Code 直接调用发布工具，无需手动输入命令。

### 第一步 — 注册 MCP（一次性）

**CLI（推荐，全局生效）：**

```powershell
claude mcp add confluence_publisher confluence-mcp
```

> 已用旧名称（`confluence-publisher`，含连字符）注册过的需重新注册：
> ```powershell
> claude mcp remove confluence-publisher
> claude mcp add confluence_publisher confluence-mcp
> ```
> 连字符会导致工具名 `mcp__confluence-publisher__publish` 无法被解析，Claude 找不到工具。

**或手动创建 `.claude/settings.json`（仅限当前项目）：**

```json
{
  "mcpServers": {
    "confluence_publisher": {
      "command": "confluence-mcp"
    }
  }
}
```

### 第二步 — 使用

Claude Code 打开项目时会自动启动 MCP server，`pages/` 和 `pages/images/` 在此时自动创建。

**文档文件**：把 `.md` 或 `.html` 放进 `pages/`。

**本地图片**：把图片也放进 `pages/`，在 md 里直接用文件名引用：

```markdown
![图片说明](图片文件名.png)
```

> 图片文件名建议用英文或数字，避免中文或空格（如 `diagram-1.png`、`screenshot.png`）。

**`pages/images/`** 是 crawl 抓取时自动保存网页图片用的，不用手动放文件进去。

准备好后直接对 Claude 说：

```
帮我把 pages/报告.md 发布到 Confluence
```

```
抓取 https://example.com 的内容，参考关键词用 pages/报告.md
```

### 多项目并存时指定工作目录

同一个 Claude Code session 里同时打开多个项目时，MCP server 可能用错目录。  
在 MCP 配置中加 `CONFLUENCE_PROJECT_DIR` 明确指定：

```json
{
  "mcpServers": {
    "confluence_publisher": {
      "command": "confluence-mcp",
      "env": {
        "CONFLUENCE_PROJECT_DIR": "D:/Github/你的项目目录"
      }
    }
  }
}
```

### MCP 可用工具

| 工具 | 参数 | 说明 |
|------|------|------|
| `publish` | `file_path` | 发布 .md 或 .html 文件到 Confluence |
| `crawl` | `url`、`md_path`（可选）、`save_images`（可选）、`top_n`（可选） | 抓取网页并提取相关内容 |

---

## 方式二：命令行

### 文件结构

手动创建 `pages/` 目录，把文件放进去：

```
你的项目/
  pages/
    报告.md        ← 写文档的地方
    报告.html      ← 或直接放 HTML
    图片1.png      ← md 里引用的本地图片放这里
  .env             ← 账号配置（不要上传 git）
```

### 发布命令

```bash
# 发布单个文件
confluence-publish "pages/报告.md"
confluence-publish "pages/报告.html"

# 发布 pages/ 目录下所有文件
confluence-publish
```

### 网页内容抓取

根据关键词从网页提取相关内容，辅助写文档。

编辑 `crawl_sources.txt`：

```
md: pages/我的文档.md

https://参考网站.com/page1
https://其他网站.com/docs
```

运行：

```bash
confluence-crawl                # 使用 crawl_sources.txt
confluence-crawl --save-images  # 同时保存图片到 pages/images/
```

---

## 写 Markdown 文档

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

---

## 图片处理

工具自动处理三种图片，无需手动操作：

| 类型 | 写法 | 说明 |
|------|------|------|
| 本地文件 | `![说明](图片.png)` 或 `![说明](./图片.png)` | 放在 `pages/` 目录，两种写法都支持 |
| 外部 URL | `![说明](https://example.com/图.png)` | 自动下载并上传 |
| base64 内嵌 | HTML 里的 `data:image/png;base64,...` | 自动提取并上传 |

---

## 发布逻辑

- **页面已存在** → 自动更新（根据标题匹配）
- **页面不存在** → 自动创建（在 `DEFAULT_PARENT_ID` 下）
- **发布失败** → 自动删除刚创建的空页面（不留垃圾页）
- **标题来源** → `<title>` 标签 → `<h1>` 标签 → 文件名（优先级顺序）

---

## 注意事项

- Confluence 6.x 不支持 emoji，会自动过滤
- 公司内网 SSL 证书验证已关闭（适配内网环境）
- 文件名含空格时加引号：`confluence-publish "pages/文件 名称.md"`
- `.env` 放在运行命令的目录或其任意父目录均可，工具会自动向上查找
- MCP 注册名必须用下划线：`confluence_publisher`（含连字符的旧名称会导致工具无法调用）
