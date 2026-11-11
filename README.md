# jib-gyeol

> 집에 가기 전에, 집 안을 걸어 보세요.
> 조건을 남기면 코디가 추천하고, 추천받은 집을 3D(가우시안 스플래팅)로 둘러보는 가상 부동산 서비스

D21 Flask ② 팀 프로젝트 · 5인 팀

## 역할 · 1인 1페이지
| 담당 | 역할 | 페이지 | 고칠 파일 |
|---|---|---|---|
| 원님 | 디자인 · 배포 | ① 홈 `/` | `pages/home.py` · `templates/home.html` · **공통** `base.html` `404.html` `500.html` `static/` |
| 팀원 A | 개발 | ② 매물 목록 `/listings` | `pages/listings.py` · `templates/listings.html` · **공통** `db.py`(매물 표) `data/listings.csv` |
| 여님 | 3D 데이터 | ③ 매물 상세 + 3D `/listings/<번호>` | `pages/detail.py` · `templates/detail.html` · `static/splats/` (DB 코드는 안 써요) |
| 팀원 B | 개발 | ④ 의뢰서 `/request` | `pages/request_form.py` · `templates/request.html` · `db.py`(의뢰서 표) |
| PO | PO · GitHub | ⑤ 찜 · 비교 `/wishlist` | `pages/wishlist.py` · `templates/wishlist.html` · `app.py` |

> 자기 파일만 고쳐요. 공통 파일은 주인에게 부탁해요. 할 일은 각 파일의 `TODO(이름)` 주석에 있어요.

## 매물 데이터 칸 (data/listings.csv)
`id, title, region, deal_type(전세/월세/매매), price(만원), monthly_rent(만원), rooms, area_m2, floor, description, image_url, splat_url`
CSV를 고친 뒤엔 `jibgyeol.db` 파일을 지우고 다시 켜야 새 데이터가 들어가요.

## 팀 작업 규칙
- 작업 전에 항상 `git pull origin main`
- 각자 브랜치에서 작업 → Pull Request → PO가 확인 후 Merge
- `main`에 직접 push 금지 (Render가 main을 배포)
- `.env` · `*.db` 는 올리지 않기
- 작업 기록: Claude Code에서 "기록담당 에이전트로 기록해 줘" → `작업로그.md`

## 실행 (내 컴퓨터)
```
pip install -r requirements.txt
flask --app app run --debug
```
→ http://127.0.0.1:5000 · 확인: `/listings/999` 는 404 화면, 찜은 시크릿 창에서 0개

## 배포 (Render)
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`
- 환경 변수: `SECRET_KEY`

## 한계
- 무료 배포라 15분 쉬면 잠들어요 (첫 접속 1분쯤)
- 디스크가 임시라 재배포 · 재시작 때 SQLite 데이터가 초기화될 수 있어요
- 3D는 샘플 공간으로 시연해요
