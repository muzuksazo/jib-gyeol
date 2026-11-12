# app.py — 뼈대 (담당: PO)
# 이 파일은 5개 페이지를 한데 모으는 곳이에요. 각자 페이지는 pages/ 안의 자기 파일만 고쳐요.
# 켜기: flask --app app run --debug   ·   배포(Render): gunicorn app:app

import os

from flask import Flask, render_template

try:                                   # .env 파일에서 SECRET_KEY 읽기 (python-dotenv)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:                    # 아직 설치 안 했어도 내 컴퓨터에선 켜지게
    pass

import db
from pages.ask import bp as ask_bp
from pages.detail import bp as detail_bp
from pages.home import bp as home_bp
from pages.listings import bp as listings_bp
from pages.request_form import bp as request_bp
from pages.wishlist import bp as wishlist_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")   # 세션 · flash 잠금 열쇠

db.init_db()   # 앱이 켜질 때 표 만들기 (Render 새 서버엔 DB 파일이 없어서 꼭 필요)

# 5개 페이지 등록 — 1인 1페이지
app.register_blueprint(home_bp)        # ① 홈            — 원님
app.register_blueprint(listings_bp)    # ② 매물 목록     — 팀원 A
app.register_blueprint(detail_bp)      # ③ 매물 상세+3D  — 여님
app.register_blueprint(request_bp)     # ④ 의뢰서        — 팀원 B
app.register_blueprint(wishlist_bp)    # ⑤ 찜·비교       — PO
app.register_blueprint(ask_bp)         # ⑥ 물어보기      — D22 RAG (rag.py · docs/ · index.json)


@app.errorhandler(404)                 # 없는 주소 · 없는 매물 → 친절한 404 화면 (디자인: 원님)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)                 # 서버 코드 에러 → 친절한 500 화면 (디자인: 원님)
def server_error(e):
    return render_template("500.html"), 500


if __name__ == "__main__":             # python app.py 로 켤 때만 (내 컴퓨터 전용)
    app.run(debug=True)
