# ① 홈 — 담당: 원님 (디자인 · 배포)
# 주소: /
# 할 일: 브랜드 소개 · 대표 매물 몇 개 · 목록으로 가는 검색창

from flask import Blueprint, render_template

import db

bp = Blueprint("home", __name__)


@bp.route("/")
def index():
    featured = db.get_listings()[:3]   # TODO(원님): 대표 매물 고르는 기준 정하기
    return render_template("home.html", featured=featured)
