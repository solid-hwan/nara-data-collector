#!/usr/bin/env python3
"""요일별 콜 캘린더 자동 생성기 (CSV 입력 · 매칭점수순 균등배분).

기존 call_calendar.py(5/11 주차, 28사 인라인 하드코딩)를 대체하는 파이프라인 버전.
매주 winner_match 재실행 후 이 스크립트만 돌리면 요일별 콜 캘린더가 자동 갱신된다.

설계(사용자 확정 결정):
- 입력: data/processed/winners_match_agency_1w_{window}.csv (final_score 내림차순 정렬됨)
        = winner_match_0616.py 산출물. 최종낙찰자(fnlSucsfCorpNm+bizrno 존재)만 그룹화돼 있음.
- 요일 배분: **매칭점수 우선순 균등배분** — 고점수를 월·화 앞 요일에, 하루 N콜(기본 6).
- 후보 범위: 최종 낙찰자만 (입력 CSV가 이미 그 기준).
- 7항목 채움:
  ① 후보=corp ② 공고번호=biz_details에서 추출 ③ 금액=total_amt
  ④ 낙찰일=recent_date_kr ⑤ 관련링크=g2b URL 조립 ⑥ 협업포인트=build_why()
  ⑦ 장점/단점=build_pros_cons() ⑧ 전화문구=build_talks()
- 번호 보강: tel 빈값/마스킹 → 리스트 유지 + 사업자번호 조회 가이드.

출력:
- data/reports/call/{mon|tue|wed|thu|fri}-call-{날짜}.md
- data/reports/call/index.md
- data/processed/call_calendar_w{월요일}.csv  (pros/cons/link 컬럼 포함)

사용법:
  python3 scripts/call_calendar_auto.py \
      --match-csv data/processed/winners_match_agency_1w_20260610-0616.csv \
      --week-monday 2026-06-22 --per-day 6
"""
import argparse
import csv
import os
import re
from datetime import date, datetime, timedelta

# 저장소 루트를 스크립트 위치에서 유도한다 (scripts/ 의 부모).
# 하드코딩하면 다른 사용자가 클론해서 실행할 수 없다.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = f"{ROOT}/data/reports/call"
WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]
DAY_KEYS = ["mon", "tue", "wed", "thu", "fri"]
SLOTS = ["09:30", "10:30", "11:30", "14:00", "15:00", "16:00"]

# g2b 공고 링크 템플릿 (계약 API 응답 bidNtceUrl 포맷과 동일 — 실측 확인)
G2B_LINK = "https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo={bid_no}&bidPbancOrd=000"

# 대형 SI 키워드 (시온랩 단독 비현실 → 컨소시엄 서브 포지션)
BIG_SI_HINT = ["엘지씨엔에스", "엘지 씨엔에스", "삼성에스디에스", "에스케이", "포스코", "롯데정보",
               "현대오토에버", "한진정보", "신세계아이앤씨", "아이티센", "쌍용정보"]
UNIV_HINT = ["대학교", "산학협력단", "연구원", "연구소", "재단법인", "진흥원"]


def fmt_amount(amt):
    try:
        amt = int(amt)
    except (ValueError, TypeError):
        return str(amt)
    if amt >= 100_000_000:
        return f"{amt / 100_000_000:.2f}억"
    if amt >= 10_000:
        return f"{amt:,}원"
    return f"{amt:,}원"


def fmt_tel(tel):
    """숫자만 들어온 전화번호를 보기 좋게. 마스킹/빈값은 그대로 판정용으로 반환."""
    t = (tel or "").strip()
    if not t or t in ("-", "--"):
        return ""
    if "*" in t:  # 마스킹
        return t
    digits = re.sub(r"\D", "", t)
    if len(digits) == 10 and digits.startswith("02"):
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    if len(digits) == 9 and digits.startswith("02"):
        return f"{digits[:2]}-{digits[2:5]}-{digits[5:]}"
    return t


def tel_is_usable(tel):
    t = (tel or "").strip()
    return bool(t) and t not in ("-", "--") and "*" not in t


def parse_first_biz(biz_details):
    """biz_details 의 첫 사업 레코드 파싱.

    포맷: '{bid_no}|{title}|{date}|{agency}|{cntrct_status}|{cntrct_method}|{amount}|{rate} || ...'
    반환: dict(bid_no, title, date, agency, amount)
    """
    if not biz_details:
        return {}
    first = biz_details.split("||")[0].strip()
    parts = [p.strip() for p in first.split("|")]
    rec = {}
    if len(parts) >= 1:
        rec["bid_no"] = parts[0]
    if len(parts) >= 2:
        rec["title"] = parts[1]
    if len(parts) >= 3:
        rec["date"] = parts[2]
    if len(parts) >= 4:
        rec["agency"] = parts[3]
    if len(parts) >= 7:
        rec["amount"] = parts[6]
    return rec


def make_link(bid_no):
    if not bid_no or not re.match(r"^[A-Za-z0-9]+$", bid_no):
        return ""
    return G2B_LINK.format(bid_no=bid_no)


def tier_of(score):
    s = float(score)
    if s >= 4.0:
        return "A", "🔥"
    if s >= 3.0:
        return "B", "⭐"
    if s >= 2.0:
        return "C", "🟡"
    return "D", "🔹"


def is_big_si(corp):
    c = corp.replace(" ", "")
    return any(h.replace(" ", "") in c for h in BIG_SI_HINT)


def is_univ(corp, agency):
    blob = f"{corp} {agency}"
    return any(h in blob for h in UNIV_HINT)


def build_why(row, biz):
    """⑥ 협업포인트 — 도메인·금액·규모 기반 생성."""
    corp = row["corp"]
    kw = row.get("matched_kw", "")
    amt = biz.get("amount") or row.get("total_amt", "0")
    try:
        amt_i = int(amt)
    except (ValueError, TypeError):
        amt_i = 0
    biz_count = row.get("biz_count", "1")

    if is_big_si(corp):
        return (f"대형 SI 낙찰사({kw}). 시온랩은 RAG·OCR·문서자동화 모듈을 "
                f"컨소시엄 서브모듈/하도급으로 공급하는 포지션이 현실적. 단독 경쟁 아님.")
    if is_univ(corp, biz.get("agency", "")):
        return (f"대학·연구기관 라인({kw}). 직접 영업보다 산학협력단 협력기업 등록·"
                f"학습데이터/콘텐츠 공급 협업이 적합.")
    if 50_000_000 <= amt_i <= 500_000_000:
        return (f"적정규모({fmt_amount(amt_i)}) {kw} 낙찰사. 시온랩 RAG/OCR/데이터품질 "
                f"모듈을 본 사업 운영단계 또는 차기 발주에 결합 제안 가능. "
                f"{'사업 ' + biz_count + '건 활발사.' if biz_count not in ('', '1') else ''}")
    if amt_i > 500_000_000:
        return (f"{fmt_amount(amt_i)} 중대형 {kw} 사업. 하도급/컨소시엄 협력 라인. "
                f"시온랩은 문서자동화·데이터 정제 파트 분담 제안.")
    return (f"{kw} 낙찰사({fmt_amount(amt_i)}). 소규모지만 도메인 매칭. "
            f"시온랩 모듈 동반 응찰 또는 관계 형성 가치.")


def build_pros_cons(row, biz):
    """⑦ 시온랩이 했을 때의 장점/단점 — sionlab-profile 기준 규칙."""
    corp = row["corp"]
    amt = biz.get("amount") or row.get("total_amt", "0")
    try:
        amt_i = int(amt)
    except (ValueError, TypeError):
        amt_i = 0
    rate = row.get("avg_rate", "")
    cntrct = (biz.get("title", "") + " " + row.get("bonus_notes", ""))

    pros, cons = [], []

    # 장점
    if 50_000_000 <= amt_i <= 500_000_000:
        pros.append("적정 수주규모(5천만~5억) — 시온랩 단독 수행 가능")
    if "AI" in row.get("matched_kw", "") or "생성형" in row.get("matched_kw", ""):
        pros.append("AI/생성형 도메인 — RAG·LLM 모듈 즉시 결합")
    if "OCR" in row.get("matched_kw", "") or "문서" in row.get("matched_kw", ""):
        pros.append("문서·OCR 도메인 — S-Docs 핵심 차별화 직결")
    if is_big_si(corp):
        pros.append("대형 SI — 컨소시엄 서브모듈 공급처로 안정적 거래선 가능")
    if row.get("biz_count", "1") not in ("", "1"):
        pros.append(f"활발사(사업 {row.get('biz_count')}건) — 반복 협업 여지")
    if not pros:
        pros.append("도메인 키워드 매칭 — 관계 형성 시 차기 협업 가능")

    # 단점
    try:
        rate_f = float(re.sub(r"[^0-9.]", "", rate)) if rate else 0
    except ValueError:
        rate_f = 0
    if rate_f >= 99.5 or "수의" in cntrct:
        cons.append("수의·단독 성향(고투찰률) — 재하도급 여지 작음, 발주처 동시접촉 금지")
    if is_univ(corp, biz.get("agency", "")):
        cons.append("대학/연구기관 — 직접영업 불가, 산학협력단 경유 필요")
    if is_big_si(corp):
        cons.append("대형사 — 시온랩 단독 수주 비현실, 모듈 공급 포지션 한정")
    if amt_i and amt_i < 30_000_000:
        cons.append("소규모 사업 — 영업비용 대비 기대수익 낮음")
    if amt_i > 2_000_000_000:
        cons.append("초대형(20억+) — 자격·실적 요건 진입장벽")
    if not cons:
        cons.append("특이 리스크 낮음 — 표준 영업 절차 진행")

    return pros, cons


def build_talks(row, biz):
    """⑧ 3줄 전화문구."""
    corp = row["corp"]
    ceo = row.get("ceo", "").strip()
    title = biz.get("title", "낙찰 사업")
    bid_no = biz.get("bid_no", "")
    date_kr = row.get("recent_date_kr", "")
    honorific = f"{ceo} 대표님" if ceo else "담당자님"

    t1 = f"{honorific}, {date_kr} '{title[:30]}' 낙찰 진심으로 축하드립니다."
    if is_big_si(corp):
        t2 = ("시온랩은 RAG·OCR·문서자동화 모듈 전문으로, 본 사업의 일부 파트를 "
              "컨소시엄/하도급으로 분담할 수 있는지 여쭙고 싶습니다.")
    elif is_univ(corp, biz.get("agency", "")):
        t2 = ("시온랩은 학습데이터 정제·RAG 콘텐츠 모듈 전문으로, 산학협력단 "
              "협력기업 등록 또는 콘텐츠 공급 협업 가능성을 여쭙습니다.")
    else:
        t2 = ("시온랩은 RAG·OCR·데이터품질 모듈 전문으로, 본 사업 운영단계나 "
              "차기 발주에서 협력 여지를 여쭙고 싶습니다.")
    t3 = "이번 주 30분 미팅 또는 영업담당자 직통 연결을 부탁드립니다."
    return t1, t2, t3


def build_warn(row, biz):
    """금지/주의 + 번호 보강 가이드 (Phase 6)."""
    warns = []
    if not tel_is_usable(row.get("tel", "")):
        warns.append(f"대표전화 미확보/마스킹 — 사업자번호 {row.get('bizrno','')} "
                     f"NICE·홈페이지·잡코리아 조회로 보강 필요")
    rate = row.get("avg_rate", "")
    try:
        rate_f = float(re.sub(r"[^0-9.]", "", rate)) if rate else 0
    except ValueError:
        rate_f = 0
    if rate_f >= 99.5 or "수의" in biz.get("title", ""):
        warns.append("수의계약 성향 — 본 사업 발주처 동시 접촉 금지")
    else:
        warns.append("경쟁 낙찰 — 발주처 평가위원/사업담당 동시 접촉 절대 금지")
    if is_univ(row["corp"], biz.get("agency", "")):
        warns.append("대학/연구기관 — 산학협력단 경유, 직접 영업 부적합")
    return " · ".join(warns)


# 오매칭(노이즈) 필터: 사업명에 아래 키워드가 있으면서 시온랩 핵심 도메인 신호가
# 없으면 제외. 'AI교육거점센터' 같은 고유명사·'ON-AIR' 등이 AI로 오탐되는 케이스 차단.
NOISE_HINT = ["태양광", "전기공사", "토목", "건축공사", "조경", "방수", "포장공사",
              "상하수도", "콘서트", "ON-AIR", "온에어", "축제", "행사대행", "급식",
              "청소용역", "경비용역", "차량임차", "보험"]
# 시온랩 진짜 도메인 신호 (이게 있으면 노이즈 키워드가 있어도 살림)
CORE_SIGNAL = ["인공지능", "AI 기반", "AI를", "생성형", "LLM", "RAG", "OCR", "데이터",
               "빅데이터", "머신러닝", "딥러닝", "챗봇", "자동화", "시스템 구축",
               "플랫폼", "문서", "분석", "품질"]


def is_noise(title):
    """사업명이 시온랩과 무관한 오매칭인지 판정."""
    if not title:
        return False
    has_noise = any(h in title for h in NOISE_HINT)
    if not has_noise:
        return False
    # 노이즈 키워드가 있어도 핵심 도메인 신호가 뚜렷하면 살림
    # (단, 'AI'가 고유명사 일부인 경우 대비 — 공백/한글경계 신호만 인정)
    has_core = any(s in title for s in CORE_SIGNAL)
    return not has_core


def load_candidates(match_csv):
    rows = []
    dropped = []
    with open(match_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            title = r.get("biz_titles", "")
            if is_noise(title):
                dropped.append((r.get("corp", ""), title[:40]))
                continue
            rows.append(r)
    # 입력은 이미 final_score 내림차순. 안전하게 재정렬.
    rows.sort(key=lambda r: -float(r.get("final_score", 0)))
    if dropped:
        print(f"[filter] 노이즈 제외 {len(dropped)}사: " +
              "; ".join(f"{c}({t})" for c, t in dropped))
    return rows


def assign_days(cands, per_day):
    """매칭점수 우선순 균등배분: 상위 per_day개씩 월→화→… 슬라이스.
    5일(월~금) × per_day 상한. 초과분은 backup 으로 분리.
    """
    by_day = {k: [] for k in DAY_KEYS}
    cap = per_day * len(DAY_KEYS)
    active = cands[:cap]
    backup = cands[cap:]
    for i, c in enumerate(active):
        day_idx = i // per_day
        slot_idx = i % per_day
        c["_day"] = DAY_KEYS[day_idx]
        c["_slot"] = SLOTS[slot_idx % len(SLOTS)]
        by_day[DAY_KEYS[day_idx]].append(c)
    return by_day, backup


def enrich(c):
    """후보 dict에 파생 필드(biz/link/why/pros/cons/talks/warn) 부착."""
    biz = parse_first_biz(c.get("biz_details", ""))
    c["_biz"] = biz
    c["_bid_no"] = biz.get("bid_no", "")
    c["_link"] = make_link(biz.get("bid_no", ""))
    c["_amount"] = biz.get("amount") or c.get("total_amt", "0")
    c["_why"] = build_why(c, biz)
    c["_pros"], c["_cons"] = build_pros_cons(c, biz)
    c["_talks"] = build_talks(c, biz)
    c["_warn"] = build_warn(c, biz)
    tier, emoji = tier_of(c.get("final_score", 0))
    c["_tier"], c["_emoji"] = tier, emoji
    return c


def render_day_md(day_key, calls, date_str, window):
    lines = []
    lines.append(f"# 콜 캘린더 · {date_str} · {len(calls)}콜")
    lines.append("")
    lines.append(f"> **배분 기준**: 매칭점수(시온랩 적합도) 우선순 균등배분 — 고점수 우선 요일")
    lines.append(f"> **데이터 윈도우**: {window} (용역 낙찰, 최종낙찰자만)")
    lines.append(f"> **본 일자 배정**: {len(calls)}콜")
    lines.append("> **⚠️ 공통 금지**: 발주처 평가위원/사업담당 동시 접촉 금지. 낙찰사 영업라인만 컨택.")
    lines.append("")
    lines.append("---")
    lines.append("")

    for c in calls:
        score = float(c.get("final_score", 0))
        lines.append(f"## 🕘 {c['_slot']} — {c['corp']} ({c['_emoji']} Tier {c['_tier']} · score {score:.1f})")
        lines.append("")
        # ②공고번호 ③금액 ④낙찰일
        biz = c["_biz"]
        lines.append(f"**① 후보**: {c['corp']} (대표 {c.get('ceo','-')})")
        lines.append(f"**② 공고번호**: `{c['_bid_no'] or '다수/미상'}`  ·  **사업명**: {biz.get('title','-')}")
        lines.append(f"**③ 금액**: {fmt_amount(c['_amount'])}  ·  **④ 낙찰일**: {c.get('recent_date_kr','-')}")
        link = c["_link"]
        lines.append(f"**⑤ 관련 링크**: {link if link else '(공고번호 미상 — g2b 직접검색)'}")
        lines.append(f"- 발주기관: {biz.get('agency','-')}  ·  매칭 키워드: {c.get('matched_kw','-')}  ·  사업자 {c.get('bizrno','-')}")
        tel = fmt_tel(c.get("tel", ""))
        lines.append(f"- 📞 컨택: {tel if tel else '(미확보 — 아래 보강 가이드)'}  ·  소재지: {c.get('sido','-')}")
        lines.append("")
        lines.append(f"**⑥ 협업포인트**")
        lines.append(f"> {c['_why']}")
        lines.append("")
        lines.append(f"**⑦ 시온랩 관점 장점 / 단점**")
        for p in c["_pros"]:
            lines.append(f"- ✅ {p}")
        for n in c["_cons"]:
            lines.append(f"- ⚠️ {n}")
        lines.append("")
        lines.append("**⑧ 전화문구 (3줄)**")
        t1, t2, t3 = c["_talks"]
        lines.append(f"1. \"{t1}\"")
        lines.append(f"2. \"{t2}\"")
        lines.append(f"3. \"{t3}\"")
        lines.append("")
        lines.append(f"**🚫 금지/주의**: {c['_warn']}")
        lines.append("")
        lines.append("**📋 콜 결과** (콜 후 기록)")
        lines.append("- [ ] 통화 성공 / [ ] 부재 / [ ] 거절 / [ ] 후속 미팅 예약 (날짜: ___)")
        lines.append("- 메모:")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def render_index_md(by_day, backup, dates, window, today_str):
    lines = []
    mon = dates["mon"]
    fri = dates["fri"]
    total = sum(len(v) for v in by_day.values())
    lines.append(f"# 콜 캘린더 주간 인덱스 ({mon} 월 ~ {fri} 금)")
    lines.append("")
    lines.append(f"- **작성일**: {today_str} (KST)")
    lines.append(f"- **배분 기준**: 매칭점수(시온랩 적합도) 우선순 균등배분")
    lines.append(f"- **데이터 윈도우**: {window} (용역 낙찰, 최종낙찰자만)")
    lines.append(f"- **총 콜**: {total}콜 (5일 분산) + backup {len(backup)}사")
    lines.append("- **데이터 출처**: `winner_match_0616.py` → `winners_match_agency_1w_*.csv`")
    lines.append("")
    lines.append("## 📅 요일별 콜 분포")
    lines.append("")
    lines.append("| 요일 | 날짜 | 콜수 | 파일 |")
    lines.append("|---|---|---:|---|")
    for k in DAY_KEYS:
        fn = f"{k}-call-{dates[k].replace('-', '')}.md"
        lines.append(f"| {k.title()} | {dates[k]}({WEEKDAY_KR[DAY_KEYS.index(k)]}) | {len(by_day.get(k, []))} | [{fn}](./{fn}) |")
    lines.append("")
    lines.append("## 🎯 주간 최우선 Top 5 (매칭점수순)")
    lines.append("")
    allc = [c for v in by_day.values() for c in v]
    allc.sort(key=lambda c: -float(c.get("final_score", 0)))
    lines.append("| 순위 | 회사 | 점수 | 금액 | 콜 시점 |")
    lines.append("|---:|---|---:|---|---|")
    for i, c in enumerate(allc[:5], 1):
        lines.append(f"| {i} | **{c['corp']}** | {float(c['final_score']):.1f} | "
                     f"{fmt_amount(c['_amount'])} | {dates[c['_day']]} {c['_slot']} |")
    lines.append("")
    lines.append("## ⚠️ 주간 공통 금지사항")
    lines.append("")
    lines.append("1. **발주처 평가위원/사업담당 동시 접촉 절대 금지** — 낙찰사 영업라인만 컨택.")
    lines.append("2. **1분 내 동일사 3회 이상 콜 금지** — 부재 시 다른 시간대 1회 재시도.")
    lines.append("3. **점심(12:00~13:30) 콜 회피**.")
    lines.append("4. **수의계약 단독건은 발주처 동시 접촉 금지**.")
    lines.append("5. **전화 미확보사**: 사업자번호 NICE·홈페이지 조회 후 보강.")
    lines.append("")
    if backup:
        lines.append("## 🔁 Backup (요일 상한 초과분 — 취소 시 대타)")
        lines.append("")
        lines.append("| 회사 | 점수 | 금액 | 키워드 |")
        lines.append("|---|---:|---|---|")
        for c in backup[:15]:
            lines.append(f"| {c['corp']} | {float(c['final_score']):.1f} | "
                         f"{fmt_amount(c.get('total_amt','0'))} | {c.get('matched_kw','-')} |")
        lines.append("")
    lines.append("## 📁 산출 위치")
    lines.append("")
    lines.append(f"- 요일별 md: `data/reports/call/{{mon..fri}}-call-{mon.replace('-','')}*.md`")
    lines.append(f"- flat CSV: `data/processed/call_calendar_w{mon.replace('-','')}.csv`")
    lines.append("- 재현: `python3 scripts/call_calendar_auto.py --match-csv ... --week-monday ...`")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match-csv", required=True)
    ap.add_argument("--week-monday", required=True, help="콜 주차 월요일 YYYY-MM-DD")
    ap.add_argument("--per-day", type=int, default=6, help="요일당 콜 상한")
    ap.add_argument("--window", default="", help="데이터 윈도우 표기 (예: 2026-06-10~06-16)")
    ap.add_argument("--today", default="", help="작성일 표기 YYYY-MM-DD (기본: week-monday)")
    args = ap.parse_args()

    mon = datetime.strptime(args.week_monday, "%Y-%m-%d").date()
    dates = {k: (mon + timedelta(days=i)).isoformat() for i, k in enumerate(DAY_KEYS)}
    window = args.window or "(미지정)"
    today_str = args.today or args.week_monday

    # 주차별 하위 폴더로 출력 (2026-W{NN}). 평면 적재 금지 — README.md 규칙 준수.
    iso_year, iso_week, _ = mon.isocalendar()
    week_dir = os.path.join(OUT_DIR, f"{iso_year}-W{iso_week:02d}")

    cands = load_candidates(args.match_csv)
    for c in cands:
        enrich(c)
    by_day, backup = assign_days(cands, args.per_day)

    os.makedirs(week_dir, exist_ok=True)
    out_csv = f"{ROOT}/data/processed/call_calendar_w{mon.isoformat().replace('-','')}.csv"
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)

    # CSV (pros/cons/link 컬럼 포함)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["day", "date", "slot", "tier", "score", "corp", "ceo", "tel", "bizrno",
                    "bid_no", "bid_title", "amount", "win_date", "link", "matched_kw",
                    "why", "pros", "cons", "talk1", "talk2", "talk3", "warn",
                    "call_result_status", "call_result_memo"])
        for k in DAY_KEYS:
            for c in by_day[k]:
                t1, t2, t3 = c["_talks"]
                w.writerow([k, dates[k], c["_slot"], c["_tier"], c.get("final_score", ""),
                            c["corp"], c.get("ceo", ""), fmt_tel(c.get("tel", "")), c.get("bizrno", ""),
                            c["_bid_no"], c["_biz"].get("title", ""), c["_amount"], c.get("recent_date_kr", ""),
                            c["_link"], c.get("matched_kw", ""), c["_why"],
                            " / ".join(c["_pros"]), " / ".join(c["_cons"]),
                            t1, t2, t3, c["_warn"], "", ""])
    print(f"[csv] {out_csv} ({sum(len(v) for v in by_day.values())} rows)")

    # 요일별 md (주차 폴더 안에)
    for k in DAY_KEYS:
        fn = f"{k}-call-{dates[k].replace('-', '')}.md"
        path = f"{week_dir}/{fn}"
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_day_md(k, by_day[k], f"{dates[k]}({WEEKDAY_KR[DAY_KEYS.index(k)]})", window))
        print(f"[md ] {path} ({len(by_day[k])} 콜)")

    # index.md (주차 폴더 안에)
    with open(f"{week_dir}/index.md", "w", encoding="utf-8") as f:
        f.write(render_index_md(by_day, backup, dates, window, today_str))
    print(f"[md ] {week_dir}/index.md")
    print(f"  → 마스터 인덱스(README.md)에 {iso_year}-W{iso_week:02d} 행 추가 필요시 갱신")

    print()
    print("=== 요일별 콜 분포 (매칭점수순) ===")
    for k in DAY_KEYS:
        names = ", ".join(f"{c['corp'][:14]}({float(c['final_score']):.1f})" for c in by_day[k])
        print(f"  {k.upper()} {dates[k]}: {len(by_day[k])}콜 — {names}")
    print(f"\n총 {sum(len(v) for v in by_day.values())}콜 + backup {len(backup)}사")


if __name__ == "__main__":
    main()
