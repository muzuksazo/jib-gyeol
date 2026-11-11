# ② 매물 목록 — 담당: 팀원 A
# 주소: /listings   ·   필터 예: /listings?region=마포구&deal_type=전세&max_price=30000&rooms=2
# 지역 · 거래 유형 · 최대 가격 · 방 수 필터 (보기만 하니까 GET = 엽서)

from flask import Blueprint, render_template, request

import db

bp = Blueprint("listings", __name__)

DEAL_TYPES = ("전세", "월세", "매매")


def _to_int(value):
    """주소창 값은 글자라서 숫자로 바꿔요. 숫자가 아니거나 음수면 '조건 없음'으로 봐요."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


@bp.route("/listings")
def index():
    region = request.args.get("region", "").strip()
    deal_type = request.args.get("deal_type", "")
    if deal_type not in DEAL_TYPES:          # 목록에 없는 값은 무시
        deal_type = ""
    max_price = _to_int(request.args.get("max_price"))
    rooms = _to_int(request.args.get("rooms"))

    items = db.get_listings_filtered(region, deal_type, max_price, rooms)
    filters = {"region": region, "deal_type": deal_type, "max_price": max_price, "rooms": rooms}
    return render_template(
        "listings.html",
        items=items,
        filters=filters,
        regions=db.get_regions(),
        deal_types=DEAL_TYPES,
        filtered=any(v not in ("", None) for v in filters.values()),
    )
