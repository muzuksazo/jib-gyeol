"""rag.py — 물어보기(/ask)의 RAG 공통 함수 (D22 수업 d22-rag/rag.py 를 집결에 맞게 옮김)
흐름: ① 읽기 · 자르기 → ② 임베딩 · 저장(index.json) → ③ 찾기 → ④ 답하기
문서를 고쳤으면 꼭 다시: python build_index.py"""
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()                                   # .env 읽기 (GOOGLE_API_KEY)

DOCS_DIR = Path(__file__).parent / "docs"       # 답의 근거가 되는 문서 폴더
INDEX_PATH = Path(__file__).parent / "index.json"   # 조각 + 숫자(벡터) 저장 파일

CHUNK_SIZE = 400                                # 조각 하나의 최대 글자 수
CHUNK_OVERLAP = 40                              # 조각끼리 겹치는 글자 수 (10%)
TOP_K = 4                                       # 질문마다 찾아올 조각 수

BASE_URL_DEFAULT = "https://generativelanguage.googleapis.com/v1beta/openai/"
MAIN_MODEL = os.getenv("OPENAI_MODEL", "gemini-3.1-flash-lite")   # 메인: 제미나이
SUB_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")              # 서브: 내 컴퓨터의 Ollama (메인이 한도에 걸리면)
NOT_FOUND = "문서에서 찾지 못했어요"               # 자료에 답이 없을 때 쓰는 문장

SYSTEM_PROMPT = f"""너는 가상 부동산 서비스 '집결 ZIPGYEOL'의 안내 도우미야. 아래 규칙을 반드시 지켜.

1) [자료] 안에 있는 내용만으로 답해. 원래 알던 지식은 쓰지 마.
2) [자료]에 답이 없으면 이 문장만 써: "{NOT_FOUND}"
   (다른 말이나 출처를 덧붙이지 마.)
3) 숫자 · 가격 · 기간 · 조건은 [자료]에 적힌 그대로 써. 바꾸거나 어림하지 마.
4) 답을 했으면 마지막 줄에 실제로 답에 쓴 자료의 번호만 이렇게 써: "자료: 1"
   (여러 개면 "자료: 1, 3". 파일 이름은 쓰지 마 — 출처는 프로그램이 붙여.)
5) 계약 · 대출 · 세금 · 법률 조언, 시세 전망은 하지 마. [자료]에 없으면 2)번대로 답해.

답은 존댓말로 2~3문장 안에 짧게 써."""


class RagError(Exception):
    """화면에 한국어 한 줄로 보여 줄 오류"""


def _explain(what, e):
    """API 오류를 한국어 한 줄로 바꾼다 (키 값은 넣지 않는다)"""
    name = type(e).__name__
    if "RateLimit" in name:
        return f"{what}에 실패했어요 — 잠깐 사이에 너무 많이 불렀어요(사용량 한도). 1분쯤 뒤에 다시 해 주세요."
    return f"{what}에 실패했어요 ({name}). 키 · 모델 이름 · 네트워크를 확인해 주세요."


# ── ① 읽기 · 자르기 ─────────────────────────────────────────────

def load_docs(folder=DOCS_DIR):
    """docs 폴더의 .md 파일을 모두 읽어 Document 목록으로 돌려준다. 출처 = 파일 이름"""
    docs = []
    for path in sorted(Path(folder).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        docs.append(Document(page_content=text, metadata={"source": path.name}))
    return docs


def split_docs(docs, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
    """문서를 chunk_size 글자 이하의 조각으로 자른다. 조각마다 출처(파일 이름)가 따라간다"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n## ", "\n\n", "\n", " ", ""],   # 제목 → 빈 줄 → 줄 → 띄어쓰기 → 글자 순서로 자를 자리 찾기
    )
    return splitter.split_documents(docs)


# ── ② 임베딩 · 저장 ─────────────────────────────────────────────

def get_key():
    """.env 에서 키를 꺼낸다 (키 값은 화면에 찍지 않는다)"""
    key = os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RagError("API 키를 찾지 못했어요. .env 에 GOOGLE_API_KEY 를 넣어 주세요. (.env.example 참고)")
    return key


def get_embeddings():
    """임베딩 모델 연결 창구를 만든다"""
    return OpenAIEmbeddings(
        model=os.getenv("OPENAI_EMBED_MODEL", "gemini-embedding-001"),
        api_key=get_key(),
        base_url=os.getenv("OPENAI_BASE_URL", BASE_URL_DEFAULT),
        check_embedding_ctx_length=False,       # 글자를 그대로 보낸다 (제미나이 주소에서는 꼭 필요)
        chunk_size=50,                          # 한 번에 50조각씩 나눠 보낸다
    )


def build_index(chunks, path=INDEX_PATH):
    """조각을 숫자로 바꿔(임베딩) index.json 에 저장한다"""
    try:
        store = InMemoryVectorStore.from_documents(chunks, get_embeddings())
    except RagError:
        raise
    except Exception as e:
        raise RagError(_explain("임베딩", e)) from None
    store.dump(str(path))
    return store


def load_index(path=INDEX_PATH):
    """저장해 둔 index.json 을 불러온다"""
    if not Path(path).exists():
        raise RagError("index.json 이 없어요. 먼저 python build_index.py 를 실행해 주세요.")
    return InMemoryVectorStore.load(str(path), get_embeddings())


# ── ③ 찾기 ──────────────────────────────────────────────────────

def search(question, k=TOP_K, store=None):
    """질문과 가장 비슷한 조각 k개를 (조각, 점수) 목록으로 돌려준다. 점수는 코사인 유사도 — 클수록 비슷"""
    if store is None:
        store = load_index()
    try:
        return store.similarity_search_with_score(question, k=k)
    except Exception as e:
        raise RagError(_explain("검색", e)) from None


# ── ④ 답하기 ────────────────────────────────────────────────────

def build_messages(question, results):
    """찾아온 조각과 질문으로 모델에게 보낼 메시지(규칙 + 자료 + 질문)를 만든다"""
    parts = []
    for i, (chunk, _score) in enumerate(results, 1):
        parts.append(f"(자료 {i} · 파일: {chunk.metadata['source']})\n{chunk.page_content}")
    user_prompt = "[자료]\n" + "\n\n".join(parts) + f"\n\n[질문]\n{question}"
    return [("system", SYSTEM_PROMPT), ("human", user_prompt)]


def get_llm():
    """답을 만드는 모델 연결 창구를 만든다 (temperature 0 — 같은 질문엔 되도록 같은 답)"""
    return ChatOpenAI(
        model=MAIN_MODEL,
        api_key=get_key(),
        base_url=os.getenv("OPENAI_BASE_URL", BASE_URL_DEFAULT),
        temperature=0,
        max_retries=0,                          # 한도에 걸리면 기다리지 않고 바로 서브 모델로 넘어간다
    )


def get_sub_llm():
    """서브 모델 연결 창구 — 내 컴퓨터의 Ollama (배포 서버에는 없으니 내 컴퓨터에서만 동작)"""
    return ChatOpenAI(
        model=SUB_MODEL,
        api_key="ollama",                       # Ollama 는 키를 확인하지 않는다 (빈칸만 아니면 된다)
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        temperature=0,
        max_retries=0,
        timeout=60,
    )


def _should_fall_back(e):
    """메인 모델 오류가 '서브로 넘어갈 만한' 것인지 — 사용량 한도(429) · 서버 혼잡(5xx)"""
    name = type(e).__name__
    status = getattr(e, "status_code", None)
    return "RateLimit" in name or status == 429 or (isinstance(status, int) and status >= 500)


def call_model_info(messages):
    """메시지를 모델에 보내 (답 글자, 어떤 모델이 답했는지) 를 돌려준다
    메인(제미나이)이 한도 · 혼잡에 걸리면 서브(Ollama)로 넘어간다"""
    try:
        text = get_llm().invoke(messages).content.strip()
        return text, {"role": "메인", "model": MAIN_MODEL}
    except RagError:
        raise
    except Exception as e:
        if not _should_fall_back(e):
            raise RagError(_explain("답 만들기", e)) from None
    try:
        text = get_sub_llm().invoke(messages).content.strip()
    except Exception:
        raise RagError("지금은 질문이 많아 답하지 못했어요(사용량 한도). 1분쯤 뒤에 다시 물어봐 주세요.") from None
    return text, {"role": "서브", "model": SUB_MODEL}


def finish_answer(reply, results):
    """모델 답을 다듬는다 — 출처는 AI가 아니라 코드가 붙인다
    · '찾지 못했어요' 면 그 한 문장만 남긴다
    · 모델이 적은 '자료: 1, 3' 번호를 실제로 찾아온 조각의 파일 이름으로 바꾼다
    (답 글, 출처 파일 이름 목록, 답에 쓴 자료 번호 목록)을 돌려준다"""
    reply = reply.strip()
    if reply.startswith(NOT_FOUND):
        return NOT_FOUND, [], []                          # 뒤에 붙은 말 · 출처는 잘라낸다

    body, numbers = [], []
    for line in reply.splitlines():
        m = re.search(r"\(?\s*자료\s*[:：]\s*([\d,\s]+)\)?\s*$", line)   # 줄 끝의 '자료: 1, 3' (따로 한 줄이든, 문장 뒤든)
        if m:
            numbers += [int(n) for n in re.findall(r"\d+", m.group(1))]
            line = line[:m.start()].rstrip()                # 번호 표시는 떼어 내고 앞의 문장만 남긴다
        if line.strip().startswith(("출처", "[출처")):        # 모델이 직접 쓴 출처 줄은 버린다
            continue
        body.append(line)

    files, used = [], []
    for n in numbers:
        if 1 <= n <= len(results) and n not in used:        # 실제로 찾아온 자료 번호만 인정
            used.append(n)
            name = results[n - 1][0].metadata["source"]
            if name not in files:
                files.append(name)
    text = "\n".join(body).strip().replace("**", "")       # 굵게 표시(**)는 화면에 별표로 보이니 지운다
    return text, files, used


def answer(question, k=TOP_K, store=None):
    """검색 → 프롬프트 만들기 → 모델 부르기 → 출처 붙이기를 한 번에
    {"answer", "not_found", "sources", "chunks", "model"} 을 돌려준다"""
    results = search(question, k=k, store=store)                # ③ 찾기
    reply, info = call_model_info(build_messages(question, results))   # ④ 답하기 (한도면 서브 모델)
    text, files, used = finish_answer(reply, results)           # 출처는 코드가 붙인다
    return {
        "answer": text,
        "not_found": text == NOT_FOUND,
        "sources": files,
        "chunks": [
            {
                "rank": rank,
                "file": chunk.metadata["source"],
                "score": float(score),
                "used": rank in used,                       # 모델이 답에 썼다고 적은 조각
                "preview": " ".join(chunk.page_content.replace("#", " ").split())[:200],
            }
            for rank, (chunk, score) in enumerate(results, 1)
        ],
        "model": info,
    }
