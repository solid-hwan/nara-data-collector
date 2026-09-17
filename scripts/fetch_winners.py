#!/usr/bin/env python3
"""낙찰내역 전수 페이징 수집기 (search_successful_bids).

MCP 서버(data-go-mcp)를 JSON-RPC over stdio 로 직접 구동해 페이지를 끝까지 받아
data/raw/data-go-mcp/search_successful_bids/full/ 에 저장한다.

설계 의도:
- 응답이 페이지당 ~100KB라 메인 Claude 컨텍스트로 올리면 토큰 초과. 이 스크립트가
  파일로 직접 적재 → 후속 가공 스크립트(winner_match 등)가 파일을 읽음.
- 파일명/메타 규칙은 data/raw/README.md 준수.
  full/{업종}_w7d{start8}-{end4}_p{NN}_full_{ts}.json
- 각 파일 최상위에 _meta (source/tool/called_at/params/note).

사용법:
  python3 scripts/fetch_winners.py --biztype 5 --start 2026-06-10 --end 2026-06-16 \
      [--rows 100] [--max-pages 0(=전수)] [--sleep 0.4]

biztype: 1=물품, 5=용역 (3=공사 등)
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data/raw/data-go-mcp/search_successful_bids/full")
KST = timezone(timedelta(hours=9))
BIZ_NAME = {"1": "물품", "5": "용역", "3": "공사", "2": "외자"}


class MCP:
    """data-go-mcp 서버를 stdio JSON-RPC 로 구동하는 최소 클라이언트."""

    def __init__(self):
        self.proc = subprocess.Popen(
            ["bash", os.path.join(ROOT, "scripts/run-mcp.sh"), "data-go-mcp"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1,
        )
        self._id = 0
        self._handshake()

    def _send(self, obj):
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def _readmsg(self):
        """id 가 있는 응답 라인이 나올 때까지 읽는다 (알림/로그 라인 스킵)."""
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP 서버 stdout 종료 (연결 끊김)")
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue  # 비-JSON 로그 라인 무시
            if "id" in msg:
                return msg

    def _handshake(self):
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "fetch_winners", "version": "1.0"}}})
        self._readmsg()
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def call(self, name, arguments):
        self._id += 1
        self._send({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                    "params": {"name": name, "arguments": arguments}})
        msg = self._readmsg()
        if "error" in msg:
            raise RuntimeError(f"MCP error: {msg['error']}")
        # FastMCP 응답: result.content[0].text 에 JSON 문자열
        content = msg["result"]["content"]
        text = content[0]["text"]
        return json.loads(text)

    def call_retry(self, name, arguments, expect_items=True, tries=4, backoff=2.0):
        """data.go.kr 가 간헐적으로 빈/0 응답을 줄 때 재시도.

        expect_items=True 면 total_count==0 또는 items 빈 응답을 일시 오류로 보고 재시도.
        (실제 0건 페이지와 구분 불가하므로, 1페이지 total_count 판정에만 엄격 적용)
        """
        last = None
        for attempt in range(1, tries + 1):
            try:
                payload = self.call(name, arguments)
            except RuntimeError as e:
                last = e
                time.sleep(backoff * attempt)
                continue
            res = payload.get("result", payload)
            if expect_items and int(res.get("total_count", 0)) == 0:
                last = RuntimeError("total_count=0 (일시 오류 의심)")
                time.sleep(backoff * attempt)
                continue
            return payload
        raise RuntimeError(f"call_retry 실패 ({tries}회): {last}")

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--biztype", required=True, choices=["1", "2", "3", "5"])
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--rows", type=int, default=100)
    ap.add_argument("--max-pages", type=int, default=0, help="0=전수")
    ap.add_argument("--start-page", type=int, default=1,
                    help="이어받기 시작 페이지 (기본 1). 이미 받은 뒷부분만 보강할 때 사용")
    ap.add_argument("--sleep", type=float, default=0.4)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    biz = BIZ_NAME[args.biztype]
    start8 = args.start.replace("-", "")
    end4 = args.end.replace("-", "")[4:]  # MMDD
    ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")

    mcp = MCP()
    try:
        # 1페이지로 total_count 확인 (빈 응답 재시도)
        first = mcp.call_retry("search_successful_bids", {
            "business_type": args.biztype, "start_date": args.start,
            "end_date": args.end, "num_of_rows": args.rows, "page_no": 1},
            expect_items=True)
        res = first.get("result", first)
        total = int(res.get("total_count", 0))
        n_pages = (total + args.rows - 1) // args.rows if total else 1
        if args.max_pages > 0:
            n_pages = min(n_pages, args.max_pages)
        start_page = max(1, args.start_page)
        print(f"[fetch] {biz} {args.start}~{args.end}: total={total:,} → {n_pages} pages "
              f"(rows={args.rows}, start_page={start_page})", flush=True)

        for page in range(start_page, n_pages + 1):
            if page == 1:
                payload = first
            else:
                payload = mcp.call_retry("search_successful_bids", {
                    "business_type": args.biztype, "start_date": args.start,
                    "end_date": args.end, "num_of_rows": args.rows, "page_no": page},
                    expect_items=False)
            wrapped = {
                "_meta": {
                    "source": "data-go-mcp",
                    "tool": "search_successful_bids",
                    "called_at": datetime.now(KST).isoformat(),
                    "params": {"business_type": args.biztype, "start_date": args.start,
                               "end_date": args.end, "num_of_rows": args.rows, "page_no": page},
                    "note": f"전수 페이징 수집 fetch_winners.py ({biz}); page {page}/{n_pages}",
                },
                "result": payload.get("result", payload),
            }
            fn = f"{biz}_w7d{start8}-{end4}_p{page:02d}_full_{ts}.json"
            with open(os.path.join(OUT_DIR, fn), "w", encoding="utf-8") as f:
                json.dump(wrapped, f, ensure_ascii=False)
            items = wrapped["result"].get("items", [])
            print(f"  p{page:02d}/{n_pages}  items={len(items)}  → {fn}", flush=True)
            if page < n_pages:
                time.sleep(args.sleep)
        print(f"[fetch] 완료: {n_pages} 파일 저장 → {OUT_DIR}", flush=True)
    finally:
        mcp.close()


if __name__ == "__main__":
    main()
