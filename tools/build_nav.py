"""3D 스캔(.ply)에서 '걸어 다닐 수 있는 바닥' 지도를 만든다.

    python tools/build_nav.py <scene.ply> <장면 폴더>

장면 폴더에 세 파일을 쓴다.
  nav.png  — 흰색 = 걸을 수 있는 바닥 (한 칸 5cm)
  map.png  — 도면처럼 단순하게 그린 평면도 (미니맵용: 흰 바닥 · 진한 벽 · 연한 가구)
  nav.json — 범위 · 바닥 높이 · 눈높이 · 시작 위치와 방향
좌표는 뷰어 기준(스플랫을 X축으로 180도 돌린 뒤: X=x, Y=-y, Z=-z, 위가 +Y).
필요: numpy, pillow
"""
import json
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageFilter

CELL = 0.05          # 격자 한 칸 (m)
BODY = 0.18          # 사람 반경 — 벽·가구에서 이만큼 떨어진 곳만 걸을 수 있음 (m)
OBST_LOW, OBST_HIGH = 0.25, 1.7   # 바닥에서 이 높이 사이에 뭔가 있으면 장애물 (m)
EYE = 1.5            # 눈높이 (m)


def read_ply(path):
    f = open(path, 'rb')
    props, n = [], 0
    while True:
        line = f.readline().decode().strip()
        if line.startswith('element vertex'):
            n = int(line.split()[-1])
        elif line.startswith('property'):
            props.append(line.split()[1:])
        elif line == 'end_header':
            break
    kinds = {'float': '<f4', 'double': '<f8', 'uchar': 'u1', 'int': '<i4'}
    d = np.fromfile(f, dtype=np.dtype([(name, kinds[t]) for t, name in props]), count=n)
    opacity = 1 / (1 + np.exp(-d['opacity']))
    return d['x'], -d['y'], -d['z'], opacity


def dilate(mask, radius_cells):
    out = mask.copy()
    r = radius_cells
    for dz in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dz * dz > r * r or (dx == 0 and dz == 0):
                continue
            src = mask[max(0, -dz):mask.shape[0] - max(0, dz), max(0, -dx):mask.shape[1] - max(0, dx)]
            out[max(0, dz):max(0, dz) + src.shape[0], max(0, dx):max(0, dx) + src.shape[1]] |= src
    return out


def components(mask):
    label = np.zeros(mask.shape, 'i4')
    sizes = [0]
    for z, x in zip(*np.nonzero(mask)):
        if label[z, x]:
            continue
        k = len(sizes)
        label[z, x] = k
        q, size = deque([(z, x)]), 0
        while q:
            cz, cx = q.popleft()
            size += 1
            for nz, nx in ((cz + 1, cx), (cz - 1, cx), (cz, cx + 1), (cz, cx - 1)):
                if 0 <= nz < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[nz, nx] and not label[nz, nx]:
                    label[nz, nx] = k
                    q.append((nz, nx))
        sizes.append(size)
    return label, sizes


def main(ply, out_dir):
    X, Y, Z, op = read_ply(ply)
    solid = op > 0.5

    # 바닥 높이: 5cm 두께로 썰었을 때 '덮인 면적'이 넓은 가장 낮은 층.
    # (점 개수로 고르면 점이 촘촘한 가구 높이를 바닥으로 잘못 잡는다)
    vis = op > 0.3
    lo, hi = np.percentile(Y[vis], [0.5, 99.5])
    xr, zr = np.percentile(X[vis], [1, 99]), np.percentile(Z[vis], [1, 99])
    levels = np.arange(lo, lo + 1.5, 0.05)
    cover = []
    for y in levels:
        sel = vis & (Y >= y) & (Y < y + 0.05)
        g, _, _ = np.histogram2d(Z[sel], X[sel], bins=[int((zr[1] - zr[0]) / 0.1), int((xr[1] - xr[0]) / 0.1)], range=[zr, xr])
        cover.append(int((g > 0).sum()))
    first = next(i for i, c in enumerate(cover) if c >= 0.5 * max(cover))
    best = max(range(first, min(first + 4, len(cover))), key=lambda i: cover[i])
    floor = float(levels[best] + 0.025)
    ceil = float(hi)

    # 평면 범위: 바닥 근처 점들의 범위 (멀리 튄 점 제외)
    # 스캔 바닥은 두께·기울기가 있어 위아래로 넉넉히 본다
    near_floor = (op > 0.1) & (Y > floor - 0.2) & (Y < floor + 0.12)
    x0, x1 = np.percentile(X[near_floor], [0.2, 99.8])
    z0, z1 = np.percentile(Z[near_floor], [0.2, 99.8])
    pad = 0.5
    x0, x1, z0, z1 = x0 - pad, x1 + pad, z0 - pad, z1 + pad
    w, d = int(np.ceil((x1 - x0) / CELL)), int(np.ceil((z1 - z0) / CELL))

    def grid(sel, min_count):
        g, _, _ = np.histogram2d(Z[sel], X[sel], bins=[d, w], range=[[z0, z0 + d * CELL], [x0, x0 + w * CELL]])
        return g >= min_count

    # 바닥의 작은 구멍 메우기: 넓혔다가 다시 줄인다
    floor_cells = ~dilate(~dilate(grid(near_floor, 1), 4), 3)
    obstacle = grid(solid & (Y > floor + OBST_LOW) & (Y < floor + OBST_HIGH), 2)
    walk = floor_cells & ~dilate(obstacle, int(round(BODY / CELL)))

    # 1㎡ 미만의 고립된 조각은 버린다
    label, sizes = components(walk)
    keep = [k for k, s in enumerate(sizes) if s * CELL * CELL >= 1.0]
    walk = np.isin(label, keep)

    # 시작 위치: 가장 큰 구역에서 장애물과 가장 먼 칸
    label, sizes = components(walk)
    biggest = int(np.argmax(sizes))
    core, last = label == biggest, None
    blocked = ~walk
    while core.any():
        last = core
        blocked = dilate(blocked, 1)
        core = core & ~blocked
    sz, sx = [int(v[0]) for v in np.nonzero(last)]
    start = [x0 + (sx + 0.5) * CELL, floor + EYE, z0 + (sz + 0.5) * CELL]

    # 시작 방향: 걸어서 가장 멀리 트인 쪽 (뷰어 yaw: 0도 = -Z, 90도 = -X)
    best_yaw, best_len = 0, -1
    for yaw in range(0, 360, 15):
        fx, fz = -np.sin(np.radians(yaw)), -np.cos(np.radians(yaw))
        steps = 0
        while True:
            cx, cz = int(sx + fx * (steps + 1)), int(sz + fz * (steps + 1))
            if not (0 <= cx < w and 0 <= cz < d) or not walk[cz, cx]:
                break
            steps += 1
        if steps > best_len:
            best_yaw, best_len = yaw, steps

    # 평면도(미니맵): 스캔 색을 그대로 찍으면 얼룩덜룩해서, 도면처럼 단순하게 그린다.
    #   집 안 바닥 = 흰색 · 벽과 키 큰 가구 = 진한 남색 · 낮은 가구 = 연한 파랑 · 집 밖 = 투명
    def close(mask, r):                                     # 틈 메우기
        return ~dilate(~dilate(mask, r), r)

    def open_(mask, r):                                     # 얇은 부스러기 지우기
        return dilate(~dilate(~mask, r), r)

    def keep_big(mask, min_m2):
        lab, cnt = components(mask)
        return np.isin(lab, [k for k, n in enumerate(cnt) if k and n * CELL * CELL >= min_m2])

    reach = dilate(walk, int(round(BODY / CELL)) + 1)       # 걸을 수 있는 바닥을 벽까지 넓힌 것
    lab, cnt = components(obstacle | reach)                 # 바닥과 이어진 벽·가구만 (집 밖 조각 제외)
    linked = np.isin(lab, np.unique(lab[reach])) & obstacle
    tall = linked & grid(solid & (Y > floor + 1.45) & (Y < floor + 1.75), 2)   # 눈높이까지 닿는 것 = 벽
    tall = keep_big(close(tall, 2), 0.08)
    low = keep_big(open_(close(linked & ~dilate(tall, 1), 2), 2), 0.15) & ~tall   # 낮은 가구
    inside = close(reach | low | tall, 3)
    lab, cnt = components(~inside)                          # 안쪽에 갇힌 구멍도 집 안으로
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    inside = ~np.isin(lab, list(border))

    zs, xs = np.nonzero(inside)
    m = 6                                                    # 여백(칸)
    cz0, cz1 = max(0, zs.min() - m), min(d, zs.max() + m + 1)
    cx0, cx1 = max(0, xs.min() - m), min(w, xs.max() + m + 1)
    UP = 8                                                   # 한 칸을 8픽셀로 키워 가장자리를 매끈하게

    def smooth(mask):
        im = Image.fromarray((mask[cz0:cz1, cx0:cx1] * 255).astype('u1'))
        im = im.resize((im.width * UP, im.height * UP), Image.BICUBIC).filter(ImageFilter.GaussianBlur(UP * 0.45))
        return np.clip((np.asarray(im, 'f4') - 96) / 64, 0, 1)    # 0~1 덮임 정도 (가장자리만 부드럽게)

    a_in, a_low, a_tall = smooth(inside), smooth(low), smooth(tall)
    rgb = np.ones(a_in.shape + (3,), 'f4') * np.array([255, 255, 255], 'f4')
    for alpha, color in ((a_low, (205, 221, 250)), (a_tall, (38, 52, 84))):
        rgb = rgb * (1 - alpha[..., None]) + np.array(color, 'f4') * alpha[..., None]
    alpha = a_in * 255
    Image.fromarray(np.dstack([rgb, alpha]).astype('u1'), 'RGBA').save(f'{out_dir}/map.png', optimize=True)
    map_area = {'minX': round(float(x0 + cx0 * CELL), 3), 'minZ': round(float(z0 + cz0 * CELL), 3),
                'sizeX': round(float((cx1 - cx0) * CELL), 3), 'sizeZ': round(float((cz1 - cz0) * CELL), 3)}

    Image.fromarray((walk * 255).astype('u1')).save(f'{out_dir}/nav.png', optimize=True)
    meta = {
        'rotation': [180, 0, 0],          # 스플랫에 주는 회전 (Y 아래 → Y 위)
        'cell': CELL, 'width': w, 'depth': d,
        'minX': round(float(x0), 3), 'minZ': round(float(z0), 3),
        'floorY': round(floor, 3), 'ceilingY': round(ceil, 3), 'eyeHeight': EYE,
        'start': [round(float(v), 3) for v in start], 'startYaw': best_yaw,
        'map': map_area,                  # map.png가 덮는 범위 (m)
    }
    json.dump(meta, open(f'{out_dir}/nav.json', 'w'), indent=2)
    areas = sorted((round(s * CELL * CELL, 1) for s in sizes[1:]), reverse=True)
    print(json.dumps(meta), 'areas(m2)', areas)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
