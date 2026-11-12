"""make_depth.py — 사진 둘러보기용 깊이 지도 만들기
실행: python tools/make_depth.py            (없는 것만 만든다)
      python tools/make_depth.py --all      (전부 다시 만든다)
하는 일: data/listings.csv 에서 3D 스캔이 없는 매물의 사진을 받아 → 깊이 추정 모델로 '가까움 · 멂'을 계산 →
        static/listings/depth/번호.jpg (회색 그림 — 밝을수록 가깝다) 로 저장한다.
매물 사진을 바꿨으면 그 번호의 깊이 지도도 다시 만들어야 한다 (사진과 안 맞으면 화면이 일그러져 보인다).
필요한 것(배포 서버에는 필요 없다 — 내 컴퓨터에서 한 번만): pip install torch transformers pillow"""
import csv
import io
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageFilter

BASE = Path(__file__).resolve().parent.parent
CSV_PATH = BASE / "data" / "listings.csv"
OUT_DIR = BASE / "static" / "listings" / "depth"
MODEL = "depth-anything/Depth-Anything-V2-Small-hf"
WIDTH = 512                                     # 깊이 지도 가로 크기 — 부드러운 그림이라 작아도 된다


def open_photo(url):
    """사진을 연다 — /static/... 은 폴더에서, http 는 인터넷에서"""
    if url.startswith("/static/"):
        return Image.open(BASE / url.lstrip("/")).convert("RGB")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return Image.open(io.BytesIO(response.read())).convert("RGB")


def main():
    redo = "--all" in sys.argv
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("image_url") and not r.get("splat_url")]
    todo = [r for r in rows if redo or not (OUT_DIR / f"{r['id']}.jpg").exists()]
    if not todo:
        print("만들 것이 없어요. (전부 다시 만들려면 --all)")
        return

    from transformers import pipeline           # 무거워서 필요할 때만 불러온다
    estimate = pipeline("depth-estimation", model=MODEL)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for row in todo:
        photo = open_photo(row["image_url"])
        depth = estimate(photo)["depth"].convert("L")          # 밝을수록 가깝다
        low, high = depth.getextrema()
        if high > low:                                          # 가장 먼 곳 0 ~ 가장 가까운 곳 255 로 펴기
            depth = depth.point(lambda v: round((v - low) * 255 / (high - low)))
        height = round(WIDTH * photo.height / photo.width)
        depth = depth.resize((WIDTH, height), Image.LANCZOS).filter(ImageFilter.GaussianBlur(3))   # 경계를 부드럽게 (찢어져 보이지 않게)
        path = OUT_DIR / f"{row['id']}.jpg"
        depth.save(path, quality=82)
        print(f"{row['id']:>3}  {row['title']}  →  {path.relative_to(BASE)}  ({path.stat().st_size // 1024}KB)")


if __name__ == "__main__":
    main()
