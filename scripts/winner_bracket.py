#!/usr/bin/env python3
"""금액대별 영업 풀 분할판 — 4구간(1천 미만 / 1천~5천 / 5천~1억 / 1억+)

입력 (3개 소스 통합):
  1. data/processed/winner_collab_score_20260509.csv
     — search_successful_bids 기반 1주 dedupe 198건 (낙찰액/추정가 + 도메인)
  2. data/processed/winners_match_agency_1w_20260502-0509.csv
     — 매칭 회사 12사 (점수+컨택)
  3. data/raw/nara-jangteo/get_bids_by_keyword/*_14d_*.json
     — 진행중/마감 공고 풀 (텍스트 응답 파싱)

출력:
  - data/processed/bracket_pool_20260509.csv   (전체 통합 풀, 구간 라벨 부여)
  - data/processed/bracket_summary_20260509.csv (구간×키워드/도메인 매트릭스)
  - data/processed/bracket_top_targets_20260509.csv (구간별 Top 후보)
"""
import csv
import glob
import json
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_RAW = ROOT / "data" / "raw"
NARA_GLOB = str(DATA_RAW / "nara-jangteo" / "get_bids_by_keyword" / "*.json")

OUT_POOL = DATA_PROCESSED / "bracket_pool_20260509.csv"
OUT_SUMMARY = DATA_PROCESSED / "bracket_summary_20260509.csv"
OUT_TOP = DATA_PROCESSED / "bracket_top_targets_20260509.csv"

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]
HOLIDAYS_2026_05 = {"20260505": "어린이날"}

# 4구간 정의 (원 단위)
BRACKETS = [
    ("B1_LT_1000만",     0,            10_000_000),
    ("B2_1000_5000만",   10_000_000,   50_000_000),
    ("B3_5000_1억",      50_000_000,   100_000_000),
    ("B4_GTE_1억",       100_000_000,  10**15),
]


def normalize_yyyymmdd(s) -> str:
    if not s:
        return ""
    digits = re.sub(r"\D", "", str(s))[:8]
    return digits if len(digits) == 8 else ""


def fmt_date_with_dow(value) -> str:
    s = normalize_yyyymmdd(value)
    if not s:
        return "-"
    try:
        dt = datetime.strptime(s, "%Y%m%d")
    except ValueError:
        return str(value)
    dow = WEEKDAY_KR[dt.weekday()]
    holiday = HOLIDAYS_2026_05.get(s)
    suffix = f"{dow}/{holiday}" if holiday else dow
    return f"{dt.strftime('%Y-%m-%d')}({suffix})"


def bracket_of(amount: int) -> str:
    """금액(원) → 구간 라벨."""
    for label, lo, hi in BRACKETS:
        if lo <= amount < hi:
            return label
    return "B4_GTE_1억"  # 안전망


def parse_amount(s) -> int:
    if not s:
        return 0
    try:
        return int(float(str(s).replace(",", "")))
    except Exception:
        return 0


# ─────────────────────────────────────────────────────────────
# 1. winner_collab_score CSV 로드 (낙찰 완료/응찰 + 도메인 매칭)
# ─────────────────────────────────────────────────────────────
def load_collab_csv():
    src = DATA_PROCESSED / "winner_collab_score_20260509.csv"
    if not src.exists():
        print(f"[skip] {src} 없음")
        return []
    rows = []
    with open(src, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            amt = parse_amount(r.get("final_amt")) or parse_amount(r.get("presm_amt"))
            if amt == 0:
                continue
            rows.append({
                "source": "successful_bids",
                "bid_no": r.get("bid_no", ""),
                "title": r.get("title", ""),
                "domain": r.get("domain", ""),
                "matched_kw": r.get("matched_kw", ""),
                "amount": amt,
                "amount_kind": "낙찰" if parse_amount(r.get("final_amt")) else "추정",
                "agency": r.get("ntce_inst") or r.get("dmnd_inst", ""),
                "contract_type": r.get("contract_type", ""),
                "winner_decision": r.get("winner_decision", ""),
                "winner_corp": r.get("winner_corp", ""),
                "winner_ceo": r.get("winner_ceo", ""),
                "winner_tel": r.get("winner_tel", ""),
                "winner_bizrno": r.get("winner_bizrno", ""),
                "winner_addr": r.get("winner_addr", ""),
                "score": int(r.get("score", 0) or 0),
                "fnl_date_kr": r.get("fnl_date_kr", ""),
                "openg_date_kr": r.get("openg_date_kr", ""),
                "status": "낙찰완료" if r.get("winner_corp") else "응찰진행",
            })
    print(f"[load] winner_collab_score: {len(rows)}건 (금액 0 제외)")
    return rows


# ─────────────────────────────────────────────────────────────
# 2. nara-jangteo get_bids_by_keyword 텍스트 응답 파싱
#    응답 포맷: "## N. <제목>\n   📌 공고번호: ...\n   🏢 수요기관: ...\n   💰 예산: 727,272,727원\n   ⏰ 마감일시: ...\n"
# ─────────────────────────────────────────────────────────────
def parse_nara_text(text: str, keyword: str):
    """get_bids_by_keyword 텍스트를 dict 리스트로 파싱."""
    items = []
    # 일반 / 사전규격 두 섹션 — 둘 다 동일 포맷
    blocks = re.split(r"^## \d+\.\s+", text, flags=re.MULTILINE)
    section = "regular"
    if "사전규격" in (blocks[0] if blocks else ""):
        section = "prespec"
    for block in blocks[1:]:
        # 첫 줄이 제목, 이후 마크다운 필드들
        lines = block.strip().split("\n")
        if not lines:
            continue
        title = lines[0].strip()
        rec = {"title": title, "keyword": keyword, "section": section}
        for ln in lines[1:]:
            ln = ln.strip()
            # 공고번호 (일반) 또는 사전규격번호 (사전규격) 모두 매칭
            if "공고번호:" in ln or "사전규격번호:" in ln:
                m = re.search(r"(?:공고번호|사전규격번호):\s*([A-Z0-9]+)", ln)
                if m: rec["bid_no"] = m.group(1)
            # 수요기관 (일반) 또는 발주기관 (사전규격)
            elif "수요기관:" in ln:
                rec["agency"] = ln.split("수요기관:", 1)[1].strip()
            elif "발주기관:" in ln:
                rec["agency"] = ln.split("발주기관:", 1)[1].strip()
            # 예산 (일반) 또는 배정예산 (사전규격)
            elif "예산:" in ln or "배정예산:" in ln:
                m = re.search(r"([\d,]+)\s*원", ln)
                if m: rec["budget"] = int(m.group(1).replace(",", ""))
            # 마감일시 (일반) 또는 의견마감일시 (사전규격)
            elif "마감일시:" in ln:
                m = re.search(r"(\d{4}-\d{2}-\d{2})\s*(\d{2}:\d{2}:\d{2})", ln)
                if m:
                    rec["close_date"] = m.group(1)
                    rec["close_time"] = m.group(2)
                rec["close_status"] = "진행중" if "진행중" in ln else ("마감" if "마감" in ln else "")
        if rec.get("bid_no") and rec.get("budget"):
            items.append(rec)
        # section 토글 (응답에 일반→사전규격 순서로 등장)
        if "📋 **사전규격" in block:
            section = "prespec"
    return items


def load_nara_keyword_pool():
    files = sorted(glob.glob(NARA_GLOB))
    files = [f for f in files if "SUMMARY" not in f]
    rows = []
    by_kw = defaultdict(int)
    seen_keys = set()
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            print(f"WARN {os.path.basename(f)}: {e}")
            continue
        kw = (d.get("_meta") or {}).get("params", {}).get("keyword", "") or os.path.basename(f).split("_")[0]
        text = ""
        try:
            data = d.get("data") or {}
            res = data.get("result") if isinstance(data, dict) else None
            # 두 응답 포맷 모두 지원:
            # (5/8 mcp-operator 1차) result.content[0].text 구조
            # (5/9 mcp-operator 2차) result 자체가 문자열
            if isinstance(res, str):
                text = res
            elif isinstance(res, dict):
                content = res.get("content")
                if isinstance(content, list) and content:
                    text = content[0].get("text", "")
                elif isinstance(content, str):
                    text = content
        except Exception:
            continue
        if not text:
            continue
        # 일반 + 사전규격 모두 같은 텍스트에 들어 있음 — 분할 마커로 한 번 더 처리
        for split_marker in ["📋 **사전규격", "📋 사전규격"]:
            if split_marker in text:
                regular_part, prespec_part = text.split(split_marker, 1)
                items = parse_nara_text(regular_part, kw)
                for it in items:
                    it["section"] = "regular"
                items_pre = parse_nara_text(split_marker + prespec_part, kw)
                for it in items_pre:
                    it["section"] = "prespec"
                items = items + items_pre
                break
        else:
            items = parse_nara_text(text, kw)

        for it in items:
            key = (it["bid_no"], kw)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            it["amount"] = it.pop("budget", 0)
            rows.append({
                "source": "nara_keyword",
                "bid_no": it["bid_no"],
                "title": it["title"],
                "domain": "",
                "matched_kw": kw,
                "amount": it["amount"],
                "amount_kind": "예산",
                "agency": it.get("agency", ""),
                "contract_type": "",
                "winner_decision": "",
                "winner_corp": "",
                "winner_ceo": "",
                "winner_tel": "",
                "winner_bizrno": "",
                "winner_addr": "",
                "score": 0,
                "fnl_date_kr": "",
                "openg_date_kr": "",
                "status": it.get("close_status", "") or ("진행중" if it.get("section") == "prespec" else "마감"),
                "close_date": it.get("close_date", ""),
                "close_date_kr": fmt_date_with_dow(it.get("close_date", "")),
                "section": it.get("section", "regular"),
            })
            by_kw[kw] += 1
    print(f"[load] nara-jangteo: {len(rows)}건 / 키워드 {len(by_kw)}개")
    for kw, cnt in sorted(by_kw.items(), key=lambda x: -x[1]):
        print(f"   - {kw}: {cnt}건")
    return rows


# ─────────────────────────────────────────────────────────────
# 3. 통합 + 구간 부여 + dedupe (bid_no 단위 — 같은 공고 여러 키워드 매칭 가능)
# ─────────────────────────────────────────────────────────────
def merge_and_bracket(collab_rows, nara_rows):
    pool = collab_rows + nara_rows
    # bid_no 단위 dedupe — collab 우선(낙찰 정보 풍부), nara는 매칭 키워드만 추가
    merged = {}
    for r in pool:
        bn = r["bid_no"]
        if not bn:
            continue
        r["bracket"] = bracket_of(r["amount"])
        if bn not in merged:
            merged[bn] = r
            merged[bn]["all_keywords"] = set([r["matched_kw"]] if r["matched_kw"] else [])
        else:
            # 키워드만 추가
            if r["matched_kw"]:
                merged[bn]["all_keywords"].add(r["matched_kw"])
            # collab 소스가 우선이지만 nara에만 있는 close_date_kr 등은 보강
            if not merged[bn].get("close_date_kr") and r.get("close_date_kr"):
                merged[bn]["close_date_kr"] = r["close_date_kr"]
    final = []
    for bn, r in merged.items():
        r["all_keywords"] = ",".join(sorted(r["all_keywords"]))
        final.append(r)
    return final


def write_pool_csv(rows):
    cols = ["bracket", "amount", "amount_kind", "status", "source", "bid_no", "title",
            "domain", "matched_kw", "all_keywords", "score",
            "agency", "contract_type", "winner_decision",
            "winner_corp", "winner_ceo", "winner_tel", "winner_bizrno", "winner_addr",
            "fnl_date_kr", "openg_date_kr", "close_date_kr", "section"]
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    with open(OUT_POOL, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        rows_sorted = sorted(rows, key=lambda r: (r["bracket"], -r["amount"]))
        for r in rows_sorted:
            w.writerow(r)
    print(f"[save] {OUT_POOL} ({len(rows)}건)")


def write_summary(rows):
    """구간 × (도메인 / 출처 / 진행상태) 매트릭스."""
    counts = defaultdict(lambda: defaultdict(int))
    for r in rows:
        b = r["bracket"]
        counts[b]["total"] += 1
        counts[b][f"src_{r['source']}"] += 1
        counts[b][f"sts_{r['status']}"] += 1
        if r["domain"]:
            counts[b][f"dom_{r['domain']}"] += 1
        if r["winner_corp"]:
            counts[b]["winner_corp_set"] = counts[b].get("winner_corp_set", 0) + 1

    with open(OUT_SUMMARY, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        all_keys = sorted({k for d in counts.values() for k in d})
        w.writerow(["bracket"] + all_keys)
        for b, _, _ in BRACKETS:
            row = [b] + [counts[b].get(k, 0) for k in all_keys]
            w.writerow(row)
    print(f"[save] {OUT_SUMMARY}")


def write_top_targets(rows):
    """구간별 Top 후보 — 낙찰 컨택 완비 우선 → 점수/금액."""
    by_bracket = defaultdict(list)
    for r in rows:
        by_bracket[r["bracket"]].append(r)
    for b in by_bracket:
        # 1) 낙찰자 컨택 완비 우선 2) score 내림차순 3) 금액 내림차순
        by_bracket[b].sort(key=lambda r: (
            -1 if r["winner_corp"] and r["winner_tel"] else 0,
            -int(r["score"] or 0),
            -r["amount"],
        ))
    cols = ["bracket", "rank", "amount_eok", "amount_kind", "status", "score",
            "bid_no", "title", "all_keywords", "domain",
            "agency", "winner_corp", "winner_ceo", "winner_tel", "winner_bizrno",
            "fnl_date_kr", "close_date_kr", "contract_type"]
    with open(OUT_TOP, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for b, _, _ in BRACKETS:
            for i, r in enumerate(by_bracket[b][:15], 1):
                w.writerow([
                    b, i, round(r["amount"]/1e8, 2), r["amount_kind"], r["status"], r["score"],
                    r["bid_no"], r["title"][:80], r["all_keywords"], r["domain"],
                    r["agency"], r["winner_corp"], r["winner_ceo"], r["winner_tel"], r["winner_bizrno"],
                    r["fnl_date_kr"], r.get("close_date_kr", ""), r["contract_type"],
                ])
    print(f"[save] {OUT_TOP}")


def main():
    collab = load_collab_csv()
    nara = load_nara_keyword_pool()
    print(f"[merge] collab {len(collab)} + nara {len(nara)} = {len(collab)+len(nara)} (pre-dedupe)")
    rows = merge_and_bracket(collab, nara)
    print(f"[merge] dedupe by bid_no: {len(rows)}건")

    write_pool_csv(rows)
    write_summary(rows)
    write_top_targets(rows)

    # 콘솔 요약
    print("\n=== 금액 구간별 분포 ===")
    print(f"{'구간':<18} {'전체':>5} {'낙찰완료':>8} {'응찰진행':>8} {'마감':>5} {'진행중':>5}")
    by_b = defaultdict(lambda: defaultdict(int))
    for r in rows:
        by_b[r["bracket"]]["전체"] += 1
        by_b[r["bracket"]][r["status"]] += 1
    for label, _, _ in BRACKETS:
        d = by_b[label]
        print(f"{label:<18} {d['전체']:>5} {d.get('낙찰완료',0):>8} {d.get('응찰진행',0):>8} {d.get('마감',0):>5} {d.get('진행중',0):>5}")


if __name__ == "__main__":
    main()
