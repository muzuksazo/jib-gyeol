# jib-gyeol

> 집에 가기 전에, 집 안을 걸어 보세요.
> 조건을 남기면 코디가 추천하고, 추천받은 집을 3D(가우시안 스플래팅)로 둘러보는 가상 부동산 서비스

D21 Flask ② 팀 프로젝트 · 5인 팀

## 핵심 기능 (MVP)
1. 매물 목록 + 지역·가격 필터 (GET)
2. 매물 상세 + 3D 둘러보기 (가우시안 스플래팅 웹 뷰어)
3. 의뢰서 남기기 (POST · SQLite · 서버 검증)
4. 찜하기 · 비교 (세션)
5. 상태 화면 — 빈 목록 · 저장 성공 · 입력 오류 · 404

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

## 배포 (Render)
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`
- 환경 변수: `SECRET_KEY`

## 한계
- 무료 배포라 15분 쉬면 잠들어요 (첫 접속 1분쯤)
- 디스크가 임시라 재배포 · 재시작 때 SQLite 데이터가 초기화될 수 있어요
- 3D는 샘플 공간으로 시연해요
