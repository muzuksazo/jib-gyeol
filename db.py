# db.py — 데이터베이스 (담당: 팀원 A = 매물 표 listings · 팀원 B = 의뢰서 표 requests)
# SQLite는 DB 전체가 파일 하나(jibgyeol.db)예요. 이 파일은 깃에 올리지 않아요(.gitignore).
# 사용자 값은 절대 문장에 이어 붙이지 말고 반드시 ? 자리에 넣어요.

import csv
import os
import sqlite3
import tempfile
from pathlib import Path

BASE = Path(__file__).parent
# Vercel 서버는 프로젝트 폴더에 파일을 쓸 수 없어서(읽기 전용) 임시 폴더에 DB를 만들어요.
# 임시 폴더는 서버가 새로 뜰 때마다 비워져서, 매물은 CSV로 다시 채워지고 의뢰서는 초기화돼요.
DB_PATH = (Path(tempfile.gettempdir()) if os.environ.get("VERCEL") else BASE) / "jibgyeol.db"
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
                -- CHECK = DB가 한 번 더 막는 규칙. 서버 검증(validate.py)을 건너뛴 값이 와도 저장되지 않아요.
                nickname   TEXT NOT NULL    CHECK (length(nickname) BETWEEN 1 AND 20),
                region     TEXT NOT NULL    CHECK (length(region) BETWEEN 1 AND 20),
                budget     INTEGER NOT NULL CHECK (typeof(budget) = 'integer' AND budget BETWEEN 1 AND 1000000),  -- 만원
                rooms      INTEGER NOT NULL CHECK (typeof(rooms) = 'integer' AND rooms BETWEEN 1 AND 5),
                message    TEXT NOT NULL    CHECK (length(message) BETWEEN 1 AND 200),
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
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


def get_regions():
    """매물이 있는 지역 목록 (② 목록 필터의 지역 선택칸)."""
    con = get_db()
    try:
        return [r[0] for r in con.execute("SELECT DISTINCT region FROM listings ORDER BY region")]
    finally:
        con.close()


def get_listings_filtered(region="", deal_type="", max_price=None, min_rooms=None):
    """② 목록 필터. 빈 값은 '조건 없음'으로 보고 건너뛰어요.
    사용자 값은 문장에 이어 붙이지 않고 전부 ? 자리에 넣어요 (SQL 인젝션 방지).
    CSV를 고친 뒤엔 jibgyeol.db 파일을 지우고 다시 켜야 새 데이터가 들어가요."""
    sql = "SELECT * FROM listings WHERE 1=1"
    params = []
    if region:
        sql += " AND region = ?"
        params.append(region)
    if deal_type:
        sql += " AND deal_type = ?"
        params.append(deal_type)
    if max_price is not None:                  # 보증금 · 매매가 기준 (만원)
        sql += " AND price <= ?"
        params.append(max_price)
    if min_rooms is not None:
        sql += " AND rooms >= ?"
        params.append(min_rooms)
    sql += " ORDER BY id"
    con = get_db()
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()
