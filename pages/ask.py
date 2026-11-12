# ⑥ 물어보기 — D22 RAG (문서에서 찾아 답하고, 없으면 모른다고 말해요)
# 화면: 모든 페이지 오른쪽 아래의 챗봇 창 (templates/_ask_widget.html · static/ask-widget.js)
# 주소: POST /ask/api  — 챗봇 창이 질문을 보내는 곳 (JSON)
#       GET · POST /ask — 스크립트가 꺼져 있을 때도 쓸 수 있는 같은 기능의 페이지
# 찾기 · 답하기는 rag.py 가 해요. 여기서는 질문 검사와 화면에 넘길 값만 준비해요.
# 문서(docs/)를 고쳤으면: python build_index.py

from flask import Blueprint, jsonify, render_template, request, url_for

import db

bp = Blueprint("ask", __name__)

MAX_LEN = 300                                   # 질문 최대 글자 수
EXAMPLES = (
    "마포구에 전세 매물 있어요?",
    "3D 둘러보기는 어떻게 움직여요?",
    "의뢰서에 전화번호를 써도 되나요?",
)
MAX_LINKS = 3                                   # 답 아래 '확인해보기'에 보여 줄 매물 수
DOC_LINKS = {                                   # 답에 쓴 문서 → 확인하러 갈 화면 (엔드포인트, 버튼 글자)
    "02_서비스_소개.md": ("listings.index", "매물 둘러보기"),
    "03_매물_찾기.md": ("listings.index", "매물 둘러보기"),
    "05_의뢰서_안내.md": ("request_form.form", "의뢰서 남기기"),
    "06_찜_비교.md": ("wishlist.index", "찜 · 비교 보기"),
    "07_매물_목록.md": ("listings.index", "매물 둘러보기"),
}
BUSY = "지금은 물어보기를 쓸 수 없어요. 잠시 후 다시 시도해 주세요."

_store = None                                   # index.json 은 처음 한 번만 불러와요


@bp.app_context_processor
def widget_values():
    """모든 페이지의 챗봇 창(base.html)에서 쓰는 값"""
    return {"ask_examples": EXAMPLES, "ask_max_len": MAX_LEN}


def ask_rag(question):
    """rag.py 로 답을 만들어요. 화면에 보여 줄 오류는 ValueError 로 바꿔요.
    rag 는 여기서 불러와요 — langchain 이 없거나 키가 없어도 다른 페이지는 켜지게."""
    global _store
    try:
        import rag
    except ImportError:
        raise ValueError("물어보기에 필요한 패키지가 없어요. pip install -r requirements.txt 를 실행해 주세요.") from None
    try:
        if _store is None:
            _store = rag.load_index()
        return rag.answer(question, store=_store)
    except rag.RagError as e:
        raise ValueError(str(e)) from None


def check(question):
    """질문 검사 — 틀리면 안내 문구, 맞으면 None (브라우저 maxlength 는 안내판, 진짜 검사는 여기)"""
    if not question:
        return "질문을 입력해 주세요."
    if len(question) > MAX_LEN:
        return f"질문은 {MAX_LEN}자까지 쓸 수 있어요. (지금 {len(question)}자)"
    return None


def make_links(result):
    """답 아래 '확인해보기' 버튼 — 출처 파일 이름 대신, 답을 직접 확인할 수 있는 화면으로 보내요.
    · 답에 매물 이름이 나오면 → 그 매물 상세(3D · 사진 둘러보기) 화면
    · 아니면 답에 쓴 문서에 맞는 화면 (3D → 3D 되는 매물, 의뢰서 → 의뢰서, 찜 → 찜 · 비교 …)"""
    if result["not_found"]:
        return []
    links = []

    def add(label, url):
        if url not in [link["url"] for link in links]:
            links.append({"label": label, "url": url})

    listings = db.get_listings()
    answer = "".join(result["answer"].split())                 # 띄어쓰기가 달라도 찾게
    named = [row for row in listings if "".join(row["title"].split()) in answer]
    for row in named[:MAX_LINKS]:
        add(f"{row['title']} 둘러보기", url_for("detail.show", listing_id=row["id"]))
    if len(named) > MAX_LINKS:
        add("매물 전체 보기", url_for("listings.index"))

    if not links:
        for file in result["sources"]:
            if file == "04_3D_둘러보기.md":
                tour = next((row for row in listings if row["splat_url"]), None)
                if tour:
                    add("3D로 둘러보기", url_for("detail.show", listing_id=tour["id"]))
            elif file in DOC_LINKS:
                endpoint, label = DOC_LINKS[file]
                add(label, url_for(endpoint))
    if not links:
        add("매물 둘러보기", url_for("listings.index"))
    return links[:MAX_LINKS + 1]


def get_answer(question):
    """(결과, 오류 문구) 중 하나를 돌려줘요. 예상 못 한 오류도 500 화면 대신 안내 한 줄로."""
    try:
        result = ask_rag(question)
    except ValueError as e:
        return None, str(e)
    except Exception:
        return None, BUSY
    for chunk in result["chunks"]:              # 점수 막대 길이 (0~100)
        chunk["width"] = max(0, min(100, round(chunk["score"] * 100)))
        chunk["score"] = f"{chunk['score']:.2f}"
    try:
        result["links"] = make_links(result)
    except Exception:                           # 버튼을 못 만들어도 답은 보여 줘요
        result["links"] = []
    return result, None


@bp.route("/ask/api", methods=["POST"])
def api():
    data = request.get_json(silent=True)
    question = str(data.get("question") or "").strip() if isinstance(data, dict) else ""
    notice = check(question)
    if notice:
        return jsonify(error=notice), 400
    result, error = get_answer(question)
    if error:
        return jsonify(error=error), 503
    return jsonify(answer=result["answer"], not_found=result["not_found"],
                   links=result["links"])


def show(status=200, **kw):
    base = dict(question="", notice=None, error=None, result=None, examples=EXAMPLES, max_len=MAX_LEN)
    base.update(kw)
    return render_template("ask.html", **base), status


@bp.route("/ask", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return show()

    question = request.form.get("question", "").strip()
    notice = check(question)
    if notice:
        return show(400, question=question if len(question) > MAX_LEN else "", notice=notice)
    result, error = get_answer(question)
    if error:
        return show(503, question=question, error=error)
    return show(question=question, result=result)
