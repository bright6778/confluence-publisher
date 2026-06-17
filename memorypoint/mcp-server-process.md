# confluence-publisher → MCP Server 改造过程

## 目标
在 pip 包的基础上，新增 MCP（Model Context Protocol）Server，
使 Claude Code 能直接调用 `publish` 和 `crawl` 工具，无需手动输入命令。

---

## 什么是 MCP

MCP（Model Context Protocol）是 Anthropic 定义的标准协议，
允许 Claude Code 通过 stdio 连接到外部工具服务器，
像调用函数一样让 AI 执行操作。

---

## 改造前后结构对比

### 改造前
```
confluence_publisher/
├── __init__.py
├── publish.py
└── crawl.py
```

### 改造后
```
confluence_publisher/
├── __init__.py
├── publish.py
├── crawl.py
└── mcp_server.py    ← 新增
```

---

## 改造步骤

### Step 1 — 新增 `mcp_server.py`
- 使用 `mcp.server.fastmcp.FastMCP` 创建 MCP 服务器
- 用 `@mcp.tool()` 装饰器定义两个工具：
  - `publish(file_path)` — 调用现有的 `publish_file()`
  - `crawl(url, md_path, save_images, top_n)` — 调用现有的 `crawl()`
- 入口函数 `main()` 调用 `mcp.run()`（默认 stdio 传输）

### Step 2 — 更新 `pyproject.toml`
- 在 `dependencies` 中添加 `mcp>=1.0.0`
- 在 `[project.scripts]` 中添加 `confluence-mcp = "confluence_publisher.mcp_server:main"`

---

## 关键设计决策

### stdout 捕获
`publish_file()` 和 `crawl()` 原本通过 `print()` 输出结果。
MCP 的 stdio 传输使用 stdout 传递 JSON-RPC 协议消息，
如果工具函数直接 print，会污染协议流。

**解决方案**：用 `io.StringIO` 临时替换 `sys.stdout`，
捕获所有 print 输出，作为工具调用的返回值返回给 Claude。

```python
def _capture(func, *args, **kwargs) -> str:
    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    try:
        func(*args, **kwargs)
    finally:
        sys.stdout = old_stdout
    return buf.getvalue().strip()
```

### 延迟 `_init()` 调用
沿用 pip 版本的设计：`_init()` 在工具被调用时才执行，
而不是模块导入时执行，避免无 `.env` 时崩溃。

### CWD 路径
MCP 服务器的工作目录（CWD）是 Claude Code 的项目目录，
因此 `.env` 和 `pages/` 应放在 `.claude/settings.json` 所在的目录里。
这与 pip 版本的逻辑完全一致（`Path.cwd() / "pages"`）。

---

## 实际遇到的问题与解决

### 问题 1 — crawl.py 模块级 sys.stdout.reconfigure
`crawl.py` 第 18 行在模块顶层调用了 `sys.stdout.reconfigure(encoding="utf-8")`。
MCP 服务器启动时会导入该模块，此时对真实 stdout 重新配置，不影响 MCP 协议（UTF-8 兼容）。
工具调用时 stdout 已被替换为 StringIO，不再触发 reconfigure。

---

## 使用方式（配置后）

### 第一步 — 安装（同 pip 版本，无需重复安装）

如果已经安装了 pip 版本，直接升级即可：

```powershell
pip install --upgrade git+https://github.com/bright6778/confluence-publisher.git
```

### 第二步 — 配置 Claude Code

在你的项目目录（放 `.env` 和 `pages/` 的地方）创建 `.claude/settings.json`：

```json
{
  "mcpServers": {
    "confluence-publisher": {
      "command": "confluence-mcp"
    }
  }
}
```

### 第三步 — 直接对话

无需手动运行命令，直接在 Claude Code 中说：

- "帮我把 pages/报告.md 发布到 Confluence"
- "抓取 https://example.com 的内容，参考 pages/报告.md"

---

## 文件结构总览（pip + MCP 完整版）

```
confluence-publisher/           ← GitHub 仓库（pip install 源）
├── confluence_publisher/
│   ├── __init__.py
│   ├── publish.py
│   ├── crawl.py
│   └── mcp_server.py          ← MCP server 入口
├── pyproject.toml              ← 包含 confluence-mcp 入口点
├── README.md
├── .env.example
├── .gitignore
└── memorypoint/
    ├── pip-package-process.md
    └── mcp-server-process.md   ← 本文件

你的项目目录/                   ← 实际使用的工作目录
├── .claude/
│   └── settings.json          ← MCP 配置
├── pages/
│   └── 报告.md
└── .env                       ← 账号配置（不要上传 git）
```
