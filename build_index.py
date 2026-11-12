"""build_index.py — 물어보기용 index.json 만들기
실행: python build_index.py
하는 일: ① data/listings.csv → docs/07_매물_목록.md 다시 쓰기 → ② docs/ 읽기 · 자르기 → ③ 임베딩 → index.json 저장
문서(docs/)나 매물(data/listings.csv)을 고쳤으면 꼭 다시 실행해요. 안 하면 옛날 조각으로 찾아요."""
import csv
import sys
from pathlib import Path

import rag

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")    # 윈도우 터미널에서 한글 깨짐 방지

BASE = Path(__file__).parent
CSV_PATH = BASE / "data" / "listings.csv"
LISTINGS_DOC = rag.DOCS_DIR / "07_매물_목록.md"


def won(manwon):
    """만원 단위 숫자를 읽는 말로: 22000 → '2억 2,000만원'"""
    eok, rest = divmod(int(manwon), 10000)
    parts = ([f"{eok}억"] if eok else []) + ([f"{rest:,}만"] if rest or not eok else [])
    return " ".join(parts) + "원"


def price_text(row):
    if row["deal_type"] == "월세":
        return f"월세 보증금 {won(row['price'])} · 월 {int(row['monthly_rent']):,}만원"
    return f"{row['deal_type']} {won(row['price'])}"


def write_listings_doc():
    """매물 CSV 를 사람이 읽는 문서로 바꾼다 (손으로 고치지 않는다 — CSV 를 고치고 다시 실행)"""
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    lines = [
        "# 집결 매물 목록",
        "",
        f"집결에 등록된 매물은 모두 {len(rows)}개예요. 가격은 만원 단위를 읽기 쉽게 바꿔 적었어요.",
        "이 문서는 data/listings.csv 에서 자동으로 만들어요.",
        "",
    ]
    for row in rows:
        has_3d = "3D 둘러보기 가능" if row["splat_url"] else "사진 둘러보기 가능 (3D 스캔은 준비 중)"
        lines += [
            f"## 매물 {row['id']}번 · {row['title']}",
            f"- 지역: {row['region']} · 거래: {price_text(row)}",
            f"- 방 {row['rooms']}개 · 면적 {row['area_m2']}㎡ · {row['floor']}층 · {has_3d}",
            f"- 소개: {row['description']}",
            f"- 주소: /listings/{row['id']}",
            "",
        ]

    for title, key in (("지역별 매물", "region"), ("거래 유형별 매물", "deal_type")):
        lines.append(f"## {title}")
        groups = {}
        for row in rows:
            groups.setdefault(row[key], []).append(row)
        for name, items in groups.items():
            names = ", ".join(f"{r['title']}({price_text(r)})" for r in items)
            lines.append(f"- {name} 매물 {len(items)}개: {names}")
        lines.append("")

    with_3d = [r["title"] for r in rows if r["splat_url"]]
    lines += [
        "## 3D 둘러보기가 되는 매물",
        f"- 지금 3D로 둘러볼 수 있는 매물은 {len(with_3d)}개예요: {', '.join(with_3d) or '없음'}",
        "- 나머지 매물은 3D 스캔이 아직 없어서 '사진 둘러보기'(매물 사진을 드래그해서 둘러보기)로 보여 드려요.",
        "",
    ]
    LISTINGS_DOC.write_text("\n".join(lines), encoding="utf-8")
    return len(rows)


def main():
    count = write_listings_doc()
    print(f"① 매물 {count}개 → {LISTINGS_DOC.name}")

    docs = rag.load_docs()
    chunks = rag.split_docs(docs)
    print(f"② 문서 {len(docs)}개 → 조각 {len(chunks)}개")

    try:
        rag.build_index(chunks)
    except rag.RagError as e:
        sys.exit(f"✗ {e}")
    print(f"③ {rag.INDEX_PATH.name} 저장 완료")


if __name__ == "__main__":
    main()
