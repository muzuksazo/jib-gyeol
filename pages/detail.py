# ③ 매물 상세 + 3D 둘러보기 — 담당: 여님 (3D 데이터)
# DB 코드는 쓰지 않아요. 매물 정보는 이미 만들어 둔 db.get_listing()으로 읽어 오기만 해요.
# 주소: /listings/1, /listings/2 ...
# 할 일: 매물 정보 보여 주기 · 3D(가우시안 스플래팅) 뷰어 넣기 (templates/detail.html)

from flask import Blueprint, abort, render_template

import db

bp = Blueprint("detail", __name__)


def price_text(listing):
    """만원 단위 숫자를 읽기 쉬운 글로: 22000 → '2억 2,000만', 월세면 '1,000만 / 월 65만'."""
    def won(manwon):
        eok, rest = divmod(manwon, 10000)
        parts = ([f"{eok}억"] if eok else []) + ([f"{rest:,}만"] if rest or not eok else [])
        return " ".join(parts)

    text = won(listing["price"])
    if listing["monthly_rent"]:
        text += f" / 월 {listing['monthly_rent']:,}만"
    return text


@bp.route("/listings/<int:listing_id>")
def show(listing_id):
    listing = db.get_listing(listing_id)
    if listing is None:        # 없는 매물 번호 (예: /listings/999)
        abort(404)             # → "없어요" 404 화면 (화면 디자인은 원님의 404.html)
    return render_template("detail.html", listing=listing, price_text=price_text(listing))
