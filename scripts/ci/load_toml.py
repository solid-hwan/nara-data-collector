#!/usr/bin/env python3
"""TOML 파싱 검증 — Python 3.10 호환.

`tomllib` 은 3.11 부터 표준 라이브러리다. pyproject.toml 의
requires-python 하한이 3.10 이므로 CI 도 3.10 에서 돌고, 거기서는
`tomli` 를 써야 한다. 실측: 3.10 CI 에서 ModuleNotFoundError 로 실패했다.
"""
from __future__ import annotations

import sys

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # Python 3.10
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        print("tomllib/tomli 없음 — `pip install tomli`", file=sys.stderr)
        raise SystemExit(1)

for path in sys.argv[1:] or ["pyproject.toml"]:
    with open(path, "rb") as fh:
        tomllib.load(fh)
    print(f"  {path} OK")
