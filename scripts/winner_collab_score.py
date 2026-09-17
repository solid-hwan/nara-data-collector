#!/usr/bin/env python3
"""
1주 낙찰 데이터(2026-05-02 ~ 2026-05-09) → Sion Lab 도메인 매칭(확장: RAG/LLM/벡터DB/데이터품질) +
하도급/협업 가능성 점수화 + 요일 표기.

입력: data/raw/data-go-mcp/search_successful_bids/full/*w7d20260502-0508_p*_full*.json
       data/raw/data-go-mcp/search_successful_bids/*d20260509_p*.json
출력: data/processed/winner_collab_score_20260509.csv
"""
import json
import csv
import os
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "winner_collab_score_20260509.csv"

# 윈도우 / 요일 표기
WINDOW_DATES = {"20260502", "20260503", "20260504", "20260505",
                "20260506", "20260507", "20260508", "20260509"}
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]
HOLIDAYS_2026_05 = {"20260505": "어린이날"}


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


def pick_event_date(item: dict) -> str:
    return normalize_yyyymmdd(item.get("fnlSucsfDate") or item.get("opengDate") or "")


# 도메인 키워드 확장: RAG/LLM/벡터DB/데이터품질 추가
DOMAIN_KEYWORDS = {
    "AI/데이터": [
        "인공지능", "AI ", " AI", "AI·", "AI기반", "AI 기반", "AI플랫폼", "AI 플랫폼",
        "머신러닝", "딥러닝", "데이터분석", "데이터 분석", "빅데이터",
        "데이터 구축", "데이터구축", "생성형", "지능형", "스마트팩토리", "예측 모델", "예측모델",
        "RAG", "검색증강", "Retrieval",                     # 신규
        "LLM", "대규모언어모델", "거대언어모델",            # 신규
        "벡터DB", "벡터 검색", "임베딩", "시맨틱 검색",     # 신규
    ],
    "OCR/문서": [
        "OCR", "문서자동화", "문서 자동화", "문서인식", "문서 인식", "RPA",
        "전자문서", "디지털화", "문서지능화",
        "데이터품질", "데이터 품질", "데이터정제", "데이터 정제",  # 신규
    ],
    "SI/시스템구축": [
        "시스템 구축", "시스템구축", "정보화", "플랫폼 구축", "플랫폼구축",
        "시스템 개발", "시스템개발", "시스템 고도화", "시스템고도화",
        "정보시스템", "ISP", "정보전략계획",
        "전산시스템", "전산 시스템", "유지보수", "유지 보수",
        "S/W 개발", "SW개발", "소프트웨어", "웹사이트", "홈페이지", "앱 개발",
    ],
    "Chatbot/CRM/ERP": [
        "챗봇", "chatbot", "CRM", "ERP", "고객관리", "전사자원", "콜봇",
    ],
}

# 대형 SI사 / 중견 IT사 (낙찰업체 분류용)
BIG_SI = [
    "삼성에스디에스", "삼성SDS", "엘지씨엔에스", "LGCNS", "LG CNS",
    "에스케이", "SK주식회사", "SK C&C", "현대오토에버",
    "포스코ICT", "포스코디엑스", "롯데정보통신", "신세계아이앤씨", "케이티", "KT ",
    "한화에스앤씨", "농심NDS", "코오롱베니트", "대우정보시스템",
    "비트컴퓨터", "더존비즈온", "쌍용정보통신",
]

UNIVERSITY_PATTERNS = ["산학협력단", "대학교", "대학 산학", "연구원", "연구재단", "진흥원"]


def load_all_records():
    """1주 윈도우(2026-05-02~2026-05-09) 낙찰 캐시 로드, 중복 제거.

    - full pool: 5/02~5/08 전수 페이징 159p
    - 5/09 일일 증분 (있으면)
    """
    seen = set()
    records = []
    patterns = [
        "data-go-mcp/search_successful_bids/full/*w7d20260502-0508_p*_full*.json",
        "data-go-mcp/search_successful_bids/*d20260509_p*.json",
    ]
    files = []
    for p in patterns:
        files.extend(sorted(RAW_DIR.glob(p)))
    print(f"[load] scanning {len(files)} files (1주 윈도우)")
    skipped_window = 0
    for f in files:
        try:
            with open(f, encoding="utf-8") as fp:
                d = json.load(fp)
            result = d.get("response", {}).get("result") or d.get("result", {})
            items = result.get("items", [])
            for it in items:
                # 윈도우 안전 필터 (개찰일/낙찰일 정규화 후 비교)
                date_field = pick_event_date(it)
                if date_field and date_field not in WINDOW_DATES:
                    skipped_window += 1
                    continue
                bid_no = it.get("bidNtceNo", "")
                ord_ = it.get("bidNtceOrd", "")
                rank = it.get("opengRank", "")
                key = (bid_no, ord_, rank, it.get("bidprcCorpBizrno", ""))
                if key in seen:
                    continue
                seen.add(key)
                records.append(it)
        except Exception as e:
            print(f"WARN {f.name}: {e}")
    print(f"[load] 윈도우 외 제외: {skipped_window}건")
    return records


def match_domain(name: str):
    """사업명에서 매칭된 도메인과 키워드 반환."""
    if not name:
        return None, []
    matched = []
    domain = None
    for d, kws in DOMAIN_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in name.lower() or kw in name:
                matched.append(kw.strip())
                if domain is None:
                    domain = d
                break
    return domain, matched


def is_big_si(corp_name: str) -> bool:
    if not corp_name:
        return False
    n = corp_name.replace(" ", "").upper()
    for s in BIG_SI:
        if s.replace(" ", "").upper() in n:
            return True
    return False


def is_university_or_research(corp_name: str) -> bool:
    if not corp_name:
        return False
    return any(p in corp_name for p in UNIVERSITY_PATTERNS)


def parse_amount(s) -> int:
    if not s:
        return 0
    try:
        return int(float(str(s).replace(",", "")))
    except Exception:
        return 0


def score_record(rec: dict, domain: str) -> tuple[int, list[str]]:
    """협업 점수 + 시그널 사유."""
    score = 0
    reasons = []

    # 최종 낙찰가 우선, 없으면 응찰가
    fnl = parse_amount(rec.get("fnlSucsfAmt"))
    bidprc = parse_amount(rec.get("bidprcAmt"))
    presm = parse_amount(rec.get("presmptPrce"))
    award_amt = fnl or bidprc or presm

    contract_type = rec.get("cntrctCnclsMthdNm", "")
    winner = rec.get("fnlSucsfCorpNm") or rec.get("bidprcCorpNm") or ""
    rank = rec.get("opengRank", "")

    # 계약방식
    if "협상" in contract_type:
        score += 3
        reasons.append("협상계약(+3)")
    elif "수의" in contract_type:
        score -= 1
        reasons.append("수의계약(-1)")

    # 낙찰가 규모
    if award_amt >= 2_000_000_000:
        score += 3
        reasons.append("20억+(+3)")
    elif award_amt >= 500_000_000:
        score += 2
        reasons.append("5억+(+2)")
    elif award_amt < 100_000_000:
        score -= 1
        reasons.append("1억미만(-1)")

    # 낙찰업체 유형
    if is_big_si(winner):
        score += 2
        reasons.append("대형SI(+2)")
    elif is_university_or_research(winner):
        score -= 3
        reasons.append("대학/연구기관(-3)")

    # 도메인 가중치
    if domain in ("OCR/문서", "AI/데이터"):
        score += 1
        reasons.append(f"{domain}우선(+1)")

    return score, reasons


def main():
    records = load_all_records()
    print(f"[load] 통합 낙찰 레코드: {len(records)}건 (중복제거 후)")

    # 도메인 매칭만 추출
    matched = []
    domain_counts = defaultdict(int)
    for r in records:
        name = r.get("bidNtceNm", "")
        d, kws = match_domain(name)
        if d:
            domain_counts[d] += 1
            score, reasons = score_record(r, d)
            matched.append({
                "domain": d,
                "matched_kw": "|".join(kws),
                "score": score,
                "reasons": "; ".join(reasons),
                "bid_no": r.get("bidNtceNo", ""),
                "bid_ord": r.get("bidNtceOrd", ""),
                "title": name,
                "ntce_inst": r.get("ntceInsttNm", ""),
                "dmnd_inst": r.get("dmndInsttNm", ""),
                "contract_type": r.get("cntrctCnclsMthdNm", ""),
                "winner_decision": r.get("bidwinrDcsnMthdNm", ""),
                "presm_amt": parse_amount(r.get("presmptPrce")),
                "bid_amt": parse_amount(r.get("bidprcAmt")),
                "final_amt": parse_amount(r.get("fnlSucsfAmt")),
                "bid_rate": r.get("bidprcRt", ""),
                "final_rate": r.get("fnlSucsfRt", ""),
                "openg_rank": r.get("opengRank", ""),
                "openg_date": r.get("opengDate", ""),
                "openg_date_kr": fmt_date_with_dow(r.get("opengDate", "")),
                "fnl_date_kr": fmt_date_with_dow(r.get("fnlSucsfDate", "")),
                "winner_corp": r.get("fnlSucsfCorpNm") or r.get("bidprcCorpNm", ""),
                "winner_ceo": r.get("fnlSucsfCorpCeoNm") or r.get("bidprcCorpCeoNm", ""),
                "winner_bizrno": r.get("fnlSucsfCorpBizrno") or r.get("bidprcCorpBizrno", ""),
                "winner_addr": r.get("fnlSucsfCorpAdrs", "").strip(),
                "winner_tel": r.get("fnlSucsfCorpContactTel", ""),
                "is_big_si": is_big_si(r.get("fnlSucsfCorpNm") or r.get("bidprcCorpNm", "")),
                "is_univ": is_university_or_research(r.get("fnlSucsfCorpNm") or r.get("bidprcCorpNm", "")),
            })

    # bidNtceNo 단위 dedupe — winner_corp 채워진 행 우선, 그다음 점수
    by_bid = {}
    for m in matched:
        k = (m["bid_no"], m["bid_ord"])
        prev = by_bid.get(k)
        # 우선순위: (낙찰자 있음, score) 튜플 비교
        cur_pri = (1 if m["winner_corp"] else 0, m["score"])
        prev_pri = (1 if prev and prev["winner_corp"] else 0, prev["score"]) if prev else (-1, -999)
        if cur_pri > prev_pri:
            by_bid[k] = m
    final = sorted(by_bid.values(), key=lambda x: -x["score"])

    print(f"[match] 도메인 매칭: {len(matched)}건 → 공고 단위 dedupe: {len(final)}건")
    for d, c in domain_counts.items():
        print(f"  - {d}: {c}건 (응찰 단위)")

    # CSV 저장
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as fp:
        cols = list(final[0].keys()) if final else []
        w = csv.DictWriter(fp, fieldnames=cols)
        w.writeheader()
        w.writerows(final)
    print(f"[save] {OUT} ({len(final)}건)")

    # Top 30 미리보기
    print("\n=== Top 30 (score 기준) ===")
    for i, m in enumerate(final[:30], 1):
        amt = m["final_amt"] or m["bid_amt"] or m["presm_amt"]
        print(f"{i:2}. [{m['score']:+d}] {m['domain']} | {m['title'][:50]} | {m['winner_corp'][:25]} | {amt/1e8:.2f}억 | {m['contract_type']}")


if __name__ == "__main__":
    main()
