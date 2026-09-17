#!/usr/bin/env python3
"""사업별 깊이있는 통계 보강기

입력:
  data/processed/winners_pool_1w_20260502-0509.csv  (61,628 unique 응찰자행)
  data/processed/bracket_pool_20260509.csv          (256 dedupe 풀, 사업 단위)

출력:
  data/processed/bracket_enriched_20260509.csv      (256건 + 응찰수/투찰률 분포/안정률/이력/콜점수)

산출 컬럼 (기존 풀에 추가):
  - bidder_count       : 같은 공고에 응찰한 업체 수 (opengRank distinct)
  - rank1_rate         : 1위 응찰자 투찰률
  - rank2_rate         : 2위 응찰자 투찰률 (없으면 빈 값)
  - rate_gap           : rank1 - rank2 (음수=1위가 더 낮은 가격)
  - lower_limit_rate   : 낙찰 하한율 (sucsfLwstlmtRt)
  - stability_rate     : 추정가 대비 낙찰가 비율 (낙찰가/추정가, 100% = 단가, <90% = 경쟁)
  - bid_method         : 단독/소액수의/협상/경쟁 등 분류
  - winner_recurrence  : 같은 낙찰사가 1주 풀 안에서 다른 사업에서도 낙찰/응찰한 횟수
  - call_score         : 콜 응답성 점수 0~5 (5=받기 쉬움)
  - call_factors       : 점수 산정 요인 텍스트
"""
import csv
import glob
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
PROC = ROOT / "data" / "processed"
RAW_GLOBS = [
    str(ROOT / "data/raw/data-go-mcp/search_successful_bids/full/*w7d20260502-0508_p*_full*.json"),
    str(ROOT / "data/raw/data-go-mcp/search_successful_bids/*d20260509_p*.json"),
]
NARA_KW_GLOB = str(ROOT / "data/raw/nara-jangteo/get_bids_by_keyword/*.json")
SRC_BRACKET = PROC / "bracket_pool_20260509.csv"
OUT = PROC / "bracket_enriched_20260509.csv"


# ─────────────────────────────────────────────────────────────
# URL 빌더
# ─────────────────────────────────────────────────────────────
def build_g2b_url(bid_no: str) -> str:
    """공고번호 prefix로 g2b 검색 진입 URL 생성.

    - R26BK*: 일반 입찰공고 → 입찰공고 상세(직접) URL
    - R26BD*: 사전규격 → 사전규격 검색 페이지 (직접 URL 없음)
    - 기타: g2b 메인 검색
    """
    if not bid_no:
        return ""
    if bid_no.startswith("R26BK"):
        # 일반 입찰공고: tbidFwd 패턴 (g2b 공식)
        return f"https://www.g2b.go.kr/ep/tbid/tbidFwd.do?taskClCds=5&bidNo={bid_no}&bidSeq=000"
    if bid_no.startswith("R26BD"):
        # 사전규격: 검색 페이지 (사용자가 번호로 직접 검색)
        return "https://www.g2b.go.kr/pn/pnz/pnza/specSelectBfSpecRegList.do"
    return "https://www.g2b.go.kr/"


def load_nara_attachment_urls():
    """nara-jangteo 응답에서 공고번호 → 첫 첨부파일 URL 매핑 추출.

    g2b가 SPA라 공고 직접 URL은 검색 진입만 가능하지만,
    첨부파일 URL은 raw에 명시되어 있어 이를 보조 자료로 활용.
    """
    mapping = {}
    files = sorted(glob.glob(NARA_KW_GLOB))
    files = [f for f in files if "SUMMARY" not in f]
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        data = d.get("data") or {}
        res = data.get("result") if isinstance(data, dict) else None
        if isinstance(res, str):
            text = res
        elif isinstance(res, dict):
            c = res.get("content")
            if isinstance(c, list) and c:
                text = c[0].get("text", "")
            elif isinstance(c, str):
                text = c
            else:
                continue
        else:
            continue
        blocks = re.split(r"^## \d+\.\s+", text, flags=re.MULTILINE)
        for b in blocks[1:]:
            m = re.search(r"(?:공고번호|사전규격번호):\s*([A-Z0-9]+)", b)
            if not m:
                continue
            bn = m.group(1)
            urls = re.findall(r"https?://www\.g2b\.go\.kr[^\s)]+", b)
            if urls and bn not in mapping:
                mapping[bn] = urls[0]
    return mapping


def parse_int(s) -> int:
    if not s:
        return 0
    try:
        return int(float(str(s).replace(",", "")))
    except Exception:
        return 0


def parse_float(s) -> float:
    if not s or s in ("-", ""):
        return 0.0
    try:
        return float(str(s).replace(",", ""))
    except Exception:
        return 0.0


# ─────────────────────────────────────────────────────────────
# 1. 응찰자 행 그룹핑 (winners_pool 기반)
# ─────────────────────────────────────────────────────────────
def build_bidder_groups():
    """raw JSON에서 같은 bidNtceNo 단위로 응찰자 정보 집계.

    winners_pool.csv는 dedupe 단계에서 평탄화 되어 응찰자 행을 잃었으므로
    raw json을 직접 다시 그룹핑한다.
    """
    files = []
    for g in RAW_GLOBS:
        files.extend(sorted(glob.glob(g)))
    files = sorted(set(files))
    print(f"      raw 파일 {len(files)}개 스캔")

    groups = defaultdict(list)  # bid_no → list of bidder rows
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        items = d.get("result", {}).get("items") or []
        for it in items:
            bn = it.get("bidNtceNo", "")
            if bn:
                groups[bn].append(it)

    summary = {}
    for bn, items in groups.items():
        # 응찰자 unique (응찰자 사업자번호 기준)
        bidders = set()
        rates_with_rank = []  # (rank, bidprcRt)
        rates_without_rank = []  # rank 없는 응찰 (보조)
        for it in items:
            bidder_biz = it.get("bidprcCorpBizrno", "") or it.get("fnlSucsfCorpBizrno", "")
            if bidder_biz:
                bidders.add(bidder_biz)
            try:
                rank = int(it.get("opengRank") or 0)
            except (ValueError, TypeError):
                rank = 0
            rate = parse_float(it.get("bidprcRt") or it.get("fnlSucsfRt"))
            if rank > 0 and rate > 0:
                rates_with_rank.append((rank, rate))
            elif rate > 0:
                rates_without_rank.append(rate)

        rates_with_rank.sort()

        # 첫 행 기준으로 사업 메타 (모든 행 동일)
        first = items[0]
        presm = parse_int(first.get("presmptPrce"))
        fnl = parse_int(first.get("fnlSucsfAmt"))
        bss = parse_int(first.get("bssAmt"))
        lower_limit = parse_float(first.get("sucsfLwstlmtRt"))
        stability = (fnl / presm * 100) if presm > 0 and fnl > 0 else 0.0

        bidder_count = len(bidders) or len(items)

        # rank 1, rank 2
        rank1 = next((r[1] for r in rates_with_rank if r[0] == 1), 0.0)
        rank2 = next((r[1] for r in rates_with_rank if r[0] == 2), 0.0)
        rank_last = rates_with_rank[-1][1] if rates_with_rank else 0.0
        rate_gap = (rank1 - rank2) if (rank1 and rank2) else 0.0

        # 입찰 방식 분류
        decision = first.get("bidwinrDcsnMthdNm", "")
        contract = first.get("cntrctCnclsMthdNm", "")
        if "수의시담" in decision:
            bid_method = "수의시담"
        elif "소액" in decision:
            bid_method = "소액수의"
        elif "협상" in decision:
            bid_method = "협상"
        elif "적격심사" in decision:
            bid_method = "적격심사"
        elif "최저" in decision:
            bid_method = "최저가"
        elif "규격가격동시" in decision:
            bid_method = "규격가격동시"
        elif "수의" in contract:
            bid_method = "수의기타"
        elif "일반경쟁" in contract:
            bid_method = "일반경쟁"
        elif "제한경쟁" in contract:
            bid_method = "제한경쟁"
        else:
            bid_method = decision or contract or "-"

        summary[bn] = {
            "bidder_count": bidder_count,
            "rank1_rate": round(rank1, 2) if rank1 else "",
            "rank2_rate": round(rank2, 2) if rank2 else "",
            "rank_last_rate": round(rank_last, 2) if rank_last else "",
            "rate_gap": round(rate_gap, 2) if rate_gap else "",
            "lower_limit_rate": round(lower_limit, 2) if lower_limit else "",
            "stability_rate": round(stability, 2) if stability else "",
            "bid_method": bid_method,
            "bss_amt": bss,
            "presm_amt": presm,
            "final_amt": fnl,
        }
    return summary


# ─────────────────────────────────────────────────────────────
# 2. 낙찰사 이력 (1주 윈도우 내 등장 횟수)
# ─────────────────────────────────────────────────────────────
def build_winner_recurrence():
    """raw JSON에서 낙찰사(`fnlSucsfCorpBizrno`) 단위 등장 공고 수 집계."""
    files = []
    for g in RAW_GLOBS:
        files.extend(sorted(glob.glob(g)))
    files = sorted(set(files))
    counts = defaultdict(set)
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        for it in d.get("result", {}).get("items") or []:
            bz = (it.get("fnlSucsfCorpBizrno") or "").strip()
            bn = (it.get("bidNtceNo") or "").strip()
            # 빈 사업자번호 + 회사명도 빈 경우 스킵 — 응찰진행 행은 제외
            if bz and bn and it.get("fnlSucsfCorpNm"):
                counts[bz].add(bn)
    return {bz: len(bns) for bz, bns in counts.items()}


# ─────────────────────────────────────────────────────────────
# 3. 콜 응답성 점수 (0~5)
# ─────────────────────────────────────────────────────────────
def call_score(row):
    """낙찰사 콜 응답성 점수 (이미 낙찰된 사업의 하도급/협업 영업).
    컨택+규모+낙찰사 유형 중심. 발주방식은 무관 (발주처가 아닌 낙찰사가 대상).

    +1.0 컨택 완비 (전화 + 주소 + 사업자번호)
    +1.0 사업 규모 5천~50억 (영업 가치 적정 구간)
    +0.5 사업 규모 1~10억 (가장 두터운 미들마켓)
    +0.5 응찰자 2+ (경쟁 입찰 → 영업 익숙)
    +0.5 낙찰사가 1주 풀 안에서 2건+ 활동 (활발한 사업자)
    +0.5 낙찰사가 민간 회사 (㈜/주식회사) — 영업 게이트키퍼 적음
    -1.0 대학·연구기관/공공기관 자체 낙찰 (외부 영업 라인 폐쇄)
    -0.5 대형 SI 5사 (게이트키퍼 두꺼움)
    -0.5 컨택 정보 부족 (전화/주소 누락)

    최종 0~5 클립. 응찰진행 행(낙찰사 미정)은 자동 0.0 (별도 응찰 점수 사용).
    """
    score = 0.0
    factors = []

    has_winner = bool(row.get("winner_corp"))
    if not has_winner:
        return 0.0, "응찰진행(낙찰사미정)"

    has_tel = bool(row.get("winner_tel"))
    has_addr = bool(row.get("winner_addr"))
    has_biz = bool(row.get("winner_bizrno"))
    if has_tel and has_addr and has_biz:
        score += 1.0
        factors.append("컨택완비+1.0")
    elif not has_tel:
        score -= 0.5
        factors.append("전화누락-0.5")

    # 사업 규모
    amt = parse_int(row.get("amount"))
    if 50_000_000 <= amt <= 5_000_000_000:
        score += 1.0
        factors.append("규모5천~50억+1.0")
    if 100_000_000 <= amt <= 1_000_000_000:
        score += 0.5
        factors.append("규모1~10억+0.5")

    # 응찰자 수
    bc = row.get("_bidder_count", 0)
    try:
        bc = int(bc)
    except (ValueError, TypeError):
        bc = 0
    if bc >= 2:
        score += 0.5
        factors.append(f"응찰자{bc}자+0.5")

    # 낙찰사 활동성 (1주 윈도우 내 등장 횟수)
    rec = row.get("winner_recurrence", 0)
    try:
        rec = int(rec)
    except (ValueError, TypeError):
        rec = 0
    if rec >= 2:
        score += 0.5
        factors.append(f"활발사업자({rec}건)+0.5")

    # 낙찰사 유형
    winner = (row.get("winner_corp") or "")
    if winner.startswith("주식회사") or winner.startswith("(주)") or winner.startswith("㈜"):
        score += 0.5
        factors.append("민간회사+0.5")
    if any(p in winner for p in ["산학협력단", "대학교", "연구원", "연구재단", "과학기술원", "한국지능정보사회진흥원"]):
        score -= 1.0
        factors.append("대학·연구기관-1.0")
    if any(p in winner for p in ["삼성에스디에스", "엘지씨엔에스", "SK주식회사", "KT ", "포스코", "롯데정보통신", "현대오토에버"]):
        score -= 0.5
        factors.append("대형SI-0.5")

    # 클립 0~5
    score = max(0.0, min(5.0, score))
    return round(score, 1), "; ".join(factors) if factors else "-"


def bid_score(row):
    """응찰 진입 가능성 점수 (응찰진행 사업, 신규 응찰 검토 대상).
    개방성 + 디지털친화 + 사업 규모 중심.

    +1.5 협상에의한계약 (점수제 — 기술력으로 진입 가능)
    +1.0 적격심사 (규격 통과만 하면 가격 경쟁)
    +0.5 일반경쟁 또는 제한경쟁
    -0.5 수의시담 (기존 거래선 우선)
    +1.0 사업 규모 1~30억
    +0.5 사업 규모 5천~5억
    +0.5 디지털친화기관
    +0.5 Sion Lab 강점 도메인 (AI/데이터/OCR/문서)
    -0.5 SI/시스템구축 단순 + 단독수의 신호
    """
    score = 0.0
    factors = []

    if row.get("winner_corp"):
        return 0.0, "낙찰완료(응찰종료)"

    decision = row.get("winner_decision", "") or ""
    contract = row.get("contract_type", "") or ""
    if "협상" in decision:
        score += 1.5
        factors.append("협상에의한계약+1.5")
    elif "적격심사" in decision:
        score += 1.0
        factors.append("적격심사+1.0")
    elif "일반경쟁" in contract or "제한경쟁" in contract:
        score += 0.5
        factors.append("경쟁입찰+0.5")
    elif "수의시담" in decision:
        score -= 0.5
        factors.append("수의시담-0.5")

    amt = parse_int(row.get("amount"))
    if 100_000_000 <= amt <= 3_000_000_000:
        score += 1.0
        factors.append("규모1~30억+1.0")
    if 50_000_000 <= amt <= 500_000_000:
        score += 0.5
        factors.append("규모5천~5억+0.5")

    agency = (row.get("agency") or "")
    if any(k in agency for k in ["NIA", "지능정보사회진흥원", "KISA", "조달청", "교육청", "국세청", "우정사업본부", "정보통신산업진흥원", "한국지능정보"]):
        score += 0.5
        factors.append("디지털친화기관+0.5")

    domain = row.get("domain", "") or ""
    if domain in ("AI/데이터", "OCR/문서", "Chatbot/CRM/ERP"):
        score += 0.5
        factors.append(f"{domain}도메인+0.5")

    score = max(0.0, min(5.0, score))
    return round(score, 1), "; ".join(factors) if factors else "-"


# ─────────────────────────────────────────────────────────────
# 4. 메인
# ─────────────────────────────────────────────────────────────
def main():
    print("[1/4] 응찰자 그룹 집계 ...")
    bidder_summary = build_bidder_groups()
    print(f"      {len(bidder_summary)}개 공고 그룹")

    print("[2/4] 낙찰사 이력 집계 ...")
    recurrence = build_winner_recurrence()
    print(f"      {len(recurrence)}개 낙찰사")

    print("[2.5/4] nara-jangteo 첨부 URL 매핑 ...")
    attachment_urls = load_nara_attachment_urls()
    print(f"      공고-첨부 매핑 {len(attachment_urls)}건")

    print("[3/4] bracket_pool 로드 + 보강 ...")
    rows = list(csv.DictReader(open(SRC_BRACKET, encoding="utf-8-sig")))
    print(f"      {len(rows)}건")

    enriched = []
    for r in rows:
        bn = r["bid_no"]
        bs = bidder_summary.get(bn, {})
        # 응찰자 통계 머지
        r["bidder_count"] = bs.get("bidder_count", "")
        r["rank1_rate"] = bs.get("rank1_rate", "")
        r["rank2_rate"] = bs.get("rank2_rate", "")
        r["rank_last_rate"] = bs.get("rank_last_rate", "")
        r["rate_gap"] = bs.get("rate_gap", "")
        r["lower_limit_rate"] = bs.get("lower_limit_rate", "")
        r["stability_rate"] = bs.get("stability_rate", "")
        r["bid_method"] = bs.get("bid_method", r.get("winner_decision", ""))
        if not r.get("amount") or int(r.get("amount") or 0) == 0:
            # bracket 갱신 (raw 기반 금액으로 보강)
            r["amount"] = bs.get("final_amt") or bs.get("presm_amt") or 0

        # 낙찰사 이력 (사업자번호 기준)
        bz = r.get("winner_bizrno", "")
        r["winner_recurrence"] = recurrence.get(bz, 0) if bz else 0

        # URL 보강
        r["g2b_url"] = build_g2b_url(bn)
        r["attachment_url"] = attachment_urls.get(bn, "")

        # 콜 응답성 + 응찰 진입 점수
        r["_bidder_count"] = r["bidder_count"]
        cs, cf = call_score(r)
        bs2, bf = bid_score(r)
        r["call_score"] = cs
        r["call_factors"] = cf
        r["bid_score"] = bs2
        r["bid_factors"] = bf
        del r["_bidder_count"]
        enriched.append(r)

    print("[4/4] 저장 ...")
    cols = list(enriched[0].keys()) if enriched else []
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        # 정렬: 구간 → max(call,bid) → 금액
        for r in sorted(enriched, key=lambda r: (
            r["bracket"],
            -max(float(r["call_score"] or 0), float(r["bid_score"] or 0)),
            -int(r.get("amount") or 0),
        )):
            w.writerow(r)
    print(f"[save] {OUT} ({len(enriched)}건)")

    # 콘솔 요약
    from collections import Counter
    print(f"\n=== 콜 응답성 점수 분포 (낙찰완료) ===")
    completed = [r for r in enriched if r.get("winner_corp")]
    score_dist = Counter(round(float(r["call_score"] or 0) * 2) / 2 for r in completed)
    for s in sorted(score_dist):
        print(f"  {s:>3.1f}점: {score_dist[s]}건")

    print(f"\n=== 응찰 진입 점수 분포 (응찰진행) ===")
    ongoing = [r for r in enriched if not r.get("winner_corp")]
    bs_dist = Counter(round(float(r["bid_score"] or 0) * 2) / 2 for r in ongoing)
    for s in sorted(bs_dist):
        print(f"  {s:>3.1f}점: {bs_dist[s]}건")

    print(f"\n=== 입찰 방식 분포 ===")
    method_dist = Counter(r["bid_method"] or "-" for r in enriched)
    for m, c in method_dist.most_common(10):
        print(f"  {m}: {c}건")

    print(f"\n=== 콜 응답성 ≥ 2.5 (영업 콜 우선 후보) ===")
    hot_call = [r for r in completed if float(r["call_score"] or 0) >= 2.5]
    hot_call.sort(key=lambda r: -float(r["call_score"]))
    print(f"  {len(hot_call)}건")
    for r in hot_call[:15]:
        amt_e = int(r.get("amount") or 0) / 1e8
        bc = r.get("bidder_count") or "-"
        rate = r.get("rank1_rate") or "-"
        print(f"  [{r['call_score']:>3}] {r['bracket']:<14} {amt_e:>5.2f}억 응찰{bc}자 투찰{rate}% {r['bid_method'][:6]:<7}| {r['title'][:38]} | {r['winner_corp'][:16]}")

    print(f"\n=== 응찰 진입 점수 ≥ 2.5 (응찰 검토 우선 후보) ===")
    hot_bid = [r for r in ongoing if float(r["bid_score"] or 0) >= 2.5]
    hot_bid.sort(key=lambda r: -float(r["bid_score"]))
    print(f"  {len(hot_bid)}건")
    for r in hot_bid[:15]:
        amt_e = int(r.get("amount") or 0) / 1e8
        print(f"  [{r['bid_score']:>3}] {r['bracket']:<14} {amt_e:>5.2f}억 {r['bid_method'][:6]:<7}| {r['title'][:42]} | {r['agency'][:18]}")


if __name__ == "__main__":
    main()
