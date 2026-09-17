#!/usr/bin/env python3
"""낙찰 풀(1주: 0610-0616, full pool ~534p) → Sion Lab 키워드 매칭(확장) → 회사 단위 그룹화 + 영업 점수 보정 + 요일 표기

입력: data/raw/data-go-mcp/search_successful_bids/full/용역_w7d20260610-0616_p*_full*.json
출력:
  - data/processed/winners_pool_1w_20260610-0616.csv (전체 낙찰 풀)
  - data/processed/winners_match_agency_1w_20260610-0616.csv (매칭 회사 그룹, 영업 점수 보정)
  - data/processed/winners_dow_dist_1w_20260610-0616.csv (요일별 매칭 분포)
"""
import json, glob, csv, os, re
from collections import defaultdict
from datetime import datetime

# 저장소 루트를 스크립트 위치에서 유도한다 (scripts/ 의 부모).
# 하드코딩하면 다른 사용자가 클론해서 실행할 수 없다.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_GLOBS = [
    f"{ROOT}/data/raw/data-go-mcp/search_successful_bids/full/*용역_w7d20260610-0616_p*_full*.json",
]
OUT_FULL = f"{ROOT}/data/processed/winners_pool_1w_20260610-0616.csv"
OUT_MATCH = f"{ROOT}/data/processed/winners_match_agency_1w_20260610-0616.csv"
OUT_DOW = f"{ROOT}/data/processed/winners_dow_dist_1w_20260610-0616.csv"
MIN_SCORE = 1.5

# 윈도우 (요일별 분포 표 생성용) — 2026-06-10~16, 공휴일 없음(현충일 6/6은 윈도우 밖)
WINDOW_DATES = ["20260610", "20260611", "20260612", "20260613",
                "20260614", "20260615", "20260616"]
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]
HOLIDAYS_2026_05 = {}  # 6/10~6/16 공휴일 없음


def normalize_yyyymmdd(s: str) -> str:
    """'2026-05-07' / '20260507' / '2026-05-07T...' → '20260507'. 실패 시 ''."""
    if not s:
        return ""
    digits = re.sub(r"\D", "", str(s))[:8]
    return digits if len(digits) == 8 else ""


def fmt_date_with_dow(value: str) -> str:
    """다양한 입력을 'YYYY-MM-DD(요일[/공휴일])' 형식으로."""
    s = normalize_yyyymmdd(value)
    if not s:
        return "-"
    try:
        dt = datetime.strptime(s, "%Y%m%d")
    except ValueError:
        return value or "-"
    dow = WEEKDAY_KR[dt.weekday()]
    holiday = HOLIDAYS_2026_05.get(s)
    suffix = f"{dow}/{holiday}" if holiday else dow
    return f"{dt.strftime('%Y-%m-%d')}({suffix})"


def pick_event_date(item: dict) -> str:
    """낙찰일(`fnlSucsfDate`) 우선, 없으면 개찰일(`opengDate`). 정규화된 YYYYMMDD."""
    return normalize_yyyymmdd(item.get("fnlSucsfDate") or item.get("opengDate") or "")


# 사용자 요청 키워드 확장: Sion Lab 강점(RAG/LLM/문서자동화/데이터품질/벡터DB) 추가
KEYWORDS = [
    (3.5, ["RAG", "검색증강", "Retrieval"]),                    # 신규 — Sion Lab 핵심
    (3.5, ["LLM", "대규모언어모델", "거대언어모델", "생성형"]),  # 신규
    (3.0, ["OCR", "광학문자인식"]),
    (3.0, ["문서자동화", "문서 자동화", "문서지능화", "문서인식"]),  # 가중치 상향
    (2.5, ["데이터품질", "데이터 품질", "데이터 정제", "데이터정제"]),  # 신규
    (2.5, ["AI", "인공지능"]),
    (2.5, ["RPA", "업무자동화", "데이터자동화", "데이터 자동화", "프로세스 자동화", "자동화 시스템"]),
    (2.0, ["벡터DB", "벡터 검색", "임베딩", "시맨틱 검색"]),     # 신규
    (2.0, ["ERP"]),
    (2.0, ["CRM"]),
    (1.8, ["챗봇", "NLP", "자연어처리", "콜봇"]),
    (1.5, ["빅데이터", "머신러닝", "딥러닝"]),
    (1.5, ["오픈API", "데이터 연계", "API 연계"]),
    (1.2, ["이미지 인식", "컴퓨터비전", "영상분석"]),
    (1.0, ["자동화"]),  # 단독 매칭 시 약한 가중치 (그룹 break로 중복 가산 방지)
]
DIGITAL_AGENCIES = ["NIA", "한국지능정보사회진흥원", "KISA", "한국인터넷진흥원", "조달청", "교육청", "국세청", "우정사업본부"]


def load_items():
    files = []
    for g in RAW_GLOBS:
        files.extend(sorted(glob.glob(g)))
    files = sorted(set(files))
    all_items = []
    for f in files:
        d = json.load(open(f))
        items = d.get("result", {}).get("items") or []
        for it in items:
            it["_source_file"] = os.path.basename(f)
        all_items.extend(items)
    return all_items, files


def match_keywords(title):
    """제목에 매칭된 키워드 가중치 합 + 매칭 키워드 리스트 반환"""
    if not title:
        return 0.0, []
    score = 0.0
    matched = []
    for w, kws in KEYWORDS:
        for kw in kws:
            if kw.lower() in title.lower():
                score += w
                matched.append(kw)
                break  # 같은 가중치 그룹에서 한 번만 가산
    return score, matched


def parse_money(s):
    try:
        return int(float(s)) if s not in ("", None) else 0
    except Exception:
        return 0


def parse_rate(s):
    try:
        return float(s) if s not in ("", None) else 0.0
    except Exception:
        return 0.0


def get_sido(adrs):
    """주소 첫 토큰(시도)"""
    if not adrs:
        return ""
    m = re.match(r"\s*([가-힣]+(?:특별시|광역시|특별자치시|특별자치도|도|시))", adrs)
    return m.group(1) if m else (adrs[:6] if adrs else "")


def main():
    items, files = load_items()
    print(f"[load] {len(files)} files / {len(items)} items (raw)")

    # 윈도우 외 제외 (full pool에 윈도우 경계 외 일부 포함될 수 있음)
    window_set = set(WINDOW_DATES)
    in_window = []
    for it in items:
        d = pick_event_date(it)
        if d and d in window_set:
            in_window.append(it)
    print(f"[window] {len(in_window)}/{len(items)} items in 2026-06-10~2026-06-16")

    # full pool 페이지 중복 제거 (동일 공고+응찰 순위+낙찰자 사업자번호 키)
    seen = set()
    deduped = []
    for it in in_window:
        key = (
            it.get("bidNtceNo", ""),
            it.get("bidNtceOrd", ""),
            it.get("opengRank", ""),
            it.get("fnlSucsfCorpBizrno", "") or it.get("bidprcCorpBizrno", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)
    print(f"[dedupe] {len(deduped)}/{len(in_window)} unique records")
    items = deduped

    # 1) 전체 풀 CSV (open_date_kr 컬럼 추가)
    full_cols = ["bidNtceNo", "bidNtceNm", "bsnsDivNm", "ntceInsttNm", "dmndInsttNm",
                 "cntrctCnclsMthdNm", "bidwinrDcsnMthdNm", "presmptPrce",
                 "fnlSucsfAmt", "fnlSucsfRt", "fnlSucsfDate", "open_date_kr",
                 "fnlSucsfCorpNm", "fnlSucsfCorpCeoNm", "fnlSucsfCorpBizrno",
                 "fnlSucsfCorpContactTel", "fnlSucsfCorpAdrs"]
    os.makedirs(os.path.dirname(OUT_FULL), exist_ok=True)
    with open(OUT_FULL, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(full_cols)
        for it in items:
            row = []
            for c in full_cols:
                if c == "open_date_kr":
                    row.append(fmt_date_with_dow(pick_event_date(it)))
                else:
                    row.append(it.get(c, ""))
            w.writerow(row)
    print(f"[full] {OUT_FULL} ({len(items)} rows)")

    # 2) 매칭 (점수 ≥ 1.5) 후 회사 단위 그룹화
    #    매칭 dedupe 키: (공고번호 + 낙찰사 사업자번호) — 같은 공고에 다른 응찰순위 행으로
    #    동일 낙찰사가 반복 출현하는 케이스 제거
    matched_items = []
    bid_corp_seen = set()
    for it in items:
        title = it.get("bidNtceNm") or ""
        score, kws = match_keywords(title)
        if score < MIN_SCORE:
            continue
        corp = (it.get("fnlSucsfCorpNm") or "").strip()
        bizrno = (it.get("fnlSucsfCorpBizrno") or "").strip()
        if not corp:
            continue  # 낙찰업체 미기재 행 제외
        bid_corp_key = (it.get("bidNtceNo", ""), bizrno or corp)
        if bid_corp_key in bid_corp_seen:
            continue
        bid_corp_seen.add(bid_corp_key)
        it["_match_score"] = score
        it["_matched_kw"] = kws
        matched_items.append(it)
    print(f"[match] {len(matched_items)} items 매칭 (점수>=1.5 + 낙찰업체 존재 + 공고x낙찰사 unique)")

    # 회사 단위 그룹화 (회사명 + 사업자번호 키)
    groups = defaultdict(list)
    for it in matched_items:
        key = (it.get("fnlSucsfCorpNm", "").strip(), it.get("fnlSucsfCorpBizrno", "").strip())
        groups[key].append(it)

    # 3) 영업 보정 점수 계산
    rows = []
    for (corp, bizrno), grp in groups.items():
        ceo = grp[0].get("fnlSucsfCorpCeoNm", "")
        tel = grp[0].get("fnlSucsfCorpContactTel", "")
        adrs = grp[0].get("fnlSucsfCorpAdrs", "")
        sido = get_sido(adrs)

        # 점수 합산
        kw_score = sum(it["_match_score"] for it in grp)

        # 보정
        bonus = 0.0
        bonus_notes = []

        # 평균 투찰률
        rates = [parse_rate(it.get("fnlSucsfRt")) for it in grp]
        rates = [r for r in rates if r > 0]
        avg_rate = sum(rates) / len(rates) if rates else 0.0
        if 70 <= avg_rate <= 95:
            bonus += 1.0
            bonus_notes.append(f"경쟁시장(투찰률 {avg_rate:.1f}%)+1.0")
        elif avg_rate >= 99.5:
            bonus -= 0.5
            bonus_notes.append(f"단독·수의({avg_rate:.1f}%)-0.5")

        # 총 낙찰금액
        total_amt = sum(parse_money(it.get("fnlSucsfAmt")) for it in grp)
        if 50_000_000 <= total_amt <= 500_000_000:
            bonus += 0.5
            bonus_notes.append("적정규모(5천~5억)+0.5")
        elif total_amt > 6_000_000_000:
            bonus -= 1.0
            bonus_notes.append("대형SI(60억+)-1.0")

        # 사업수
        if len(grp) >= 2:
            bonus += 0.5
            bonus_notes.append(f"활발({len(grp)}건)+0.5")

        # 디지털 친화 발주처 가산 (매칭 사업 중 1회라도)
        agencies = set()
        for it in grp:
            for k in ("ntceInsttNm", "dmndInsttNm"):
                v = it.get(k) or ""
                if v: agencies.add(v)
        if any(any(d in a for d in DIGITAL_AGENCIES) for a in agencies):
            bonus += 0.5
            bonus_notes.append("디지털친화기관+0.5")

        final_score = round(kw_score + bonus, 2)

        # 매칭 사업 요약
        biz_titles = [it.get("bidNtceNm", "") for it in grp]
        all_kws = sorted(set(k for it in grp for k in it["_matched_kw"]))

        # 최근 낙찰일 (없으면 개찰일)
        dates = [pick_event_date(it) for it in grp]
        dates = [d for d in dates if d]
        recent = max(dates) if dates else ""

        # 사업별 (공고번호, 제목, 낙찰일+요일, 발주기관, 계약방식, 낙찰액, 투찰률) 직렬화 — 리포트 카드 작성용
        biz_details = []
        for it in grp:
            biz_details.append("|".join([
                it.get("bidNtceNo", ""),
                (it.get("bidNtceNm") or "").replace("|", "/"),
                fmt_date_with_dow(pick_event_date(it)),
                (it.get("ntceInsttNm") or "").replace("|", "/"),
                it.get("cntrctCnclsMthdNm", ""),
                it.get("bidwinrDcsnMthdNm", ""),
                str(parse_money(it.get("fnlSucsfAmt"))),
                str(parse_rate(it.get("fnlSucsfRt"))),
            ]))

        rows.append({
            "corp": corp, "ceo": ceo, "tel": tel, "bizrno": bizrno, "sido": sido, "adrs": adrs,
            "kw_score": round(kw_score, 2), "bonus": round(bonus, 2), "final_score": final_score,
            "biz_count": len(grp),
            "matched_kw": ",".join(all_kws),
            "biz_titles": " || ".join(biz_titles[:5]),
            "biz_details": " || ".join(biz_details[:10]),
            "agencies": " | ".join(sorted(agencies)[:3]),
            "avg_rate": round(avg_rate, 2),
            "total_amt": total_amt,
            "recent_date": recent,
            "recent_date_kr": fmt_date_with_dow(recent),
            "bonus_notes": "; ".join(bonus_notes),
        })

    rows.sort(key=lambda r: -r["final_score"])

    # CSV 저장
    cols = ["final_score", "kw_score", "bonus", "bonus_notes",
            "corp", "ceo", "tel", "bizrno", "sido", "adrs",
            "biz_count", "matched_kw", "biz_titles", "biz_details", "agencies",
            "avg_rate", "total_amt", "recent_date", "recent_date_kr"]
    with open(OUT_MATCH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in cols})

    print(f"[match] {OUT_MATCH} ({len(rows)} 회사)")

    # 4) 요일별 분포 (윈도우 전체 풀 vs 매칭 vs 낙찰업체 정보 완비)
    pool_by_date = defaultdict(int)
    match_by_date = defaultdict(int)
    complete_by_date = defaultdict(int)
    matched_corp_by_date = defaultdict(set)
    for it in items:
        d = pick_event_date(it)
        if d:
            pool_by_date[d] += 1
    for it in matched_items:
        d = pick_event_date(it)
        if d:
            match_by_date[d] += 1
            corp = (it.get("fnlSucsfCorpNm") or "").strip()
            bizrno = (it.get("fnlSucsfCorpBizrno") or "").strip()
            if corp and bizrno:
                complete_by_date[d] += 1
                matched_corp_by_date[d].add(corp)

    with open(OUT_DOW, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["date", "weekday", "label", "pool_count", "match_count",
                    "complete_count", "unique_corps"])
        for d in WINDOW_DATES:
            dt = datetime.strptime(d, "%Y%m%d")
            dow = WEEKDAY_KR[dt.weekday()]
            holiday = HOLIDAYS_2026_05.get(d)
            label = fmt_date_with_dow(d)
            w.writerow([
                f"{d[:4]}-{d[4:6]}-{d[6:]}",
                dow + (f"/{holiday}" if holiday else ""),
                label,
                pool_by_date.get(d, 0),
                match_by_date.get(d, 0),
                complete_by_date.get(d, 0),
                len(matched_corp_by_date.get(d, set())),
            ])
    print(f"[dow]   {OUT_DOW} ({len(WINDOW_DATES)} days)")

    print(f"\n=== 요일별 분포 ===")
    print(f"{'날짜(요일)':<22} {'풀':>5} {'매칭':>5} {'완비':>5} {'고유사':>6}")
    for d in WINDOW_DATES:
        print(f"{fmt_date_with_dow(d):<22} {pool_by_date.get(d, 0):>5} "
              f"{match_by_date.get(d, 0):>5} {complete_by_date.get(d, 0):>5} "
              f"{len(matched_corp_by_date.get(d, set())):>6}")

    print(f"\n=== Top 15 영업 후보 ===")
    print(f"{'점수':>5} {'사업':>3} {'회사명':<25} {'대표':<8} {'전화':<14} {'시도':<6} 매칭사업명(첫건)")
    for r in rows[:15]:
        print(f"{r['final_score']:>5.2f} {r['biz_count']:>3} {r['corp'][:24]:<25} {r['ceo'][:7]:<8} {r['tel'][:13]:<14} {r['sido'][:5]:<6} {r['biz_titles'].split(' || ')[0][:50]}")


if __name__ == "__main__":
    main()
