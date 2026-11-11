"""3D 스캔(.ply)에서 '걸어 다닐 수 있는 바닥' 지도를 만든다.

    python tools/build_nav.py <scene.ply> <장면 폴더>

장면 폴더에 세 파일을 쓴다.
  nav.png  — 흰색 = 걸을 수 있는 바닥 (한 칸 5cm)
  map.png  — 위에서 내려다본 컬러 평면도 (천장은 잘라 냄, 미니맵용)
  nav.json — 범위 · 바닥 높이 · 눈높이 · 시작 위치와 방향
좌표는 뷰어 기준(스플랫을 X축으로 180도 돌린 뒤: X=x, Y=-y, Z=-z, 위가 +Y).
필요: numpy, pillow
"""
import json
import sys
from collections import deque

import numpy as np
from PIL import Image

CELL = 0.05          # 격자 한 칸 (m)
BODY = 0.18          # 사람 반경 — 벽·가구에서 이만큼 떨어진 곳만 걸을 수 있음 (m)
OBST_LOW, OBST_HIGH = 0.25, 1.7   # 바닥에서 이 높이 사이에 뭔가 있으면 장애물 (m)
EYE = 1.5            # 눈높이 (m)
MAP_CELL = 0.025     # 평면도 그림 한 칸 (m)
MAP_CUT = 2.0        # 바닥에서 이 높이 위(천장·조명)는 평면도에서 뺀다 (m)


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
    rgb = np.clip(0.5 + 0.28209479 * np.stack([d['f_dc_0'], d['f_dc_1'], d['f_dc_2']], 1), 0, 1)
    return d['x'], -d['y'], -d['z'], opacity, rgb


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
    X, Y, Z, op, rgb = read_ply(ply)
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

    # 평면도: 천장을 잘라 내고 위에서 본 색. 높은 점이 낮은 점을 덮는다.
    scale = int(round(CELL / MAP_CELL))
    mw, md = w * scale, d * scale
    sel = (op > 0.3) & (Y > floor - 0.3) & (Y < floor + MAP_CUT)
    xi = ((X[sel] - x0) / MAP_CELL).astype(int)
    zi = ((Z[sel] - z0) / MAP_CELL).astype(int)
    inside = (xi >= 0) & (xi < mw) & (zi >= 0) & (zi < md)
    order = np.argsort(Y[sel][inside])
    xi, zi, col = xi[inside][order], zi[inside][order], rgb[sel][inside][order]
    img = np.zeros((md, mw, 3), 'f4')
    filled = np.zeros((md, mw), bool)
    img[zi, xi] = col
    filled[zi, xi] = True
    for _ in range(6):   # 점 사이의 작은 빈칸은 이웃 색 평균으로 메운다
        acc, cnt = np.zeros_like(img), np.zeros((md, mw), 'f4')
        for dz in (-1, 0, 1):
            for dx in (-1, 0, 1):
                src_f = np.roll(np.roll(filled, dz, 0), dx, 1)
                acc += np.roll(np.roll(img, dz, 0), dx, 1) * src_f[..., None]
                cnt += src_f
        grow = ~filled & (cnt >= 3)
        img[grow] = acc[grow] / cnt[grow][:, None]
        filled |= grow
    rgba = np.dstack([np.clip(img * 255, 0, 255), filled * 255]).astype('u1')
    Image.fromarray(rgba, 'RGBA').save(f'{out_dir}/map.png', optimize=True)

    Image.fromarray((walk * 255).astype('u1')).save(f'{out_dir}/nav.png', optimize=True)
    meta = {
        'rotation': [180, 0, 0],          # 스플랫에 주는 회전 (Y 아래 → Y 위)
        'cell': CELL, 'width': w, 'depth': d,
        'minX': round(float(x0), 3), 'minZ': round(float(z0), 3),
        'floorY': round(floor, 3), 'ceilingY': round(ceil, 3), 'eyeHeight': EYE,
        'start': [round(float(v), 3) for v in start], 'startYaw': best_yaw,
    }
    json.dump(meta, open(f'{out_dir}/nav.json', 'w'), indent=2)
    areas = sorted((round(s * CELL * CELL, 1) for s in sizes[1:]), reverse=True)
    print(json.dumps(meta), 'areas(m2)', areas)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
