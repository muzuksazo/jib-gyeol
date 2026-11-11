# ④ 의뢰서 남기기 — 담당: 팀원 B
# 주소: /request   ·   GET = 폼 보기, POST = 저장 (값을 바꾸는 일이니 POST = 봉투)
# 할 일 (오전 수업 그대로):
#   1. 서버 검증 — 닉네임 1~20자 · 예산 숫자 · 방 수 1~5 · 요청 1~200자
#      틀리면 저장 X, 400 상태 코드, 칸별 문구, 입력값은 남겨 두기
#   2. 저장 — db.get_db()로 requests 표에 INSERT, 값은 반드시 ? 자리에
#   3. PRG — 저장 성공 뒤 redirect + flash("의뢰서가 접수됐어요")
#   4. 공격 표 10개로 직접 확인 (<script>, DROP TABLE, F12로 값 바꾸기 ...)

from flask import Blueprint, flash, redirect, render_template, request, url_for

import db  # noqa: F401  (저장할 때 사용)

bp = Blueprint("request_form", __name__)


@bp.route("/request", methods=["GET", "POST"])
def form():
    if request.method == "POST":
        # TODO(팀원 B): 검증 → 저장 → redirect. 지금은 저장하지 않고 안내만 해요.
        flash("아직 저장 기능을 만드는 중이에요.")
        return redirect(url_for("request_form.form"))
    return render_template("request.html", values={}, errors={})
