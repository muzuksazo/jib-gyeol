# db.py — 데이터베이스 (담당: 여님)
# SQLite는 DB 전체가 파일 하나(jibgyeol.db)예요. 이 파일은 깃에 올리지 않아요(.gitignore).
# 사용자 값은 절대 문장에 이어 붙이지 말고 반드시 ? 자리에 넣어요.

import csv
import sqlite3
from pathlib import Path

BASE = Path(__file__).parent
DB_PATH = BASE / "jibgyeol.db"
CSV_PATH = BASE / "data" / "listings.csv"

INT_COLS = ("id", "price", "monthly_rent", "rooms", "floor")
FLOAT_COLS = ("area_m2",)


def get_db():
    """DB 연결 하나를 열어 줘요. row["title"]처럼 칸 이름으로 꺼낼 수 있어요."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    """표가 없으면 만들고, 매물 표가 비어 있으면 CSV에서 채워요."""
    con = get_db()
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id           INTEGER PRIMARY KEY,
                title        TEXT NOT NULL,
                region       TEXT NOT NULL,
                deal_type    TEXT NOT NULL,      -- 전세 / 월세 / 매매
                price        INTEGER NOT NULL,   -- 보증금 또는 매매가 (만원)
                monthly_rent INTEGER,            -- 월세 (만원, 전세·매매는 비움)
                rooms        INTEGER,
                area_m2      REAL,
                floor        INTEGER,
                description  TEXT,
                image_url    TEXT,
                splat_url    TEXT                -- 3D(가우시안 스플래팅) 파일 주소
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS requests (   -- ④ 의뢰서 (팀원 B가 칸을 바꿔도 돼요)
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                nickname   TEXT NOT NULL,
                region     TEXT NOT NULL,
                budget     INTEGER NOT NULL,
                rooms      INTEGER NOT NULL,
                message    TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        empty = con.execute("SELECT COUNT(*) FROM listings").fetchone()[0] == 0
        if empty and CSV_PATH.exists():
            _load_csv(con)
        con.commit()
    finally:
        con.close()


def _load_csv(con):
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            for col in INT_COLS:
                row[col] = int(row[col]) if row.get(col) else None
            for col in FLOAT_COLS:
                row[col] = float(row[col]) if row.get(col) else None
            con.execute(
                """INSERT INTO listings (id, title, region, deal_type, price, monthly_rent,
                   rooms, area_m2, floor, description, image_url, splat_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["id"], row["title"], row["region"], row["deal_type"], row["price"],
                 row["monthly_rent"], row["rooms"], row["area_m2"], row["floor"],
                 row["description"], row["image_url"], row["splat_url"]),
            )


def get_listings():
    """매물 전체 (②목록 · ①홈 · ⑤찜에서 사용)."""
    con = get_db()
    try:
        return con.execute("SELECT * FROM listings ORDER BY id").fetchall()
    finally:
        con.close()


def get_listing(listing_id):
    """매물 하나. 없으면 None (③상세에서 404 처리)."""
    con = get_db()
    try:
        return con.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    finally:
        con.close()


# TODO(여님 ↔ 팀원 A): ② 목록 필터용 함수 — 팀원 A가 필요한 조건을 말하면 여님이 만들어요 — 예) get_listings_filtered(region, deal_type, max_price)
#   값은 반드시 ? 자리에. CSV를 고친 뒤엔 jibgyeol.db 파일을 지우고 다시 켜야 새 데이터가 들어가요.
