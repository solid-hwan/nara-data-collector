#!/usr/bin/env python3
"""낙찰 전수 풀 → 자체 키워드 검색 레이어 → 회사 단위 영업 리스트

입력:
  data/raw/data-go-mcp/search_successful_bids/full/*.json  (rows=999 전수 수집분)
  + 기존 data/raw/data-go-mcp/search_successful_bids/*w7d2026*.json (보강)

출력:
  data/processed/winners_pool_full.csv     (전체 풀, 낙찰업체 기재 행만)
  data/processed/winners_match_keyword.csv (키워드 매칭 회사 그룹, 영업 점수 정렬)
"""
import json, glob, csv, os, re
from collections import defaultdict

# 저장소 루트를 스크립트 위치에서 유도한다 (scripts/ 의 부모).
# 하드코딩하면 다른 사용자가 클론해서 실행할 수 없다.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_GLOBS = [
    f"{ROOT}/data/raw/data-go-mcp/search_successful_bids/full/*.json",
    f"{ROOT}/data/raw/data-go-mcp/search_successful_bids/*w7d2026*.json",
]
OUT_FULL = f"{ROOT}/data/processed/winners_pool_full.csv"
OUT_MATCH = f"{ROOT}/data/processed/winners_match_keyword.csv"

# 사용자 요청 키워드: AI / OCR / ERP / CRM / 자동화
# 가중치는 docs/sionlab-profile.md 기준
KEYWORD_GROUPS = [
    ("OCR",      3.0, [r"\bOCR\b", r"광학문자인식", r"문자\s*인식", r"문서\s*인식"]),
    ("문서자동화", 2.5, [r"문서\s*자동화", r"문서\s*디지털"]),
    ("AI",       2.5, [r"\bAI\b", r"인공지능", r"지능형", r"머신러닝", r"딥러닝", r"생성형\s*AI"]),
    ("자동화",    2.5, [r"RPA", r"업무\s*자동화", r"프로세스\s*자동화", r"데이터\s*자동화"]),
    ("ERP",      2.0, [r"\bERP\b"]),
    ("CRM",      2.0, [r"\bCRM\b"]),
    ("챗봇/NLP",  1.8, [r"챗봇", r"\bNLP\b", r"자연어"]),
    ("빅데이터",  1.5, [r"빅데이터", r"데이터\s*분석", r"데이터\s*플랫폼"]),
    ("API/연계",  1.5, [r"오픈API", r"\bAPI\b", r"데이터\s*연계", r"데이터\s*허브"]),
    ("컴퓨터비전", 1.2, [r"이미지\s*인식", r"컴퓨터\s*비전", r"영상\s*분석", r"객체\s*탐지"]),
    ("자동화_단독", 1.0, [r"자동화"]),  # 위에서 매칭 안 됐을 때 약한 가산
]
DIGITAL_AGENCIES = ["NIA", "한국지능정보사회진흥원", "KISA", "한국인터넷진흥원",
                    "조달청", "교육청", "국세청", "우정사업본부", "예금보험공사",
                    "한국연구재단", "한국교육학술정보원", "KERIS", "정보통신산업진흥원"]


def load_items():
    seen_files = set()
    all_items = []
    for g in RAW_GLOBS:
        for f in sorted(glob.glob(g)):
            if f in seen_files: continue
            seen_files.add(f)
            try:
                d = json.load(open(f))
            except Exception as e:
                print(f"  [skip] {f}: {e}")
                continue
            # 두 가지 포맷 모두 처리
            items = (
                d.get("result", {}).get("items")
                or d.get("data", {}).get("result", {}).get("structuredContent", {}).get("result", {}).get("items")
                or []
            )
            for it in items:
                it["_source_file"] = os.path.basename(f)
            all_items.extend(items)
    return all_items, len(seen_files)


def match_keywords(title):
    """제목에 매칭된 키워드 가중치 합 + 매칭 라벨 반환. 그룹 단위 한 번씩만 가산."""
    if not title:
        return 0.0, []
    score = 0.0
    matched_labels = []
    for label, weight, patterns in KEYWORD_GROUPS:
        for pat in patterns:
            if re.search(pat, title, re.IGNORECASE):
                # "자동화_단독"은 다른 자동화 그룹이 이미 매칭됐으면 가산하지 않음
                if label == "자동화_단독" and "자동화" in matched_labels:
                    break
                score += weight
                matched_labels.append(label)
                break  # 한 그룹에서 한 번만
    return score, matched_labels


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
    if not adrs:
        return ""
    m = re.match(r"\s*([가-힣]+(?:특별시|광역시|특별자치시|특별자치도|도|시))", adrs)
    return m.group(1) if m else (adrs[:6] if adrs else "")


def main(min_score=2.0):
    items, fcount = load_items()
    print(f"[load] {fcount} files / {len(items)} items 평탄화")

    # 중복 제거 (동일 bidNtceNo + 동일 corp): 같은 사업의 같은 회사 응찰자 중복 제거
    seen = set()
    dedup = []
    for it in items:
        key = (it.get("bidNtceNo", ""), it.get("fnlSucsfCorpNm", "") or it.get("bidprcCorpNm", ""))
        if key in seen: continue
        seen.add(key)
        dedup.append(it)
    print(f"[dedup] {len(dedup)} 유니크 (bidNo + corp)")

    # 낙찰업체 기재 + 키워드 매칭만
    matched_items = []
    keyword_only = []  # 매칭은 됐지만 낙찰자 미기재
    for it in dedup:
        title = it.get("bidNtceNm") or ""
        score, labels = match_keywords(title)
        if score < min_score:
            continue
        corp = (it.get("fnlSucsfCorpNm") or "").strip()
        it["_match_score"] = score
        it["_matched_labels"] = labels
        if corp:
            matched_items.append(it)
        else:
            keyword_only.append(it)

    print(f"[match] 키워드>= {min_score}: {len(matched_items)+len(keyword_only)}건")
    print(f"  └ 낙찰업체 기재: {len(matched_items)}건")
    print(f"  └ 낙찰업체 미기재: {len(keyword_only)}건 (수동 추적 필요)")

    # 1) 전체 풀(낙찰자 기재) CSV — 모든 낙찰자 (매칭 무관)
    full_cols = ["bidNtceNo", "bidNtceNm", "bsnsDivNm", "ntceInsttNm", "dmndInsttNm",
                 "cntrctCnclsMthdNm", "bidwinrDcsnMthdNm", "presmptPrce",
                 "fnlSucsfAmt", "fnlSucsfRt", "fnlSucsfDate",
                 "fnlSucsfCorpNm", "fnlSucsfCorpCeoNm", "fnlSucsfCorpBizrno",
                 "fnlSucsfCorpContactTel", "fnlSucsfCorpAdrs"]
    os.makedirs(os.path.dirname(OUT_FULL), exist_ok=True)
    with open(OUT_FULL, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(full_cols)
        for it in dedup:
            if (it.get("fnlSucsfCorpNm") or "").strip():
                w.writerow([it.get(c, "") for c in full_cols])
    print(f"[full] {OUT_FULL}")

    # 2) 회사 단위 그룹화 + 영업 점수 보정
    groups = defaultdict(list)
    for it in matched_items:
        key = (it.get("fnlSucsfCorpNm", "").strip(), it.get("fnlSucsfCorpBizrno", "").strip())
        groups[key].append(it)

    rows = []
    for (corp, bizrno), grp in groups.items():
        ceo = grp[0].get("fnlSucsfCorpCeoNm", "")
        tel = grp[0].get("fnlSucsfCorpContactTel", "")
        adrs = grp[0].get("fnlSucsfCorpAdrs", "")
        sido = get_sido(adrs)

        kw_score = sum(it["_match_score"] for it in grp)
        bonus = 0.0
        bonus_notes = []

        # 평균 투찰률
        rates = [parse_rate(it.get("fnlSucsfRt")) for it in grp]
        rates = [r for r in rates if r > 0]
        avg_rate = sum(rates) / len(rates) if rates else 0.0
        if 70 <= avg_rate <= 95:
            bonus += 1.0
            bonus_notes.append(f"경쟁시장({avg_rate:.1f}%)+1.0")
        elif avg_rate >= 99.5:
            bonus -= 0.5
            bonus_notes.append(f"단독·수의({avg_rate:.1f}%)-0.5")

        # 낙찰금액
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

        # 디지털 친화 발주처
        agencies = set()
        for it in grp:
            for k in ("ntceInsttNm", "dmndInsttNm"):
                v = it.get(k) or ""
                if v: agencies.add(v)
        if any(any(d in a for d in DIGITAL_AGENCIES) for a in agencies):
            bonus += 0.5
            bonus_notes.append("디지털친화기관+0.5")

        final_score = round(kw_score + bonus, 2)

        biz_titles = [it.get("bidNtceNm", "") for it in grp]
        all_labels = sorted(set(l for it in grp for l in it["_matched_labels"]))
        dates = [it.get("fnlSucsfDate", "") for it in grp if it.get("fnlSucsfDate")]
        recent = max(dates) if dates else ""

        rows.append({
            "final_score": final_score, "kw_score": round(kw_score, 2), "bonus": round(bonus, 2),
            "bonus_notes": "; ".join(bonus_notes),
            "corp": corp, "ceo": ceo, "tel": tel, "bizrno": bizrno, "sido": sido, "adrs": adrs,
            "biz_count": len(grp),
            "matched_labels": ",".join(all_labels),
            "biz_titles": " || ".join(biz_titles[:5]),
            "agencies": " | ".join(sorted(agencies)[:3]),
            "avg_rate": round(avg_rate, 2),
            "total_amt": total_amt,
            "recent_date": recent,
        })

    rows.sort(key=lambda r: -r["final_score"])

    cols = ["final_score", "kw_score", "bonus", "bonus_notes",
            "corp", "ceo", "tel", "bizrno", "sido", "adrs",
            "biz_count", "matched_labels", "biz_titles", "agencies",
            "avg_rate", "total_amt", "recent_date"]
    with open(OUT_MATCH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in cols})
    print(f"[match] {OUT_MATCH} ({len(rows)} 회사)")

    # 매칭됐지만 낙찰자 미기재 케이스 별도 출력 (참고용)
    if keyword_only:
        print(f"\n=== 키워드 매칭 사업 중 낙찰자 미기재 (참고) ===")
        seen_titles = set()
        for it in keyword_only:
            t = it.get("bidNtceNm", "")
            if t in seen_titles: continue
            seen_titles.add(t)
            print(f"  [{','.join(it['_matched_labels'])}] {it.get('bidNtceNo','')} {t[:80]}")

    # Top 영업 후보 출력
    print(f"\n=== Top 20 영업 후보 ===")
    print(f"{'점수':>5} {'사업':>3} {'회사명':<28} {'대표':<8} {'전화':<14} {'시도':<6} 매칭사업명(첫건)")
    for r in rows[:20]:
        print(f"{r['final_score']:>5.2f} {r['biz_count']:>3} {r['corp'][:27]:<28} {r['ceo'][:7]:<8} {r['tel'][:13]:<14} {r['sido'][:5]:<6} {r['biz_titles'].split(' || ')[0][:55]}")


if __name__ == "__main__":
    import sys
    min_score = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    main(min_score)
