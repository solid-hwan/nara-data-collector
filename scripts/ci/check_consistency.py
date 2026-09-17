#!/usr/bin/env python3
"""저장소 정합성 검사 — CI 와 로컬에서 같이 쓴다.

여기서 잡는 것은 전부 **실제로 한 번씩 겪은** 드리프트다:
  1. 버전이 4곳에 흩어져 있어 server.json 만 0.2.0 으로 남았다.
  2. 마크다운 링크가 워킹트리에서만 통과했다 (gitignore된 파일이 로컬에
     있어서). 신규 클론 기준으로 11개가 깨져 있었다.
  3. MCP 서버 목록이 .mcp.json·server.json·Desktop 템플릿 3곳에서
     서로 달랐다 (Desktop 에 자체 서버가 빠져 있었다).

CI 는 clean checkout 이므로 2번이 자동으로 "신규 클론 기준"이 된다.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # Python 3.10 — requires-python 하한
    import tomli as tomllib  # type: ignore[no-redef]

FAIL: list[str] = []


def fail(msg: str) -> None:
    FAIL.append(msg)
    print(f"  ❌ {msg}")


def ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def check_versions() -> None:
    print("[1/3] 버전 일치")
    versions = {
        "pyproject.toml": tomllib.load(open("pyproject.toml", "rb"))["project"]["version"],
        "server.json": json.load(open("server.json", encoding="utf-8"))["version"],
    }
    init = open("src/koneps_mcp/__init__.py", encoding="utf-8").read()
    m = re.search(r'__version__\s*=\s*"([^"]+)"', init)
    versions["__init__.py"] = m.group(1) if m else "?"
    changelog = open("CHANGELOG.md", encoding="utf-8").read()
    m = re.search(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.M)
    versions["CHANGELOG.md"] = m.group(1) if m else "?"

    if len(set(versions.values())) == 1:
        ok(f"4곳 모두 {next(iter(versions.values()))}")
    else:
        fail(f"버전 불일치: {versions}")


def check_markdown_links() -> None:
    print("[2/3] 마크다운 링크 (추적 파일 기준)")
    tracked = subprocess.run(["git", "ls-files", "*.md"],
                             capture_output=True, text=True).stdout.split()
    pattern = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    broken = []
    for path in tracked:
        base = os.path.dirname(path)
        for match in pattern.finditer(open(path, encoding="utf-8").read()):
            target = match.group(1).split("#")[0].strip()
            if not target or target.startswith(("http", "mailto:")):
                continue
            if not os.path.exists(os.path.normpath(os.path.join(base, target))):
                broken.append(f"{path} → {target}")
    if broken:
        for b in broken:
            fail(f"깨진 링크: {b}")
    else:
        ok(f"{len(tracked)}개 파일, 깨진 링크 없음")


def check_server_lists() -> None:
    print("[3/3] MCP 서버 목록 일치")
    mcp = set(json.load(open(".mcp.json", encoding="utf-8"))["mcpServers"])
    srv = {s["name"] for s in json.load(open("server.json", encoding="utf-8"))["servers"]}
    tpl = set(json.load(open("docs/claude-desktop-config.template.json",
                            encoding="utf-8"))["mcpServers"])
    if mcp == srv == tpl:
        ok(f"3곳 모두 {len(mcp)}개: {', '.join(sorted(mcp))}")
    else:
        fail(f".mcp.json={sorted(mcp)} server.json={sorted(srv)} template={sorted(tpl)}")


if __name__ == "__main__":
    check_versions()
    check_markdown_links()
    check_server_lists()
    print()
    if FAIL:
        print(f"실패 {len(FAIL)}건")
        sys.exit(1)
    print("정합성 검사 통과")
