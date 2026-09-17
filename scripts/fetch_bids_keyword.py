#!/usr/bin/env python3
"""진행중 공고 + 사전규격 수집기 (nara-jangteo.get_bids_by_keyword).

여러 키워드를 days 윈도우로 조회해 data/raw/nara-jangteo/get_bids_by_keyword/ 에 저장.
응답은 마크다운 텍스트(get_bids_by_keyword 는 포맷된 string 반환)라 그대로 보존.

사용법:
  python3 scripts/fetch_bids_keyword.py --days 14 --keywords AI 인공지능 생성형 플랫폼 "시스템 구축" 데이터
"""
import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data/raw/nara-jangteo/get_bids_by_keyword")
KST = timezone(timedelta(hours=9))


class MCP:
    def __init__(self, target):
        self.proc = subprocess.Popen(
            ["bash", os.path.join(ROOT, "scripts/run-mcp.sh"), target],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1,
        )
        self._id = 0
        self._handshake()

    def _send(self, obj):
        self.proc.stdin.write(json.dumps(obj) + "\n"); self.proc.stdin.flush()

    def _readmsg(self):
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP stdout 종료")
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in msg:
                return msg

    def _handshake(self):
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "fetch_bids", "version": "1.0"}}})
        self._readmsg()
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def call_text(self, name, arguments, tries=4, backoff=2.0):
        last = None
        for attempt in range(1, tries + 1):
            self._id += 1
            self._send({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                        "params": {"name": name, "arguments": arguments}})
            msg = self._readmsg()
            if "error" in msg:
                last = msg["error"]; time.sleep(backoff * attempt); continue
            text = msg["result"]["content"][0]["text"]
            if not text or "Found 0" in text[:200] and "0 pre-spec" in text:
                last = "empty"; time.sleep(backoff * attempt); continue
            return text
        raise RuntimeError(f"call_text 실패: {last}")

    def close(self):
        try:
            self.proc.terminate(); self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def slug(kw):
    s = re.sub(r"\s+", "_", kw.strip())
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--keywords", nargs="+", required=True)
    ap.add_argument("--sleep", type=float, default=1.0)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    mcp = MCP("nara-jangteo")
    try:
        for kw in args.keywords:
            text = mcp.call_text("get_bids_by_keyword", {"keyword": kw, "days": args.days})
            wrapped = {
                "_meta": {
                    "source": "nara-jangteo",
                    "tool": "get_bids_by_keyword",
                    "called_at": datetime.now(KST).isoformat(),
                    "params": {"keyword": kw, "days": args.days},
                    "note": "fetch_bids_keyword.py 수집; result 는 포맷된 마크다운 텍스트",
                },
                "result": text,
            }
            fn = f"{slug(kw)}_d{args.days}_{ts}.json"
            with open(os.path.join(OUT_DIR, fn), "w", encoding="utf-8") as f:
                json.dump(wrapped, f, ensure_ascii=False)
            n_reg = len(re.findall(r"^## \d+\. ", text, re.M))
            print(f"  [{kw}] d{args.days}  공고블록≈{n_reg}  → {fn}", flush=True)
            time.sleep(args.sleep)
        print(f"[fetch_bids] 완료 → {OUT_DIR}", flush=True)
    finally:
        mcp.close()


if __name__ == "__main__":
    main()
