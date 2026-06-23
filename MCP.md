# Confluence Publisher MCP — 工具参考文档

通过 MCP（Model Context Protocol）让 Claude Code 直接发布文档到 Confluence，无需手动输入命令。

---

## 目录

- [安装与注册](#安装与注册)
- [配置 .env](#配置-env)
- [工具一：publish](#工具一publish)
- [工具二：crawl](#工具二crawl)
- [项目根目录查找规则](#项目根目录查找规则)
- [错误说明](#错误说明)
- [注意事项](#注意事项)

---

## 安装与注册

**安装：**

```powershell
pip install git+https://github.com/bright6778/confluence-publisher.git
```

**注册 MCP（每台机器执行一次）：**

```powershell
claude mcp add confluence_publisher confluence-mcp
```

> **注意**：注册名必须用下划线 `confluence_publisher`，不能含连字符。连字符会导致工具名 `mcp__confluence-publisher__...` 无法被 Claude 解析。

或者，将配置写入项目的 `.claude/settings.json`（适合团队共享，随代码库分发）：

```json
{
  "mcpServers": {
    "confluence_publisher": {
      "command": "confluence-mcp"
    }
  }
}
```

---

## 配置 .env

在项目目录（或其任意父目录）创建 `.env` 文件：

```env
CONFLUENCE_URL=https://wiki.yourcompany.com/
CONFLUENCE_USERNAME=你的用户名
CONFLUENCE_PASSWORD=你的密码
DEFAULT_SPACE=~你的用户名
DEFAULT_PARENT_ID=123456
```

| 变量名 | 必填 | 说明 |
|--------|------|------|
| `CONFLUENCE_URL` | 是 | Confluence 站点根地址，末尾斜杠可选 |
| `CONFLUENCE_USERNAME` | 是 | 登录用户名 |
| `CONFLUENCE_PASSWORD` | 是 | 登录密码 |
| `DEFAULT_SPACE` | 是 | 发布目标 Space Key（个人空间格式：`~用户名`） |
| `DEFAULT_PARENT_ID` | 否 | 新页面的父页面 ID（留空则创建在 Space 根目录） |

MCP 启动时从**当前目录向上**自动查找 `.env`，无需手动指定路径。

> **.env 包含密码，务必加入 `.gitignore`，不要提交到 git。**

---

## 工具一：`publish`

### 功能

将 `.md` 或 `.html` 文件发布到 Confluence：

- 页面已存在（按标题匹配） → 自动更新内容
- 页面不存在 → 在 `DEFAULT_PARENT_ID` 下自动创建
- 发布失败 → 自动删除刚创建的空页面，不留垃圾页
- 图片全程自动处理（见下方图片处理规则）

### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file_path` | string | 是 | 文件名或路径，支持三种写法（见下方） |

**`file_path` 三种写法：**

| 写法 | 示例 | 说明 |
|------|------|------|
| 绝对路径 | `D:/Github/myproject/reports/报告.md` | 直接使用该路径 |
| 相对路径 | `reports/报告.md` | 相对于项目根目录（`.env` 所在目录） |
| 仅文件名 | `报告.md` | 自动在项目内递归搜索，找到第一个匹配文件 |

### 图片处理规则

发布时，所有 `<img>` 标签自动上传为 Confluence 附件并转换为图片宏：

| 图片类型 | Markdown 写法 | 处理方式 |
|----------|---------------|----------|
| 本地文件 | `![说明](./报告_images/图片.png)` | 从 `{文件名}_images/` 子目录读取后上传 |
| 外部 URL | `![说明](https://example.com/图.png)` | 自动下载后上传 |
| Base64 内嵌 | HTML 中的 `data:image/png;base64,...` | 自动提取后上传 |

本地图片目录规范（与 `.md` 文件同级）：

```
项目目录/
  reports/
    20260618_报告.md
    20260618_报告_images/   ← 图片放这里
      01_架构图.png
      02_流程图.png
```

### 标题来源优先级

发布时，页面标题按以下顺序提取：

1. HTML `<title>` 标签内容
2. 第一个 `<h1>` 标签内容
3. 文件名（去掉扩展名）

### 对话示例

```
帮我把 20260618_报告.md 发布到 Confluence
```

```
发布 reports/20260618_报告.md
```

### 返回值示例

```
[UPDATE] 2026年6月报告  →  https://wiki.example.com/pages/viewpage.action?pageId=123456
[CREATE] 2026年6月报告  →  https://wiki.example.com/pages/viewpage.action?pageId=789012
  [IMG] ./报告_images/架构图.png → 架构图.png
  [IMG] https://example.com/logo.png → a3f9b2c1d4e5.png
```

失败时返回 `[ERROR] ...` 开头的错误信息。

---

## 工具二：`crawl`

### 功能

抓取网页内容，按关键词相关度筛选段落后输出，辅助写文档。

- 自动过滤导航栏、页脚、广告等噪音内容
- 支持内网 Confluence 页面（自动使用 `.env` 里的账号认证）
- 可将网页图片下载保存到本地

### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `url` | string | 是 | — | 要抓取的网页地址 |
| `md_path` | string | 否 | `""` | `.md` 文件路径，用于提取关键词来过滤相关内容 |
| `save_images` | bool | 否 | `false` | 是否将网页图片下载保存到 `pages/images/` 目录 |
| `top_n` | int | 否 | `20` | 最多返回多少个内容段落 |

### 关键词过滤逻辑（提供 `md_path` 时生效）

从 `.md` 文件中自动提取关键词：
- `#` / `##` / `###` 标题里的词
- `**加粗**` 文本里的词（长度 ≥ 2 个字符）

然后对网页各段落按关键词命中数打分，只返回得分 ≥ 1 的段落，按相关度由高到低排序。

不提供 `md_path` 时，按页面原始顺序返回前 `top_n` 个段落。

### 内容提取逻辑

1. 去除 `<script>` / `<style>` / `<nav>` / `<footer>` / `<header>` / `<aside>` / `<iframe>` 等标签
2. 按 `h1~h4` 标题将页面拆分为段落
3. 每段摘要最多 300 字

### 对话示例

```
抓取 https://docs.example.com/api 的内容，参考关键词用 reports/架构设计.md
```

```
帮我抓取 https://wiki.example.com/某页面 并保存图片
```

### 返回值示例

```
[FETCH] https://docs.example.com/api
[PAGE] API 设计规范

[MD 关键词] 12个: 认证, 接口, 鉴权, Token...

============================================================
相关段落
============================================================

[1] 认证方式
    所有 API 请求需在 Header 中携带 Bearer Token...

[2] 接口限流
    每个 Token 每分钟最多请求 60 次...

============================================================
MD 文件可用内容（复制后使用）：
============================================================

### 认证方式

所有 API 请求需在 Header 中携带 Bearer Token...
```

---

## 项目根目录查找规则

MCP server 按以下优先级确定"项目根目录"（用于读取 `.env`、解析相对路径）：

| 优先级 | 条件 | 说明 |
|--------|------|------|
| 1 | 环境变量 `CONFLUENCE_PROJECT_DIR` | 在 MCP 配置中显式指定 |
| 2 | 从 CWD 向上查找 `.env` | 找到 `.env` 的第一个目录 |
| 3 | 当前工作目录（CWD） | 兜底 |

### 多项目并存时

同一个 Claude Code session 打开多个工作目录时，CWD 可能指向错误的项目。在 MCP 配置里加 `CONFLUENCE_PROJECT_DIR` 明确指定：

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

---

## 错误说明

| 错误信息 | 原因 | 解决方法 |
|---------|------|----------|
| `[ERROR] 환경변수 누락: 'CONFLUENCE_URL'` | `.env` 文件缺少必填变量 | 检查 `.env`，补全缺少的变量 |
| `[WARN] 未找到 .env 文件（从 ... 向上搜索）` | 当前目录和所有父目录均无 `.env` | 在项目目录创建 `.env` |
| `[WARN] 이미지 없음: ...` | 引用的本地图片文件不存在 | 确认图片放在 `{文件名}_images/` 目录内，路径拼写正确 |
| `[XML ERROR] ...` + 生成 `debug_storage.xml` | HTML 转 Confluence storage format 时 XML 解析失败 | 打开 `debug_storage.xml` 定位问题行，通常是特殊字符或未闭合标签 |
| `[SKIP] ...: .env에 DEFAULT_SPACE 설정 필요` | `.env` 缺少 `DEFAULT_SPACE` | 在 `.env` 中添加 `DEFAULT_SPACE` |

---

## 注意事项

- **Confluence 6.x 不支持 emoji**：发布时自动过滤所有 4 字节 Unicode 字符（emoji）
- **内网 SSL 证书**：已关闭 SSL 验证，适配公司内网自签名证书环境
- **MCP 名称**：注册时必须用下划线 `confluence_publisher`，含连字符的旧版注册需重新注册
- **并发安全**：单次对话内多次调用 `publish` 是安全的，每次调用独立初始化
