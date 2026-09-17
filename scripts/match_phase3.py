# -*- coding: utf-8 -*-
"""Phase 3 매칭 파이프라인.

data/raw/ 의 MCP 응답을 정규화하여 Sion Lab 매칭 점수를 계산하고
data/processed/matches_phase3.csv 와 matches_phase3_top30.md 를 생성한다.
"""
import csv
import glob
import json
import os
import re
import sys
from collections import defaultdict

# 저장소 루트를 스크립트 위치에서 유도한다 (scripts/ 의 부모).
# 하드코딩하면 다른 사용자가 클론해서 실행할 수 없다.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = f"{ROOT}/data/raw"
OUT_DIR = f"{ROOT}/data/processed"

# 키워드 가중치 (정규식 — 대소문자 무시, 공백 변형 허용)
KEYWORDS = [
    ("OCR", 3.0, r"OCR"),
    ("문서인식", 2.5, r"문서\s*인식"),
    ("문서자동화", 2.5, r"문서\s*자동화"),
    ("AI", 2.0, r"\bAI\b"),
    ("인공지능", 2.0, r"인공지능"),
    ("데이터자동화", 2.0, r"데이터\s*자동화"),
    ("업무자동화", 2.0, r"업무\s*자동화"),
    ("RPA", 2.0, r"\bRPA\b"),
    ("API", 1.8, r"\bAPI\b"),
    ("데이터연계", 1.8, r"데이터\s*연계"),
    ("오픈API", 1.8, r"오픈\s*API"),
    ("ERP", 1.5, r"\bERP\b"),
    ("CRM", 1.5, r"\bCRM\b"),
    ("시스템구축", 1.5, r"시스템\s*구축"),
    ("산업안전", 1.5, r"산업\s*안전"),
    ("안전컨설팅", 1.5, r"안전\s*컨설팅"),
    ("안전관리", 1.5, r"안전\s*관리"),
    ("이미지인식", 1.2, r"이미지\s*인식"),
    ("컴퓨터비전", 1.2, r"컴퓨터\s*비전"),
]

DIGITAL_AGENCIES = [
    "NIA", "KISA", "한국지능정보사회진흥원", "한국인터넷진흥원",
    "우정사업본부", "교육청", "국세청", "조달청",
    "한국전자통신연구원", "ETRI", "한국정보화진흥원",
]

# source_kind 우선순위 (높을수록 우선)
KIND_PRIO = {"award": 4, "recommend": 3, "announce": 2, "keyword": 1}


def score_record(title, agency, budget):
    """제목/기관/예산 기반 점수 계산. 매칭된 키워드 목록 동시 반환."""
    title = title or ""
    agency = agency or ""
    matched = []
    score = 0.0
    seen = set()
    for name, w, pat in KEYWORDS:
        if name in seen:
            continue
        if re.search(pat, title, re.IGNORECASE):
            score += w
            matched.append(name)
            seen.add(name)
    # 기관 보너스
    for a in DIGITAL_AGENCIES:
        if a and a in agency:
            score += 1.0
            matched.append(f"기관:{a}")
            break
    # 예산 보너스/페널티
    try:
        b = int(budget) if budget not in (None, "", "0") else 0
    except (TypeError, ValueError):
        b = 0
    if 50_000_000 <= b <= 500_000_000:
        score += 1.0
        matched.append("예산적정")
    elif b > 6_000_000_000:
        score -= 2.0
        matched.append("대형SI감점")
    return score, matched


def parse_int(v):
    if v is None:
        return None
    s = str(v).replace(",", "").strip()
    if not s or s in ("--", "-"):
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def extract_datago_items(payload):
    """data-go-mcp 응답에서 items 리스트 추출."""
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        return []
    # case 1: result.content[0].text 안에 JSON 문자열
    result = data.get("result") or {}
    content = result.get("content") if isinstance(result, dict) else None
    if isinstance(content, list) and content:
        text = content[0].get("text", "") if isinstance(content[0], dict) else ""
        try:
            inner = json.loads(text)
            if isinstance(inner, dict) and isinstance(inner.get("items"), list):
                return inner["items"]
        except (json.JSONDecodeError, TypeError):
            pass
    # case 2: result.sample (search_contracts old format)
    if isinstance(result, dict) and isinstance(result.get("sample"), list):
        return result["sample"]
    # case 3: data.items
    if isinstance(data.get("items"), list):
        return data["items"]
    return []


# nara-jangteo 마크다운 텍스트 추출 정규식
# 헤더 두 가지 형태 지원:
#   "## 1. 제목" / "## 1. 📋 [사전규격] 제목" (get_bids_by_keyword)
#   "### [BID-1] 제목" / "### [PRESPEC-1] 📋 [사전규격] 제목" (recommend_bids_for_dept)
RE_TITLE_A = re.compile(
    r"^##\s+(?:\d+\.\s+)?(?:📋\s*\[사전규격\]\s*)?(.+?)\s*$", re.MULTILINE
)
RE_TITLE_B = re.compile(
    r"^###\s+\[(?:BID|PRESPEC)-\d+\]\s+(?:📋\s*\[사전규격\]\s*)?(.+?)\s*$", re.MULTILINE
)
RE_BIDNO = re.compile(r"공고번호:\s*([A-Z0-9]+)")
RE_PRESPEC = re.compile(r"사전규격번호:\s*([A-Z0-9]+)")
RE_AGENCY = re.compile(r"(?:수요기관|발주기관):\s*([^\n]+?)\s*$", re.MULTILINE)
RE_BUDGET = re.compile(r"(?:예산|배정예산):\s*([\d,]+)\s*원")


def parse_nara_markdown(text):
    """나라장터 마크다운 응답을 (title, bid_no, agency, budget) tuple 리스트로 분해."""
    # 블록 분리: '## ' 헤더 단위
    blocks = re.split(r"\n(?=##\s)", text)
    out = []
    for block in blocks:
        if not block.strip().startswith("##"):
            continue
        m_title = RE_TITLE.search(block)
        m_bidno = RE_BIDNO.search(block) or RE_PRESPEC.search(block)
        m_ag = RE_AGENCY.search(block)
        m_bd = RE_BUDGET.search(block)
        if not (m_title and m_bidno):
            continue
        title = m_title.group(1).strip()
        bidno = m_bidno.group(1).strip()
        agency = m_ag.group(1).strip() if m_ag else ""
        budget = parse_int(m_bd.group(1)) if m_bd else None
        out.append((title, bidno, agency, budget))
    return out


def extract_nara_text(payload):
    """nara-jangteo 응답에서 마크다운 텍스트 추출."""
    data = payload.get("data") or {}
    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(result, dict):
        # 구버전: data가 직접 dict with summary
        if isinstance(data, dict) and isinstance(data.get("summary"), str):
            return data["summary"]
        return ""
    content = result.get("content")
    if isinstance(content, list) and content and isinstance(content[0], dict):
        return content[0].get("text", "") or ""
    sc = result.get("structuredContent")
    if isinstance(sc, dict) and isinstance(sc.get("result"), str):
        return sc["result"]
    return ""


def classify_source(meta, item=None):
    """source_kind 결정."""
    tool = meta.get("tool", "")
    if tool == "search_successful_bids" or tool == "search_contracts":
        return "award"
    if tool == "recommend_bids_for_dept":
        return "recommend"
    if tool == "search_bid_announcements":
        return "announce"
    if tool == "get_bids_by_keyword":
        return "keyword"
    if tool == "analyze_bid_detail":
        return "announce"
    return "keyword"


def main():
    files = sorted(glob.glob(os.path.join(RAW_DIR, "**", "*.json"), recursive=True))
    records = []  # 정규화된 모든 레코드
    nara_missing = 0  # 필드 추출 못한 nara 블록 수
    nara_total = 0

    for fp in files:
        fname = os.path.basename(fp)
        try:
            payload = json.load(open(fp, encoding="utf-8"))
        except Exception as e:
            print(f"[skip] {fname}: {e}", file=sys.stderr)
            continue
        # naver-cafe 등 비-MCP 소스는 list/기타 형태일 수 있음 — 매칭 대상 아니므로 skip
        if not isinstance(payload, dict):
            continue
        meta = payload.get("_meta", {}) or {}
        source = meta.get("source", "")
        tool = meta.get("tool", "")
        kind = classify_source(meta)

        if source.startswith("data-go-mcp") or "data-go-mcp" in fname:
            items = extract_datago_items(payload)
            for it in items:
                if not isinstance(it, dict):
                    continue
                bid_no = (it.get("bidNtceNo") or it.get("cntrctNo") or it.get("refNtceNo") or "").strip()
                title = (it.get("bidNtceNm") or it.get("cntrctNm") or "").strip()
                agency = (it.get("ntceInsttNm") or it.get("dmndInsttNm")
                          or it.get("cntrctInsttNm") or "").strip()
                dept = (it.get("ntceInsttOfclDeptNm") or it.get("dmndInsttOfclDeptNm") or "").strip()
                budget = parse_int(it.get("presmptPrce") or it.get("asignBdgtAmt")
                                   or it.get("cntrctAmt") or it.get("fnlSucsfAmt"))
                award_date = (it.get("fnlSucsfDate") or it.get("cntrctCnclsDate")
                              or it.get("opengDate") or "").strip()
                winner = (it.get("fnlSucsfCorpNm") or it.get("rprsntCorpNm")
                          or it.get("bidprcCorpNm") or "").strip()
                wname = (it.get("fnlSucsfCorpOfclNm") or "").strip()
                wtel = (it.get("fnlSucsfCorpContactTel") or "").strip()
                if not bid_no or not title:
                    continue
                # award kind 판정 미세조정: successful_bids는 sucsfYn=Y만 award, 아니면 announce
                rec_kind = kind
                if tool == "search_successful_bids":
                    if (it.get("sucsfYn") or "").upper() != "Y" or not winner:
                        rec_kind = "announce"
                records.append({
                    "bid_no": bid_no,
                    "title": title,
                    "agency": agency,
                    "dept": dept,
                    "budget": budget,
                    "award_date": award_date,
                    "winner_corp": winner,
                    "winner_name": wname,
                    "winner_tel": wtel,
                    "source_kind": rec_kind,
                    "source_file": fname,
                })
        else:
            # nara-jangteo 텍스트 파싱
            text = extract_nara_text(payload)
            if not text:
                continue
            # 두 헤더 패턴 모두 분리 — '\n##' 또는 '\n###'
            blocks = re.split(r"\n(?=#{2,3}\s)", text)
            for block in blocks:
                bs = block.strip()
                if not (bs.startswith("## ") or bs.startswith("### ")):
                    continue
                # recommend 스타일에서 메타 헤더(## Regular Bids ...) 무시:
                # 공고/사전규격 번호가 없으면 자동으로 missing 처리됨
                nara_total += 1
                m_title = RE_TITLE_B.search(block) or RE_TITLE_A.search(block)
                m_bidno = RE_BIDNO.search(block) or RE_PRESPEC.search(block)
                m_ag = RE_AGENCY.search(block)
                m_bd = RE_BUDGET.search(block)
                if not (m_title and m_bidno):
                    nara_missing += 1
                    continue
                title = m_title.group(1).strip()
                # 사전규격/이모지 제거
                title = re.sub(r"^[\U0001F300-\U0001FAFF☀-➿\s]+", "", title).strip()
                bid_no = m_bidno.group(1).strip()
                agency = m_ag.group(1).strip() if m_ag else ""
                budget = parse_int(m_bd.group(1)) if m_bd else None
                records.append({
                    "bid_no": bid_no,
                    "title": title,
                    "agency": agency,
                    "dept": "",
                    "budget": budget,
                    "award_date": "",
                    "winner_corp": "",
                    "winner_name": "",
                    "winner_tel": "",
                    "source_kind": kind,
                    "source_file": fname,
                })

    total_records = len(records)

    # 중복 제거 — bid_no 기준, source_kind 우선순위 유지
    by_bid = {}
    file_map = defaultdict(set)
    for r in records:
        bid = r["bid_no"]
        file_map[bid].add(r["source_file"])
        prev = by_bid.get(bid)
        if prev is None or KIND_PRIO[r["source_kind"]] > KIND_PRIO[prev["source_kind"]]:
            by_bid[bid] = r
        else:
            # 누락 필드 보완
            for k in ("agency", "dept", "budget", "award_date",
                      "winner_corp", "winner_name", "winner_tel"):
                if not prev.get(k) and r.get(k):
                    prev[k] = r[k]

    # 점수 계산
    rows = []
    for bid, r in by_bid.items():
        score, matched = score_record(r["title"], r["agency"], r["budget"])
        rows.append({
            "bid_no": bid,
            "title": r["title"],
            "agency": r["agency"],
            "dept": r["dept"],
            "budget_krw": r["budget"] if r["budget"] is not None else "",
            "award_date": r["award_date"],
            "winner_corp": r["winner_corp"],
            "winner_contact_name": r["winner_name"],
            "winner_contact_tel": r["winner_tel"],
            "source_kind": r["source_kind"],
            "source_files": ";".join(sorted(file_map[bid])),
            "matched_keywords": ",".join(matched),
            "match_score": round(score, 2),
        })

    rows.sort(key=lambda x: (-x["match_score"], x["bid_no"]))

    # CSV 출력
    os.makedirs(OUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUT_DIR, "matches_phase3.csv")
    cols = ["bid_no", "title", "agency", "dept", "budget_krw", "award_date",
            "winner_corp", "winner_contact_name", "winner_contact_tel",
            "source_kind", "source_files", "matched_keywords", "match_score"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # Top30 마크다운
    top = rows[:30]
    md_path = os.path.join(OUT_DIR, "matches_phase3_top30.md")
    KIND_KR = {"award": "낙찰", "announce": "공고", "keyword": "키워드", "recommend": "추천"}
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Sion Lab 매칭 Top 30\n\n")
        f.write(f"- 생성: {os.path.basename(__file__)} 자동생성\n")
        f.write(f"- 전체 정규화 레코드: {total_records}건 / 유니크 bid_no: {len(by_bid)}건\n")
        f.write(f"- 점수 > 0 매칭: {sum(1 for r in rows if r['match_score']>0)}건\n\n")
        f.write("| 순위 | 점수 | 사업명 | 발주기관 | 예산(억) | 낙찰업체 | 매칭키워드 | 종류 | bid_no |\n")
        f.write("|---:|---:|---|---|---:|---|---|---|---|\n")
        for i, r in enumerate(top, 1):
            b = r["budget_krw"]
            bil = f"{int(b)/1e8:.2f}" if isinstance(b, int) and b else "-"
            title = r["title"].replace("|", "\\|")[:80]
            agency = r["agency"].replace("|", "\\|")[:30]
            winner = (r["winner_corp"] or "-").replace("|", "\\|")[:30]
            kw = r["matched_keywords"][:80]
            kind_kr = KIND_KR.get(r["source_kind"], r["source_kind"])
            f.write(f"| {i} | {r['match_score']} | {title} | {agency} | {bil} | {winner} | {kw} | {kind_kr} | {r['bid_no']} |\n")

    # 보고
    pos = [r for r in rows if r["match_score"] > 0]
    scores = [r["match_score"] for r in top]
    by_kind_top = defaultdict(int)
    for r in top:
        by_kind_top[r["source_kind"]] += 1

    print("=== Phase 3 매칭 결과 ===")
    print(f"전체 정규화 레코드: {total_records}건")
    print(f"유니크 bid_no: {len(by_bid)}건")
    print(f"점수 > 0 매칭: {len(pos)}건")
    if scores:
        scores_sorted = sorted(scores)
        med = scores_sorted[len(scores_sorted)//2]
        print(f"Top30 점수 — 최대 {max(scores)}, 중앙값 {med}, 최소 {min(scores)}")
    print(f"Top30 종류 분포: {dict(by_kind_top)}")
    if nara_total:
        print(f"nara-jangteo 블록 {nara_total}개 중 필드 누락 {nara_missing}개 ({nara_missing/nara_total*100:.1f}%)")
    print(f"CSV: {csv_path}")
    print(f"Top30 MD: {md_path}")


if __name__ == "__main__":
    main()
