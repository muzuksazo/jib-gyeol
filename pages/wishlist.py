# ⑤ 찜 · 비교 — 담당: PO
# 주소: /wishlist (내 찜 목록)  ·  /wishlist/toggle/<번호> (찜 / 찜 취소, POST)
# 로그인 없이 "이 브라우저"의 찜을 세션에 기억해요. 시크릿 창에선 0개가 정상.

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

import db

bp = Blueprint("wishlist", __name__)


@bp.route("/wishlist")
def index():
    ids = session.get("wish", [])
    items = [row for row in db.get_listings() if row["id"] in ids]
    # TODO(PO): 찜한 매물 2~3개 나란히 비교하는 표
    return render_template("wishlist.html", items=items)


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
