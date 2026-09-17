#!/usr/bin/env python3
"""RFP 문의처 추출기 (nara-jangteo.analyze_bid_detail).

공고 리스트(JSON: [{bid_no, file_url, filename}, ...])를 받아 각 RFP 본문을
analyze_bid_detail 로 추출, data/raw/nara-jangteo/analyze_bid_detail/{bid_no}_{ts}.json 에
전체 텍스트를 보존하고, 동시에 "문의/문의처/담당자/연락처/TEL" 인접 라인을 휴리스틱으로
뽑아 contacts 요약(stdout JSON)을 만든다. 본문 전체를 메인 컨텍스트로 올리지 않기 위함.

사용법:
  python3 scripts/fetch_rfp_contacts.py --jobs jobs.json [--sleep 1.5]
  jobs.json = [{"bid_no":"R26BK...","file_url":"https://...","filename":"제안요청서.hwp"}, ...]
"""
import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data/raw/nara-jangteo/analyze_bid_detail")
KST = timezone(timedelta(hours=9))

# 문의처 신호 키워드 (사업담당/제출/문의 — 평가위원 제외)
SIGNAL = re.compile(r"문\s*의|담\s*당|연\s*락\s*처|제출처|TEL|전화|☎|☏|이메일|E-?mail|e-?mail|@")
# 평가위원/심사위원 라인은 제외
EXCLUDE = re.compile(r"평가위원|심사위원|평가위원회")
TEL = re.compile(r"(0\d{1,2}[-)\s]?\d{3,4}[-\s]?\d{4})")
EMAIL = re.compile(r"[\w.\-]+@[\w.\-]+\.\w+")


class MCP:
    def __init__(self, target):
        self.proc = subprocess.Popen(
            ["bash", os.path.join(ROOT, "scripts/run-mcp.sh"), target],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1)
        self._id = 0
        self._handshake()

    def _send(self, o):
        self.proc.stdin.write(json.dumps(o) + "\n"); self.proc.stdin.flush()

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
                               "clientInfo": {"name": "fetch_rfp", "version": "1.0"}}})
        self._readmsg()
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def call_text(self, name, arguments, tries=3, backoff=3.0):
        last = None
        for attempt in range(1, tries + 1):
            self._id += 1
            self._send({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                        "params": {"name": name, "arguments": arguments}})
            msg = self._readmsg()
            if "error" in msg:
                last = msg["error"]; time.sleep(backoff * attempt); continue
            return msg["result"]["content"][0]["text"]
        raise RuntimeError(f"call_text 실패: {last}")

    def close(self):
        try:
            self.proc.terminate(); self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def extract_contacts(text):
    """본문에서 문의처 후보 라인을 추출 (평가위원 제외)."""
    # 줄바꿈이 거의 없는 hwp 추출 텍스트 → 구분자 기준 분할
    chunks = re.split(r"[\n。]|(?<=[다음])\s|(?<=\d{4})\s{2,}", text)
    hits = []
    for ch in chunks:
        if SIGNAL.search(ch) and not EXCLUDE.search(ch):
            tels = TEL.findall(ch)
            emails = EMAIL.findall(ch)
            if tels or emails or "문의" in ch or "담당" in ch or "제출처" in ch:
                snippet = ch.strip()[:200]
                hits.append({"snippet": snippet, "tels": tels, "emails": emails})
    # 중복 제거
    seen = set(); uniq = []
    for h in hits:
        key = (tuple(h["tels"]), tuple(h["emails"]), h["snippet"][:60])
        if key in seen:
            continue
        seen.add(key); uniq.append(h)
    return uniq[:8]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--sleep", type=float, default=1.5)
    args = ap.parse_args()

    with open(args.jobs, encoding="utf-8") as f:
        jobs = json.load(f)
    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    mcp = MCP("nara-jangteo")
    summary = []
    try:
        for job in jobs:
            bid = job["bid_no"]
            try:
                text = mcp.call_text("analyze_bid_detail",
                                     {"file_url": job["file_url"], "filename": job["filename"]})
            except RuntimeError as e:
                summary.append({"bid_no": bid, "error": str(e)})
                print(f"  [{bid}] ERROR {e}", flush=True)
                continue
            wrapped = {
                "_meta": {
                    "source": "nara-jangteo", "tool": "analyze_bid_detail",
                    "called_at": datetime.now(KST).isoformat(),
                    "params": {"file_url": job["file_url"], "filename": job["filename"],
                               "bid_no": bid},
                    "note": "fetch_rfp_contacts.py 추출; result=RFP 전체 텍스트",
                },
                "result": text,
            }
            fn = f"{bid}_{ts}.json"
            with open(os.path.join(OUT_DIR, fn), "w", encoding="utf-8") as f:
                json.dump(wrapped, f, ensure_ascii=False)
            contacts = extract_contacts(text)
            summary.append({"bid_no": bid, "file": fn, "contacts": contacts})
            print(f"  [{bid}] 문의처 후보 {len(contacts)}건 → {fn}", flush=True)
            time.sleep(args.sleep)
    finally:
        mcp.close()
    # 요약을 별도 파일로 (메인 컨텍스트 절약)
    sum_path = os.path.join(OUT_DIR, f"_contacts_summary_{ts}.json")
    with open(sum_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[fetch_rfp] 완료. 요약 → {sum_path}", flush=True)


if __name__ == "__main__":
    main()
