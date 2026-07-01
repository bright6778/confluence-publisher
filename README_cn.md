# Confluence 自动发布工具

将 `.md` 或 `.html` 文件自动发布到公司 Confluence wiki。  
支持两种使用方式：**MCP（让 Claude 直接操作）** 和 **命令行**。

---

## 安装

```powershell
pip install git+https://github.com/bright6778/confluence-publisher.git
```

更新：

```powershell
pip install --force-reinstall --no-cache-dir git+https://github.com/bright6778/confluence-publisher.git
```

---

## 凭据配置（每台机器执行一次）

```powershell
confluence-setup
```

交互式输入后凭据存入系统 Keychain，不依赖任何项目文件。

```powershell
confluence-setup show    # 验证
confluence-setup delete  # 清除
```

| 项目 | 必填 | 说明 |
|------|------|------|
| Confluence URL | 是 | 站点根地址 |
| 用户名 | 是 | 登录用户名 |
| 密码 | 是 | 登录密码 |
| 默认 Space | 是 | Space Key，个人空间格式：`~用户名` |
| 默认父页面 ID | 否 | 留空则创建在 Space 根目录 |

---

## 方式一：MCP — 让 Claude 直接操作（推荐）

### 注册（每台机器执行一次）

```powershell
claude mcp add --scope user confluence_publisher confluence-mcp
```

> 注册名必须用下划线 `confluence_publisher`，含连字符会导致工具无法调用。

或写入项目 `.claude/settings.json`（团队共享）：

```json
{
  "mcpServers": {
    "confluence_publisher": {
      "command": "confluence-mcp"
    }
  }
}
```

### 使用

直接对 Claude 说：

```
帮我把 20260618_报告.md 发布到 Confluence
抓取 https://example.com 的内容，参考关键词用 reports/报告.md
```

工具会在项目内自动搜索文件，无需指定完整路径。

### 多项目并存时

同一 session 打开多个项目时，在 MCP 配置中加 `CONFLUENCE_PROJECT_DIR` 明确指定：

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

### 工具参考

**`publish`** — 发布 .md 或 .html 文件

| 参数 | 类型 | 说明 |
|------|------|------|
| `file_path` | string | 绝对路径 / 相对项目根目录的路径 / 仅文件名（自动搜索） |

返回示例：
```
[UPDATE] 报告标题  →  https://wiki.example.com/pages/viewpage.action?pageId=123456
[CREATE] 报告标题  →  https://wiki.example.com/pages/viewpage.action?pageId=789012
  [IMG] ./报告_images/架构图.png → 架构图.png
```

**`crawl`** — 抓取网页并提取相关内容

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `url` | string | — | 目标网页地址 |
| `md_path` | string | `""` | .md 文件路径，用于提取关键词过滤内容 |
| `save_images` | bool | false | 是否保存图片到 `pages/images/` |
| `top_n` | int | 20 | 最多返回段落数 |

---

## 方式二：命令行

```
你的项目/
  pages/
    报告.md
    报告_images/
      图片.png
```

```bash
confluence-publish "pages/报告.md"   # 发布单个文件
confluence-publish                    # 发布 pages/ 下所有文件
confluence-crawl                      # 按 crawl_sources.txt 抓取
confluence-crawl --save-images        # 同时保存图片
```

---

## 图片处理

| 类型 | 写法 | 处理方式 |
|------|------|----------|
| 本地文件 | `![说明](./报告_images/图片.png)` | 从 `{文件名}_images/` 子目录上传 |
| 外部 URL | `![说明](https://example.com/图.png)` | 自动下载后上传 |
| Base64 内嵌 | HTML 中的 `data:image/png;base64,...` | 自动提取后上传 |

---

## 发布逻辑

- 页面已存在（按标题匹配）→ 自动更新
- 页面不存在 → 在 `DEFAULT_PARENT_ID` 下创建
- 发布失败 → 自动删除刚创建的空页面
- 标题来源：`<title>` → `<h1>` → 文件名

---

## 错误说明

| 错误 | 原因 | 解决 |
|------|------|------|
| `[ERROR] 缺少凭据: ...` | Keychain 无凭据 | 运行 `confluence-setup` |
| `[WARN] 이미지 없음: ...` | 本地图片不存在 | 确认图片在 `{文件名}_images/` 目录内 |
| `[XML ERROR] ...` | HTML 转换失败 | 查看生成的 `debug_storage.xml` |
| `[SKIP] ...: DEFAULT_SPACE 설정 필요` | 缺少 DEFAULT_SPACE | 运行 `confluence-setup` 补充 |

---

## 注意事项

- Confluence 6.x 不支持 emoji，发布时自动过滤
- 内网 SSL 证书验证已关闭，适配公司自签名证书
- MCP 注册名必须用下划线 `confluence_publisher`
