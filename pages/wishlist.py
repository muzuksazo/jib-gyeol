# ⑤ 찜 · 비교 — 담당: PO
# 주소: /wishlist (내 찜 목록 + 비교 표)  ·  /wishlist/toggle/<번호> (찜 / 찜 취소, POST)
# 로그인 없이 "이 브라우저"의 찜을 세션에 기억해요. 시크릿 창에선 0개가 정상.
# 비교할 매물 고르기는 보기만 바꾸는 일이라 GET (?compare=1&compare=5)

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

import db

bp = Blueprint("wishlist", __name__)

MAX_COMPARE = 3   # 한 번에 나란히 비교할 매물 수


def _best_ids(rows, key, pick):
    """rows 중 key 값이 가장 좋은(pick=max/min) 매물 id들. 모두 같으면 강조하지 않아요."""
    values = [r[key] for r in rows if r[key] is not None]
    if len(values) < 2 or len(set(values)) == 1:
        return set()
    best = pick(values)
    return {r["id"] for r in rows if r[key] == best}


def compare_highlights(rows):
    """비교 표에서 칸마다 가장 좋은 매물을 표시해요 (넓은 면적 · 많은 방 · 낮은 가격)."""
    best = {
        "area_m2": _best_ids(rows, "area_m2", max),
        "rooms": _best_ids(rows, "rooms", max),
        "price": set(),
        "monthly_rent": set(),
    }
    deal_types = {r["deal_type"] for r in rows}
    same_deal = len(deal_types) == 1        # 전세 · 월세 · 매매가 섞이면 가격은 단순 비교 X
    if same_deal:
        best["price"] = _best_ids(rows, "price", min)
        if deal_types == {"월세"}:
            best["monthly_rent"] = _best_ids(rows, "monthly_rent", min)
    return best, same_deal


@bp.route("/wishlist")
def index():
    ids = session.get("wish", [])
    items = [row for row in db.get_listings() if row["id"] in ids]   # 지워진 매물은 자동으로 빠져요

    picked = request.args.getlist("compare", type=int)                # 비교할 매물 (없으면 앞의 3개)
    compare = [row for row in items if row["id"] in picked][:MAX_COMPARE] or items[:MAX_COMPARE]
    best, same_deal = compare_highlights(compare)

    return render_template(
        "wishlist.html",
        items=items,
        compare=compare,
        compare_ids=[row["id"] for row in compare],
        best=best,
        same_deal=same_deal,
        max_compare=MAX_COMPARE,
    )


@bp.route("/wishlist/toggle/<int:listing_id>", methods=["POST"])   # 값을 바꾸니까 POST
def toggle(listing_id):
    if db.get_listing(listing_id) is None:
        abort(404)
    ids = session.get("wish", [])
    if listing_id in ids:
        ids.remove(listing_id)
        flash("찜을 취소했어요.")
    else:
        ids.append(listing_id)
        flash("찜했어요. 찜 목록에서 비교해 보세요.")
    session["wish"] = ids
    return redirect(request.referrer or url_for("wishlist.index"))   # PRG
