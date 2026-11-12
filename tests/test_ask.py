# ⑥ 물어보기 자동 테스트 — 화면 흐름만 확인해요 (API 는 부르지 않아요 · 키 없이도 돌아가요)
# 돌리기: python -m pytest -q

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import db  # noqa: E402
from app import app  # noqa: E402
from pages import ask  # noqa: E402

FOUND = {
    "answer": "한 번에 최대 3개까지 비교할 수 있어요.",
    "not_found": False,
    "sources": ["06_찜_비교.md"],
    "chunks": [
        {"rank": 1, "file": "06_찜_비교.md", "score": 0.79, "used": True, "preview": "한 번에 최대 3개까지 비교해요"},
        {"rank": 2, "file": "01_FAQ.md", "score": 0.61, "used": False, "preview": "찜은 브라우저에만 기억돼요"},
    ],
    "model": {"role": "메인", "model": "test"},
}
NOT_FOUND = {**FOUND, "answer": "문서에서 찾지 못했어요", "not_found": True, "sources": [],
             "chunks": [{**c, "used": False} for c in FOUND["chunks"]]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")   # 진짜 DB는 건드리지 않아요
    db.init_db()
    app.config["TESTING"] = True
    return app.test_client()


def fake(result):
    """rag 대신 정해 둔 답을 돌려주는 가짜 (받은 질문을 기억해요)"""
    asked = []

    def ask_rag(question):
        asked.append(question)
        if isinstance(result, Exception):
            raise result
        return {**result, "chunks": [dict(c) for c in result["chunks"]]}

    ask_rag.asked = asked
    return ask_rag


def text(res):
    return res.get_data(as_text=True)


def test_폼_열기(client):
    res = client.get("/ask")
    assert res.status_code == 200
    assert "물어보기" in text(res)
    assert ask.EXAMPLES[0] in text(res)


def test_메뉴에_물어보기가_있다(client):
    assert 'href="/ask"' in text(client.get("/"))


def test_답과_출처_카드(client, monkeypatch):
    monkeypatch.setattr(ask, "ask_rag", fake(FOUND))
    res = client.post("/ask", data={"question": "  몇 개까지 비교해요?  "})
    body = text(res)
    assert res.status_code == 200
    assert ask.ask_rag.asked == ["몇 개까지 비교해요?"]      # 앞뒤 공백은 떼고 물어봐요
    assert FOUND["answer"] in body
    assert "06_찜_비교.md" in body and body.count("답에 사용") == 1   # 답에 쓴 조각에만 표시
    assert "점수 0.79" in body and 'data-ask-width="79"' in body


def test_찾지_못했어요_화면(client, monkeypatch):
    monkeypatch.setattr(ask, "ask_rag", fake(NOT_FOUND))
    body = text(client.post("/ask", data={"question": "중개 수수료는 얼마예요?"}))
    assert "문서에서 찾지 못했어요" in body
    assert "답에 사용" not in body                           # 출처를 지어내지 않아요
    assert "의뢰서로 조건 남기기" in body


@pytest.mark.parametrize("question", ["", "   ", "가" * 301])
def test_빈_질문_긴_질문은_묻지_않는다(client, monkeypatch, question):
    monkeypatch.setattr(ask, "ask_rag", fake(FOUND))
    res = client.post("/ask", data={"question": question})
    assert res.status_code == 400
    assert ask.ask_rag.asked == []                           # 모델을 부르지 않아요 (비용 X)


def test_오류는_안내_한_줄로(client, monkeypatch):
    monkeypatch.setattr(ask, "ask_rag", fake(ValueError("index.json 이 없어요.")))
    res = client.post("/ask", data={"question": "아무 질문"})
    assert res.status_code == 503
    assert "index.json 이 없어요." in text(res)
    assert "아무 질문" in text(res)                           # 쓴 질문은 남겨 둬요


def test_예상_못_한_오류도_500_화면이_아니다(client, monkeypatch):
    monkeypatch.setattr(ask, "ask_rag", fake(RuntimeError("boom")))
    res = client.post("/ask", data={"question": "아무 질문"})
    assert res.status_code == 503
    assert ask.BUSY in text(res) and "boom" not in text(res)


def test_질문은_글자_그대로_보인다(client, monkeypatch):
    monkeypatch.setattr(ask, "ask_rag", fake(FOUND))
    body = text(client.post("/ask", data={"question": "<script>alert(1)</script>"}))
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body


# ── 챗봇 창 (모든 페이지 오른쪽 아래 · POST /ask/api) ──

def test_모든_페이지에_챗봇_창이_있다(client):
    for path in ("/", "/listings", "/listings/1", "/request", "/wishlist", "/listings/999"):
        body = text(client.get(path))
        assert "data-askw-open" in body and 'data-api="/ask/api"' in body, path
    assert "data-askw" not in text(client.get("/ask"))        # /ask 페이지는 본문에 같은 기능이 있어요


def test_api_답과_출처(client, monkeypatch):
    monkeypatch.setattr(ask, "ask_rag", fake(FOUND))
    res = client.post("/ask/api", json={"question": "  몇 개까지 비교해요?  "})
    data = res.get_json()
    assert res.status_code == 200
    assert ask.ask_rag.asked == ["몇 개까지 비교해요?"]
    assert data["answer"] == FOUND["answer"]
    assert data["links"] == [{"label": "찜 · 비교 보기", "url": "/wishlist"}]   # 출처 대신 확인하러 갈 화면
    assert set(data) == {"answer", "not_found", "links"}       # 출처 파일 · 조각 · 모델 이름은 보내지 않아요


def test_api_찾지_못했어요(client, monkeypatch):
    monkeypatch.setattr(ask, "ask_rag", fake(NOT_FOUND))
    data = client.post("/ask/api", json={"question": "중개 수수료는 얼마예요?"}).get_json()
    assert data["not_found"] is True and data["links"] == []


@pytest.mark.parametrize("payload", [{}, {"question": ""}, {"question": "   "}, {"question": "가" * 301},
                                     {"question": None}, [], "글자"])
def test_api_잘못된_질문은_묻지_않는다(client, monkeypatch, payload):
    monkeypatch.setattr(ask, "ask_rag", fake(FOUND))
    res = client.post("/ask/api", json=payload)
    assert res.status_code == 400 and res.get_json()["error"]
    assert ask.ask_rag.asked == []


def test_api_오류는_안내_한_줄로(client, monkeypatch):
    monkeypatch.setattr(ask, "ask_rag", fake(RuntimeError("boom")))
    res = client.post("/ask/api", json={"question": "아무 질문"})
    assert res.status_code == 503 and res.get_json() == {"error": ask.BUSY}


def test_api는_GET으로_열리지_않는다(client):
    assert client.get("/ask/api").status_code == 405


# ── 확인해보기 (출처 대신 · 답을 직접 확인할 화면으로) ──

def links_for(client, monkeypatch, answer, sources):
    monkeypatch.setattr(ask, "ask_rag", fake({**FOUND, "answer": answer, "sources": sources}))
    return client.post("/ask/api", json={"question": "질문"}).get_json()["links"]


def test_답에_나온_매물은_그_매물로_간다(client, monkeypatch):
    links = links_for(client, monkeypatch, "가장 저렴한 매물은 봉천동 햇살 원룸으로, 월 40만원입니다.", ["07_매물_목록.md"])
    assert links == [{"label": "봉천동 햇살 원룸 둘러보기", "url": "/listings/10"}]


def test_매물이_많으면_3개와_전체_보기(client, monkeypatch):
    answer = "햇살 드는 망원동 투룸, 서울숲 근처 투룸 빌라, 신림동 대학가 투룸, 압구정 한강뷰 전세가 있습니다."
    links = links_for(client, monkeypatch, answer, ["07_매물_목록.md"])
    assert [link["url"] for link in links] == ["/listings/1", "/listings/5", "/listings/9", "/listings"]


def test_3D_답은_3D가_되는_매물로_간다(client, monkeypatch):
    links = links_for(client, monkeypatch, "드래그해서 둘러볼 수 있습니다.", ["04_3D_둘러보기.md"])
    assert links == [{"label": "3D로 둘러보기", "url": "/listings/1"}]


def test_문서에_맞는_화면이_없으면_매물_둘러보기(client, monkeypatch):
    links = links_for(client, monkeypatch, "집결은 무료입니다.", ["01_FAQ.md"])
    assert links == [{"label": "매물 둘러보기", "url": "/listings"}]


def test_물어보기_페이지도_확인해보기(client, monkeypatch):
    monkeypatch.setattr(ask, "ask_rag", fake(FOUND))
    body = text(client.post("/ask", data={"question": "몇 개까지 비교해요?"}))
    assert "확인해보기" in body and 'href="/wishlist"' in body


# ── 매물 상세: 3D 스캔이 없으면 사진으로 둘러보기 ──

def test_3D_스캔이_없는_매물은_사진_둘러보기(client):
    body = text(client.get("/listings/2"))
    assert "data-photo=" in body and "viewer/photo.js" in body
    assert "준비되지 않았어요" not in body and "viewer/viewer.js" not in body


def test_사진_둘러보기_매물마다_깊이_지도가_있다(client):
    import csv
    from pathlib import Path
    base = Path(__file__).parent.parent
    with open(base / "data" / "listings.csv", encoding="utf-8", newline="") as f:
        photo_only = [r["id"] for r in csv.DictReader(f) if r["image_url"] and not r["splat_url"]]
    assert photo_only
    for listing_id in photo_only:
        assert (base / "static" / "listings" / "depth" / f"{listing_id}.jpg").exists(), f"{listing_id}번 깊이 지도가 없어요 — python tools/make_depth.py"
    assert 'data-depth="/static/listings/depth/2.jpg"' in text(client.get("/listings/2"))


def test_3D_스캔이_있는_매물은_그대로(client):
    body = text(client.get("/listings/1"))
    assert "data-splat-url=" in body and "viewer/viewer.js" in body
    assert "data-photo=" not in body and "viewer/photo.js" not in body
