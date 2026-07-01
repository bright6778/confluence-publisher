#!/usr/bin/env python3
"""Interactive setup: store Confluence credentials in the OS keychain."""

import getpass
import sys
from confluence_publisher.config import SERVICE, ALL_KEYS, get, set_credential, delete_credential


def main():
    args = sys.argv[1:]

    if args and args[0] == "delete":
        for key in ALL_KEYS:
            delete_credential(key)
        print("已从 Keychain 删除所有 Confluence 凭据。")
        return

    if args and args[0] == "show":
        print(f"Keychain 服务名: {SERVICE}\n")
        for key in ALL_KEYS:
            val = get(key)
            if key == "CONFLUENCE_PASSWORD":
                display = "******" if val else "（未设置）"
            else:
                display = val or "（未设置）"
            print(f"  {key}: {display}")
        return

    print("=== Confluence Publisher 凭据设置 ===")
    print("凭据将存入系统 Keychain（Windows: Credential Manager，macOS: Keychain Access）\n")

    fields = [
        ("CONFLUENCE_URL",      "Confluence URL",            False),
        ("CONFLUENCE_USERNAME", "用户名",                    False),
        ("CONFLUENCE_PASSWORD", "密码",                      True),
        ("DEFAULT_SPACE",       "默认 Space（如 ~username）", False),
        ("DEFAULT_PARENT_ID",   "默认父页面 ID（可选）",      False),
    ]

    for key, label, secret in fields:
        current = get(key)
        if current and not secret:
            hint = f" [{current}]"
        elif current and secret:
            hint = " [已设置，直接回车跳过]"
        else:
            hint = ""
        prompt = f"{label}{hint}: "
        value = getpass.getpass(prompt) if secret else input(prompt)
        value = value.strip()
        if value:
            set_credential(key, value)
        elif not current:
            print(f"  （跳过 {key}）")

    print("\n✓ 凭据已保存。运行 `confluence-setup show` 验证。")


if __name__ == "__main__":
    main()
