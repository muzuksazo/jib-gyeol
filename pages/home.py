# ① 홈 — 담당: 원님 (디자인)
# 주소: /
# 할 일: 브랜드 소개 · 대표 매물 몇 개 · 목록으로 가는 검색창

from flask import Blueprint, render_template

import db

bp = Blueprint("home", __name__)


@bp.route("/")
def index():
    featured = db.get_listings()[:3]   # TODO(원님): 대표 매물 고르는 기준 정하기
    # 검색창 자동 완성: 목록 필터가 지역 이름과 똑같아야 찾기 때문에 실제 지역 이름을 알려 줘요
    return render_template("home.html", featured=featured, regions=db.get_regions())
