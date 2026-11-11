# validate.py — ④ 의뢰서 서버 검증 (담당: 팀원 B)
# 브라우저 검사(required · maxlength)는 안내판이고, 진짜 문지기는 여기예요.
# F12로 required 를 지우거나 값을 바꿔 보내도 여기서 막아요.

import re

FIELDS = ("nickname", "region", "budget", "rooms", "message")

BUDGET_MAX = 1_000_000   # 만원 단위. 100억
PHONE = re.compile(r"01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}")   # 전화번호 모양


def validate_request(form):
    """의뢰서를 검사해요. (사용자가 쓴 값, 칸별 에러 문구) 를 돌려줘요.

    에러가 하나도 없으면 errors 는 빈 딕셔너리예요.
    values 는 앞뒤 공백만 뗀 글자 그대로라서, 틀렸을 때 폼에 다시 채워 줄 수 있어요.
    """
    values = {name: (form.get(name) or "").strip() for name in FIELDS}
    errors = {}

    nickname = values["nickname"]
    if not 1 <= len(nickname) <= 20:
        errors["nickname"] = "닉네임은 1~20자로 써 주세요."
    elif PHONE.search(nickname):
        errors["nickname"] = "전화번호는 받지 않아요. 닉네임만 써 주세요."

    if not 1 <= len(values["region"]) <= 20:
        errors["region"] = "희망 지역은 1~20자로 써 주세요. (예: 마포구)"

    budget = values["budget"]
    if not (budget.isascii() and budget.isdigit()):
        errors["budget"] = "예산은 숫자만 써 주세요. (예: 20000)"
    elif len(budget) > 7 or not 1 <= int(budget) <= BUDGET_MAX:
        errors["budget"] = "예산은 1만원부터 1,000,000만원(100억)까지 쓸 수 있어요."

    if values["rooms"] not in ("1", "2", "3", "4", "5"):
        errors["rooms"] = "방 수는 1~5 중에서 골라 주세요."

    message = values["message"]
    if not 1 <= len(message) <= 200:
        errors["message"] = f"요청 내용은 1~200자로 써 주세요. (지금 {len(message)}자)"
    elif PHONE.search(message):
        errors["message"] = "전화번호는 받지 않아요. 지우고 다시 남겨 주세요."

    return values, errors
