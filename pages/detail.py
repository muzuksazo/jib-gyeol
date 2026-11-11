# ③ 매물 상세 + 3D 둘러보기 — 담당: 여님 (데이터셋)
# 주소: /listings/1, /listings/2 ...
# 할 일: 매물 정보 보여 주기 · 3D(가우시안 스플래팅) 뷰어 넣기 (templates/detail.html)

from flask import Blueprint, abort, render_template

import db

bp = Blueprint("detail", __name__)


@bp.route("/listings/<int:listing_id>")
def show(listing_id):
    listing = db.get_listing(listing_id)
    if listing is None:        # 없는 매물 번호 (예: /listings/999)
        abort(404)             # → "없어요" 404 화면 (화면 디자인은 원님의 404.html)
    return render_template("detail.html", listing=listing)
