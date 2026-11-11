# ② 매물 목록 — 담당: 팀원 A
# 주소: /listings   ·   필터 예: /listings?region=마포구&deal_type=전세
# 할 일: 지역 · 거래 유형 · 가격 필터 (보기만 하니까 GET)

from flask import Blueprint, render_template, request

import db

bp = Blueprint("listings", __name__)


@bp.route("/listings")
def index():
    region = request.args.get("region", "")   # 주소창 ?region= 값 (GET = 엽서)
    # TODO(팀원 A): region 등으로 걸러 주세요 (db.py 필터 함수는 여님에게 부탁하거나 여기서 직접). 지금은 전체를 보여 줘요.
    items = db.get_listings()
    return render_template("listings.html", items=items, region=region)
