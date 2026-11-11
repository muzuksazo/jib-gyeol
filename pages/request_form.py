# ④ 의뢰서 남기기 — 담당: 팀원 B
# 주소: /request   ·   GET = 폼 보기, POST = 저장 (값을 바꾸는 일이니 POST = 봉투)
#   1. 서버 검증 (validate.py) — 닉네임 1~20자 · 지역 1~20자 · 예산 숫자 · 방 수 1~5 · 요청 1~200자
#      틀리면 저장 X, 400 상태 코드, 칸별 문구, 입력값은 남겨 두기
#   2. 저장 — db.get_db()로 requests 표에 INSERT, 값은 반드시 ? 자리에
#   3. PRG — 저장 성공 뒤 redirect + flash("의뢰서가 접수됐어요")

from datetime import datetime, timedelta, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for

import db
from validate import validate_request

bp = Blueprint("request_form", __name__)

KST = timezone(timedelta(hours=9))   # Render 서버는 시간이 달라서 한국 시간으로 직접 적어요


def save_request(values):
    con = db.get_db()
    try:
        with con:   # 잘 끝나면 알아서 commit
            con.execute(
                "INSERT INTO requests (nickname, region, budget, rooms, message, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    values["nickname"],
                    values["region"],
                    int(values["budget"]),
                    int(values["rooms"]),
                    values["message"],
                    datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
                ),
            )
    finally:
        con.close()


def recent_requests(limit=5):
    con = db.get_db()
    try:
        return con.execute(
            "SELECT * FROM requests ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    finally:
        con.close()


@bp.route("/request", methods=["GET", "POST"])
def form():
    if request.method == "POST":
        values, errors = validate_request(request.form)
        if errors:
            # 실패하면 redirect 하지 않아요. 쓴 값을 그대로 둔 채 400 으로 같은 화면을 다시 보여 줘요.
            return render_template(
                "request.html", values=values, errors=errors, recent=recent_requests()
            ), 400

        save_request(values)
        flash("의뢰서가 접수됐어요")
        return redirect(url_for("request_form.form"))   # PRG — 새로고침해도 두 번 저장되지 않아요

    return render_template("request.html", values={}, errors={}, recent=recent_requests())
