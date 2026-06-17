# confluence-publisher → pip 包改造过程

## 目标
将 `publish.py` 和 `crawl.py` 两个独立脚本改造成可 pip 安装的 Python 包，
使其能在任意项目中通过以下方式使用：

```bash
pip install git+https://github.com/yourname/confluence-publisher
confluence-publish pages/report.md
confluence-crawl https://example.com --md pages/report.md
```

---

## 改造前结构

```
confluence-publisher/
├── publish.py          ← 独立脚本
├── crawl.py            ← 独立脚本
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── pages_예시/
```

---

## 改造步骤

### Step 1 — 创建包目录结构
- 新建 `confluence_publisher/` 目录
- 新建 `confluence_publisher/__init__.py`

### Step 2 — 迁移源文件
- `publish.py` → `confluence_publisher/publish.py`
- `crawl.py` → `confluence_publisher/crawl.py`
- 原根目录脚本删除

### Step 3 — 创建 pyproject.toml
- 包名：`confluence-publisher`
- CLI 命令：`confluence-publish`、`confluence-crawl`
- 依赖从 `requirements.txt` 迁移

---

## 改造后结构

```
confluence-publisher/
├── confluence_publisher/
│   ├── __init__.py
│   ├── publish.py
│   └── crawl.py
├── pyproject.toml      ← 新增
├── .env.example
├── .gitignore
├── README.md
└── pages_예시/
```

---

## 实际遇到的问题与解决

### 问题 1 — 模块顶层读取环境变量导致 import 报错
**原因**：原 `publish.py` 在模块顶层直接 `os.environ["CONFLUENCE_URL"]`，
pip 安装后 `import` 时若无 `.env` 就会崩溃。

**解决**：新增 `_init()` 函数，把环境变量加载和 Session 创建全部移入其中，
在 `main()` 第一行调用 `_init()`。

### 问题 2 — PAGES_DIR 路径指向包安装目录
**原因**：`Path(__file__).parent / "pages"` 在安装后指向的是
`site-packages/confluence_publisher/pages`，而不是用户当前工作目录。

**解决**：改为 `Path.cwd() / "pages"`，始终指向命令执行时的工作目录。

### 问题 3 — pyproject.toml build-backend 名称错误
**原因**：写成了 `setuptools.backends.legacy:build`（不存在）。

**解决**：改为正确的 `setuptools.build_meta`。

---

## 使用方式（改造后）

任意项目只需：

```bash
# 安装（本地开发）
pip install -e /path/to/confluence-publisher

# 安装（从 GitHub）
pip install git+https://github.com/yourname/confluence-publisher

# 使用
confluence-publish pages/report.md
confluence-crawl crawl_sources.txt
```

`.env` 文件放在**当前工作目录**，工具会自动读取。

---

## 注意事项

- `.env` 查找逻辑：`python-dotenv` 默认从 CWD 向上查找，无需改代码
- `pages/` 目录路径：原代码用 `Path(__file__).parent / "pages"`，
  改包后需改为 `Path.cwd() / "pages"`，否则会找包安装目录下的 pages

