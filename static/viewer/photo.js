// ③ 매물 상세 — 사진으로 둘러보기 (3D 스캔이 없는 매물용)
//
// 매물 사진 한 장을 둥근 벽(원통 안쪽)에 붙이고 그 가운데에서 바라본다. 드래그하면 고개를 돌리듯 사진 속을 둘러본다.
// 진짜 3D 스캔이 아니라는 건 화면에 적는다. 엔진 없이 CSS 3D 만 쓴다 (사진 주소만 있으면 된다).
// 쓰는 법: <section class="viewer" data-photo="사진 주소"> 안에 stage · world · loading · hint · reset · wide · expand 를 둔다.
(function () {
  var root = document.querySelector('.viewer[data-photo]');
  if (!root) return;

  var el = function (name) { return root.querySelector('[data-el="' + name + '"]'); };
  var stage = el('stage');
  var world = el('world');
  var loading = el('loading');
  var hint = el('hint');

  var STRIPS = 40;          // 둥근 벽을 이루는 세로 조각 수
  var FOV_NORMAL = 70;      // 가로 시야각(도)
  var FOV_WIDE = 95;
  var MIN_ARC = 130;        // 사진이 감싸는 각도(도) — 클수록 더 많이 돌아볼 수 있지만 사진이 커진다(흐려진다)
  var RAD = Math.PI / 180;
  var reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

  var view = { yaw: 0, pitch: 0, yawTo: 0, pitchTo: 0, fov: FOV_NORMAL, fovTo: FOV_NORMAL };
  var geo = null;           // { R, arc, height } — 화면 크기가 바뀌면 다시 계산
  var strips = [];
  var img = new Image();
  var original = root.dataset.photo;
  var sharp = original.replace(/([?&]w=)800\b/, '$11800');   // 크게 늘려 보여 주니 더 큰 사진을 받는다 (Unsplash)

  function fail() {
    loading.classList.add('is-error');
    loading.querySelector('p').textContent = '사진을 불러오지 못했어요. 잠시 후 새로고침해 주세요.';
  }
  img.onload = function () {
    build();
    loading.classList.add('is-done');
    root.classList.add('is-ready');
    if (!reducedMotion && geo) {          // 처음에 살짝 돌아오며 '움직일 수 있다'는 걸 보여 준다
      view.yaw = limits().yaw * 0.7;
    }
    requestAnimationFrame(frame);
  };
  img.onerror = function () {
    if (img.src !== new URL(original, location.href).href) img.src = original;   // 큰 사진이 안 되면 원래 사진으로
    else fail();
  };
  img.src = sharp;

  // ── 둥근 벽 만들기 ─────────────────────────────────────────
  function build() {
    var w = stage.clientWidth;
    var h = stage.clientHeight;
    if (!w || !h || !img.naturalWidth) return;
    var ratio = img.naturalWidth / img.naturalHeight;
    var R = (w / 2) / Math.tan(FOV_NORMAL * RAD / 2);                 // 기본 시야에서 사진이 1배로 보이는 거리
    var arc = Math.min(220, Math.max(MIN_ARC, (1.3 * h * ratio / R) / RAD));   // 위아래도 다 덮이게
    var length = R * arc * RAD;                                        // 펼친 사진의 가로 길이
    var height = length / ratio;
    var step = arc / STRIPS;
    var stripW = 2 * R * Math.tan(step * RAD / 2) + 1.5;               // 틈이 안 보이게 조금 겹친다
    geo = { R: R, arc: arc, height: height };

    if (!strips.length) {
      for (var i = 0; i < STRIPS; i++) {
        var s = document.createElement('div');
        s.className = 'pv-strip';
        s.style.backgroundImage = 'url("' + img.src.replace(/"/g, '%22') + '")';
        world.appendChild(s);
        strips.push(s);
      }
    }
    strips.forEach(function (s, i) {
      var angle = arc / 2 - (i + 0.5) * step;                          // 사진 왼쪽 끝이 왼쪽에 오게
      s.style.width = stripW + 'px';
      s.style.height = height + 'px';
      s.style.margin = (-height / 2) + 'px 0 0 ' + (-stripW / 2) + 'px';
      s.style.backgroundSize = length + 'px ' + height + 'px';
      s.style.backgroundPosition = (-(i * length / STRIPS)) + 'px 0';
      s.style.transform = 'rotateY(' + angle + 'deg) translateZ(' + (-R) + 'px)';
    });
    clampView();
    drawn = '';
  }

  // 사진 밖(빈 곳)이 보이지 않는 범위
  function limits() {
    var w = stage.clientWidth;
    var h = stage.clientHeight;
    var p = (w / 2) / Math.tan(view.fovTo * RAD / 2);
    var vfov = 2 * Math.atan(h / 2 / p) / RAD;
    return {
      yaw: Math.max(0, (geo.arc - view.fovTo) / 2 - 3),
      pitch: Math.max(0, Math.atan(geo.height / 2 / geo.R) / RAD - vfov / 2 - 2)
    };
  }
  function clampView() {
    if (!geo) return;
    var lim = limits();
    view.yawTo = Math.min(lim.yaw, Math.max(-lim.yaw, view.yawTo));
    view.pitchTo = Math.min(lim.pitch, Math.max(-lim.pitch, view.pitchTo));
  }

  // ── 매 프레임: 목표 각도를 부드럽게 따라간다 ───────────────
  var drawn = '';
  var last = performance.now();
  function frame(now) {
    var dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (keys.size) {
      var turn = (keys.has('ArrowLeft') || keys.has('KeyA') ? 1 : 0) - (keys.has('ArrowRight') || keys.has('KeyD') ? 1 : 0);
      var tilt = (keys.has('ArrowUp') || keys.has('KeyW') ? 1 : 0) - (keys.has('ArrowDown') || keys.has('KeyS') ? 1 : 0);
      view.yawTo += turn * 40 * dt;
      view.pitchTo += tilt * 25 * dt;
      clampView();
    }
    var follow = reducedMotion ? 1 : 1 - Math.exp(-dt * (dragging || keys.size ? 16 : 3));
    view.yaw += (view.yawTo - view.yaw) * follow;
    view.pitch += (view.pitchTo - view.pitch) * follow;
    view.fov += (view.fovTo - view.fov) * (reducedMotion ? 1 : 1 - Math.exp(-dt * 8));

    var p = (stage.clientWidth / 2) / Math.tan(view.fov * RAD / 2);
    var next = p.toFixed(1) + '|' + view.pitch.toFixed(3) + '|' + view.yaw.toFixed(3);
    if (next !== drawn) {
      drawn = next;
      stage.style.perspective = p + 'px';
      world.style.transform = 'translateZ(' + p + 'px) rotateX(' + view.pitch + 'deg) rotateY(' + (-view.yaw) + 'deg)';
    }
    requestAnimationFrame(frame);
  }

  // ── 입력: 드래그 · 키보드 ──────────────────────────────────
  var dragging = null;
  stage.addEventListener('pointerdown', function (e) {
    stage.setPointerCapture(e.pointerId);
    stage.focus({ preventScroll: true });
    dragging = { x: e.clientX, y: e.clientY };
    root.classList.add('is-dragging');
  });
  stage.addEventListener('pointermove', function (e) {
    if (!dragging || !geo) return;
    var k = view.fov / stage.clientWidth;          // 끈 거리만큼 사진이 따라오게
    view.yawTo += (e.clientX - dragging.x) * k;
    view.pitchTo += (e.clientY - dragging.y) * k;
    dragging.x = e.clientX;
    dragging.y = e.clientY;
    clampView();
    dismissHint();
  });
  function endDrag() {
    dragging = null;
    root.classList.remove('is-dragging');
  }
  stage.addEventListener('pointerup', endDrag);
  stage.addEventListener('pointercancel', endDrag);

  var keys = new Set();
  var KEYS = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'KeyW', 'KeyA', 'KeyS', 'KeyD'];
  stage.addEventListener('keydown', function (e) {
    if (KEYS.indexOf(e.code) < 0) return;
    e.preventDefault();
    keys.add(e.code);
    dismissHint();
  });
  stage.addEventListener('keyup', function (e) { keys.delete(e.code); });
  stage.addEventListener('blur', function () { keys.clear(); });

  // ── 버튼 ───────────────────────────────────────────────────
  el('reset').addEventListener('click', function () {
    view.yawTo = 0;
    view.pitchTo = 0;
  });
  var wide = el('wide');
  wide.addEventListener('click', function () {
    var on = view.fovTo === FOV_NORMAL;
    view.fovTo = on ? FOV_WIDE : FOV_NORMAL;
    wide.setAttribute('aria-pressed', String(on));
    clampView();
  });
  var expand = el('expand');
  function setExpanded(on) {
    root.classList.toggle('is-expanded', on);
    document.documentElement.classList.toggle('viewer-expanded', on);
    expand.setAttribute('aria-pressed', String(on));
    expand.textContent = on ? '닫기' : '크게 보기';
  }
  expand.addEventListener('click', function () { setExpanded(!root.classList.contains('is-expanded')); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && root.classList.contains('is-expanded')) setExpanded(false);
  });

  var hintGone = false;
  function dismissHint() {
    if (hintGone) return;
    hintGone = true;
    if (hint) hint.classList.add('is-gone');
  }

  new ResizeObserver(build).observe(stage);     // 창 크기 · 크게 보기가 바뀌면 다시 맞춘다
})();
