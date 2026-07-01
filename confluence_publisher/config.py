#!/usr/bin/env python3
"""Credential management: keyring → os.environ."""

import os

SERVICE = "confluence-publisher"
ALL_KEYS = [
    "CONFLUENCE_URL",
    "CONFLUENCE_USERNAME",
    "CONFLUENCE_PASSWORD",
    "DEFAULT_SPACE",
    "DEFAULT_PARENT_ID",
]


def get(key: str) -> str | None:
    """Read a credential: keyring first, then os.environ."""
    try:
        import keyring as _kr
        val = _kr.get_password(SERVICE, key)
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(key)


def set_credential(key: str, value: str) -> None:
    import keyring as _kr
    _kr.set_password(SERVICE, key, value)


def delete_credential(key: str) -> None:
    import keyring as _kr
    try:
        _kr.delete_password(SERVICE, key)
    except Exception:
        pass
