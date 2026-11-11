# ④ 의뢰서 자동 테스트 — 담당: 팀원 B
# 돌리기: python -m pytest -q   (pip install pytest 필요)

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import db  # noqa: E402
from app import app  # noqa: E402

GOOD = {
    "nickname": "이사준비",
    "region": "마포구",
    "budget": "20000",
    "rooms": "2",
    "message": "햇빛이 잘 드는 집이면 좋겠어요.",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")   # 진짜 DB는 건드리지 않아요
    db.init_db()
    app.config["TESTING"] = True
    return app.test_client()


def text(res):
    return res.get_data(as_text=True)


def saved():
    con = db.get_db()
    try:
        return con.execute("SELECT * FROM requests ORDER BY id").fetchall()
    finally:
        con.close()


def test_form_opens(client):
    res = client.get("/request")
    assert res.status_code == 200
    assert "아직 의뢰서가 없어요" in text(res)


def test_saved_then_redirect_and_flash_once(client):
    res = client.post("/request", data=GOOD)
    assert res.status_code == 302                       # PRG: 저장했으면 다른 주소로
    first = text(client.get(res.headers["Location"]))
    assert "의뢰서가 접수됐어요" in first
    assert "이사준비" in first
    assert "의뢰서가 접수됐어요" not in text(client.get("/request"))   # F5 하면 안내는 사라짐
    assert len(saved()) == 1                            # 새로고침해도 늘어나지 않음


@pytest.mark.parametrize(
    "field, value",
    [
        ("nickname", ""),                    # 빈칸
        ("nickname", "   "),                 # 공백만
        ("nickname", "가" * 21),             # 길이 초과
        ("region", ""),
        ("region", "가" * 21),
        ("budget", "이억"),                  # 글자
        ("budget", "-5"),
        ("budget", "0"),
        ("budget", "2.5"),
        ("budget", "99999999"),
        ("rooms", ""),
        ("rooms", "0"),
        ("rooms", "6"),
        ("rooms", "999"),                    # F12로 값 바꾸기
        ("rooms", "둘"),
        ("message", ""),
        ("message", "가" * 201),
        ("message", "연락 주세요 010-1234-5678"),   # 전화번호는 받지 않아요
    ],
)
def test_bad_input_is_400_and_keeps_what_i_wrote(client, field, value):
    res = client.post("/request", data={**GOOD, field: value})
    assert res.status_code == 400
    assert len(saved()) == 0
    kept = "message" if field != "message" else "nickname"
    assert GOOD[kept] in text(res)           # 내가 쓴 다른 칸은 그대로


def test_missing_field_is_400_not_500(client):
    res = client.post("/request", data={"nickname": "이사준비"})   # F12로 칸을 통째로 지움
    assert res.status_code == 400
    assert len(saved()) == 0


def test_quotes_and_script_are_stored_as_plain_text(client):
    attack = "It's ok'); DROP TABLE requests; -- <script>alert(1)</script>"
    res = client.post("/request", data={**GOOD, "message": attack})
    assert res.status_code == 302
    assert saved()[0]["message"] == attack   # 글자 그대로 저장, 표는 그대로
    html = text(client.get("/request"))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html          # 화면에도 글자 그대로
