#!/usr/bin/env python3
"""MCP server for confluence-publisher — exposes publish and crawl as MCP tools."""

import os
import sys
import io
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("confluence-publisher")


def _project_root() -> Path:
    """Project root: CONFLUENCE_PROJECT_DIR env var > upward .env search > CWD."""
    env_dir = os.environ.get("CONFLUENCE_PROJECT_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    for directory in [Path.cwd(), *Path.cwd().parents]:
        if (directory / ".env").exists():
            return directory
    return Path.cwd()


def _capture(func, *args, **kwargs) -> str:
    """Call func with stdout captured; return all printed output as a string."""
    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    try:
        func(*args, **kwargs)
    finally:
        sys.stdout = old_stdout
    return buf.getvalue().strip()


@mcp.tool()
def publish(file_path: str) -> str:
    """Publish a Markdown or HTML file to Confluence.

    Args:
        file_path: Path to the .md or .html file to publish (relative or absolute).
    """
    try:
        root = _project_root()
        os.chdir(root)
        from confluence_publisher.publish import _init, publish_file
        _init()
        path = Path(file_path) if Path(file_path).is_absolute() else root / file_path
        return _capture(publish_file, path)
    except KeyError as e:
        return f"[ERROR] 环境变量缺失: {e}。请在项目目录创建 .env 文件。"
    except Exception as e:
        return f"[ERROR] {e}"


@mcp.tool()
def crawl(url: str, md_path: str = "", save_images: bool = False, top_n: int = 20) -> str:
    """Crawl a webpage and extract relevant content based on keywords.

    Args:
        url: Web page URL to crawl.
        md_path: Optional path to a .md file for keyword extraction (relative or absolute).
        save_images: If True, save images to pages/images/ in the project directory.
        top_n: Maximum number of content sections to return (default 20).
    """
    try:
        root = _project_root()
        os.chdir(root)
        from confluence_publisher.crawl import crawl as _crawl
        md = Path(md_path) if md_path and Path(md_path).is_absolute() else (root / md_path if md_path else None)
        return _capture(_crawl, url, md_path=md, save_images=save_images, top_n=top_n)
    except Exception as e:
        return f"[ERROR] {e}"


def main():
    root = _project_root()
    (root / "pages" / "images").mkdir(parents=True, exist_ok=True)
    mcp.run()


if __name__ == "__main__":
    main()
