// ③ 매물 상세 — 사진으로 둘러보기 (3D 스캔이 없는 매물용)
//
// 매물 사진 한 장을 둥근 벽(원통 안쪽)에 붙이고 그 가운데에서 바라본다. 드래그하면 고개를 돌리듯 사진 속을 둘러본다.
// 깊이 지도(static/listings/depth/번호.jpg — 밝을수록 가까움)가 있으면 가까운 것과 먼 것을 다르게 움직여 입체로 보이게 한다.
// 진짜 3D 스캔이 아니라는 건 화면에 적는다. 엔진 없이 WebGL 만 쓰고, WebGL 이 안 되면 CSS 3D(깊이감 없음)로 보여 준다.
// 쓰는 법: <section class="viewer" data-photo="사진 주소" data-depth="깊이 지도 주소"> 안에
//          stage · world · loading · hint · reset · wide · expand 를 둔다.
// 깊이 지도 다시 만들기(사진을 바꿨을 때): python tools/make_depth.py
(function () {
  var root = document.querySelector('.viewer[data-photo]');
  if (!root) return;

  var el = function (name) { return root.querySelector('[data-el="' + name + '"]'); };
  var stage = el('stage');
  var world = el('world');
  var loading = el('loading');
  var hint = el('hint');

  var STRIPS = 40;          // (CSS 방식) 둥근 벽을 이루는 세로 조각 수
  var FOV_NORMAL = 70;      // 가로 시야각(도)
  var FOV_WIDE = 95;        // 넓게 보기
  var FOV_MIN = 38;         // 가장 크게 확대했을 때
  var MIN_ARC = 130;        // 사진이 감싸는 각도(도) — 클수록 더 많이 돌아볼 수 있지만 사진이 커진다(흐려진다)
  var DEPTH_SHIFT = 0.016;  // 깊이감 세기 — 가장 가까운 것이 사진 너비의 이만큼까지 밀린다 (크면 가장자리가 늘어져 보인다)
  var DEPTH_FOCUS = 0.4;    // 이 깊이는 움직이지 않는다 (0 멀다 ~ 1 가깝다)
  var RAD = Math.PI / 180;
  var reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

  var view = { yaw: 0, pitch: 0, yawTo: 0, pitchTo: 0, fov: FOV_NORMAL, fovTo: FOV_NORMAL };
  var sway = { x: 0, y: 0, xTo: 0, yTo: 0 };   // 머리를 살짝 옮긴 정도(-1 ~ 1) — 깊이감에 쓴다
  var vel = { yaw: 0, pitch: 0 };              // 놓은 뒤 미끄러지는 속도(도/초)
  var geo = null;           // { R, arc, height, ratio } — 화면 크기가 바뀌면 다시 계산
  var strips = [];
  var img = new Image();
  var original = root.dataset.photo;
  var sharp = original.replace(/([?&]w=)800\b/, '$11800');   // 크게 늘려 보여 주니 더 큰 사진을 받는다 (Unsplash)

  // 사진 받기 — WebGL 은 '다른 사이트 사진을 써도 된다'는 허락(CORS)이 있어야 해서 그 방식부터 시도한다
  var tries = [{ src: sharp, cors: true }, { src: original, cors: true }, { src: original, cors: false }];
  var attempt = -1;
  function loadNext() {
    attempt += 1;
    if (attempt >= tries.length) return fail();
    img = new Image();
    if (tries[attempt].cors) img.crossOrigin = 'anonymous';
    img.onload = ready;
    img.onerror = loadNext;
    img.src = tries[attempt].src;
  }
  function fail() {
    loading.classList.add('is-error');
    loading.querySelector('p').textContent = '사진을 불러오지 못했어요. 잠시 후 새로고침해 주세요.';
  }
  function ready() {
    if (tries[attempt].cors) startGL();
    build();
    loading.classList.add('is-done');
    root.classList.add('is-ready');
    if (!reducedMotion && geo) {          // 처음에 천천히 둘러보며 '움직일 수 있다'는 걸 보여 준다 (만지면 멈춘다)
      view.yaw = limits().yaw * 0.6;
      auto = true;
    }
    requestAnimationFrame(frame);
  }
  loadNext();

  // ── WebGL: 화면의 점마다 '어느 방향을 보는지 → 사진의 어디인지'를 계산해 그린다 ──
  var gl = null, canvas = null, uni = null, hasDepth = false;
  var VERT = 'attribute vec2 p; void main(){ gl_Position = vec4(p, 0.0, 1.0); }';
  var FRAG = [
    'precision highp float;',
    'uniform sampler2D uTex, uDepth;',
    'uniform vec2 uRes, uCam;',
    'uniform float uP, uYaw, uPitch, uR, uArc, uH, uHasDepth, uFocus;',
    'void main(){',
    '  vec3 r = vec3(gl_FragCoord.xy - uRes * 0.5, -uP);',                    // 이 점을 지나는 시선
    '  float cp = cos(uPitch), sp = sin(uPitch);',
    '  r = vec3(r.x, r.y * cp - r.z * sp, r.y * sp + r.z * cp);',             // 위아래로 고개 돌리기
    '  float cy = cos(uYaw), sy = sin(uYaw);',
    '  r = vec3(r.x * cy + r.z * sy, r.y, -r.x * sy + r.z * cy);',            // 좌우로 고개 돌리기
    '  vec2 uv = vec2(0.5 + atan(r.x, -r.z) / uArc, 0.5 - r.y * uR / length(r.xz) / uH);',   // 둥근 벽의 어디에 닿는지
    '  if (uHasDepth > 0.5) {',                                               // 가까운 것일수록 더 많이 밀기
    '    vec2 o = uv;',
    '    for (int i = 0; i < 4; i++) {',
    '      float d = texture2D(uDepth, clamp(o, 0.0, 1.0)).r;',
    '      o = uv + uCam * (d - uFocus);',
    '    }',
    '    uv = o;',
    '  }',
    '  gl_FragColor = texture2D(uTex, clamp(uv, 0.001, 0.999));',
    '}'
  ].join('\n');

  function startGL() {
    try {
      canvas = document.createElement('canvas');
      canvas.setAttribute('aria-hidden', 'true');
      var opts = { antialias: false, alpha: false, powerPreference: 'low-power' };
      var gl2 = canvas.getContext('webgl2', opts);
      gl = gl2 || canvas.getContext('webgl', opts);
      if (!gl) throw new Error('no webgl');

      var prog = gl.createProgram();
      [[gl.VERTEX_SHADER, VERT], [gl.FRAGMENT_SHADER, FRAG]].forEach(function (s) {
        var sh = gl.createShader(s[0]);
        gl.shaderSource(sh, s[1]);
        gl.compileShader(sh);
        if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(sh));
        gl.attachShader(prog, sh);
      });
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
      gl.useProgram(prog);

      gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());                     // 화면 전체를 덮는 세모 하나
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
      var loc = gl.getAttribLocation(prog, 'p');
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

      uni = {};
      ['uTex', 'uDepth', 'uRes', 'uCam', 'uP', 'uYaw', 'uPitch', 'uR', 'uArc', 'uH', 'uHasDepth', 'uFocus'].forEach(function (n) {
        uni[n] = gl.getUniformLocation(prog, n);
      });
      texture(0, img, !!gl2);
      gl.uniform1i(uni.uTex, 0);
      gl.uniform1i(uni.uDepth, 1);
      gl.uniform1f(uni.uFocus, DEPTH_FOCUS);

      stage.insertBefore(canvas, world);
      canvas.addEventListener('webglcontextlost', function (e) {             // 그래픽 장치를 잃으면 CSS 방식으로 바꾼다
        e.preventDefault();
        stopGL();
        build();
      });
      loadDepth();
    } catch (err) {
      stopGL();
    }
  }
  function stopGL() {
    if (canvas && canvas.parentNode) canvas.parentNode.removeChild(canvas);
    gl = null; canvas = null; hasDepth = false;
    root.classList.remove('has-depth');
    drawn = '';
  }
  function texture(unit, image, mipmap) {
    gl.activeTexture(gl.TEXTURE0 + unit);
    gl.bindTexture(gl.TEXTURE_2D, gl.createTexture());
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    if (mipmap) gl.generateMipmap(gl.TEXTURE_2D);                            // 작게 볼 때 자글거리지 않게 (WebGL2)
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, mipmap ? gl.LINEAR_MIPMAP_LINEAR : gl.LINEAR);
  }
  function loadDepth() {
    var url = root.dataset.depth;
    if (!url || reducedMotion) return;                                       // 움직임 줄이기를 켠 사람에게는 깊이 움직임을 안 쓴다
    var d = new Image();
    d.onload = function () {
      if (!gl) return;
      try {
        texture(1, d, false);
        hasDepth = true;
        root.classList.add('has-depth');
        drawn = '';
      } catch (err) { hasDepth = false; }
    };
    d.src = url;                                                             // 못 받으면 깊이감 없이 그대로 보여 준다
  }

  // ── 둥근 벽 크기 계산 (WebGL · CSS 공통) ───────────────────
  function build() {
    var w = stage.clientWidth;
    var h = stage.clientHeight;
    if (!w || !h || !img.naturalWidth) return;
    var ratio = img.naturalWidth / img.naturalHeight;
    var R = (w / 2) / Math.tan(FOV_NORMAL * RAD / 2);                 // 기본 시야에서 사진이 1배로 보이는 거리
    var arc = Math.min(220, Math.max(MIN_ARC, (1.3 * h * ratio / R) / RAD));   // 위아래도 다 덮이게
    var length = R * arc * RAD;                                        // 펼친 사진의 가로 길이
    var height = length / ratio;
    geo = { R: R, arc: arc, height: height, ratio: ratio };

    if (gl) {
      var dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      gl.viewport(0, 0, canvas.width, canvas.height);
      world.style.display = 'none';
    } else {
      world.style.display = '';
      buildStrips(R, arc, length, height);
    }
    clampView();
    drawn = '';
  }

  // (CSS 방식) 세로 조각을 둥글게 세운다
  function buildStrips(R, arc, length, height) {
    var step = arc / STRIPS;
    var stripW = 2 * R * Math.tan(step * RAD / 2) + 1.5;               // 틈이 안 보이게 조금 겹친다
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
  function setFov(fov) {
    view.fovTo = Math.min(FOV_WIDE, Math.max(FOV_MIN, fov));
    wide.setAttribute('aria-pressed', String(view.fovTo >= FOV_WIDE - 1));
    clampView();
  }

  // ── 매 프레임: 목표 각도를 부드럽게 따라간다 ───────────────
  var drawn = '';
  var last = performance.now();
  var auto = false;         // 처음에 혼자 천천히 둘러보는 중인지
  var autoTime = 0;
  function frame(now) {
    var dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    if (!geo) { requestAnimationFrame(frame); return; }
    var lim = limits();

    if (keys.size) {
      var turn = (keys.has('ArrowLeft') || keys.has('KeyA') ? 1 : 0) - (keys.has('ArrowRight') || keys.has('KeyD') ? 1 : 0);
      var tilt = (keys.has('ArrowUp') || keys.has('KeyW') ? 1 : 0) - (keys.has('ArrowDown') || keys.has('KeyS') ? 1 : 0);
      var speed = view.fov / FOV_NORMAL;                                // 확대했을 땐 천천히
      view.yawTo += turn * 40 * speed * dt;
      view.pitchTo += tilt * 25 * speed * dt;
      clampView();
    } else if (!dragging && (Math.abs(vel.yaw) > 1 || Math.abs(vel.pitch) > 1)) {
      view.yawTo += vel.yaw * dt;                                       // 놓은 뒤 조금 더 미끄러진다
      view.pitchTo += vel.pitch * dt;
      var slow = Math.exp(-dt * 4.5);
      vel.yaw *= slow;
      vel.pitch *= slow;
      clampView();
    } else if (auto) {
      autoTime += dt;
      view.yawTo = lim.yaw * 0.6 * Math.cos(autoTime * 0.32);
      if (!hovering && !tilting) {
        sway.xTo = Math.sin(autoTime * 0.9) * 0.7;
        sway.yTo = Math.cos(autoTime * 0.6) * 0.35;
      }
    }

    var follow = reducedMotion ? 1 : 1 - Math.exp(-dt * (dragging || keys.size ? 16 : 3));
    view.yaw += (view.yawTo - view.yaw) * follow;
    view.pitch += (view.pitchTo - view.pitch) * follow;
    view.fov += (view.fovTo - view.fov) * (reducedMotion ? 1 : 1 - Math.exp(-dt * 8));
    var ease = 1 - Math.exp(-dt * 5);
    sway.x += (sway.xTo - sway.x) * ease;
    sway.y += (sway.yTo - sway.y) * ease;

    var p = (stage.clientWidth / 2) / Math.tan(view.fov * RAD / 2);
    // 머리 위치: 손 · 기울기로 옮긴 만큼 + 고개를 돌린 쪽으로 조금 (왼쪽을 보면 머리도 왼쪽으로)
    var camX = sway.x * 0.65 - (lim.yaw ? view.yaw / lim.yaw : 0) * 0.5;
    var camY = sway.y * 0.65 + (lim.pitch ? view.pitch / lim.pitch : 0) * 0.5;
    var next = p.toFixed(1) + '|' + view.pitch.toFixed(3) + '|' + view.yaw.toFixed(3) +
               (hasDepth ? '|' + camX.toFixed(3) + '|' + camY.toFixed(3) : '');
    if (next !== drawn) {
      drawn = next;
      if (gl) {
        var k = canvas.width / stage.clientWidth;                       // CSS 크기 → 실제 화소
        gl.uniform2f(uni.uRes, canvas.width, canvas.height);
        gl.uniform1f(uni.uP, p * k);
        gl.uniform1f(uni.uR, geo.R * k);
        gl.uniform1f(uni.uH, geo.height * k);
        gl.uniform1f(uni.uArc, geo.arc * RAD);
        gl.uniform1f(uni.uYaw, view.yaw * RAD);
        gl.uniform1f(uni.uPitch, view.pitch * RAD);
        gl.uniform1f(uni.uHasDepth, hasDepth ? 1 : 0);
        gl.uniform2f(uni.uCam, camX * DEPTH_SHIFT, -camY * DEPTH_SHIFT * geo.ratio);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      } else {
        stage.style.perspective = p + 'px';
        world.style.transform = 'translateZ(' + p + 'px) rotateX(' + view.pitch + 'deg) rotateY(' + (-view.yaw) + 'deg)';
      }
    }
    requestAnimationFrame(frame);
  }

  // 사람이 만지기 시작하면: 안내 문구를 지우고, 혼자 둘러보기를 멈춘다
  var hintGone = false;
  function touched() {
    auto = false;
    if (hintGone) return;
    hintGone = true;
    if (hint) hint.classList.add('is-gone');
  }

  // ── 입력: 드래그 · 두 손가락 확대 · 휠 · 키보드 ─────────────
  var dragging = null;
  var pointers = new Map();     // 지금 화면에 닿아 있는 손가락들
  var pinch = null;             // { dist, fov } — 두 손가락을 올린 순간의 간격과 시야각
  var hovering = false;
  var tilting = false;

  function spread() {
    var pts = Array.from(pointers.values());
    return Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y);
  }
  stage.addEventListener('pointerdown', function (e) {
    stage.setPointerCapture(e.pointerId);
    stage.focus({ preventScroll: true });
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    vel.yaw = vel.pitch = 0;
    touched();
    if (pointers.size === 2) {
      pinch = { dist: spread(), fov: view.fovTo };
      dragging = null;
    } else if (pointers.size === 1) {
      dragging = { x: e.clientX, y: e.clientY, t: performance.now() };
      root.classList.add('is-dragging');
    }
  });
  stage.addEventListener('pointermove', function (e) {
    if (!geo) return;
    if (pointers.has(e.pointerId)) pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pinch && pointers.size === 2) {
      setFov(pinch.fov * pinch.dist / Math.max(20, spread()));        // 벌리면 확대
      return;
    }
    if (dragging) {
      var k = view.fov / stage.clientWidth;                           // 끈 거리만큼 사진이 따라오게
      var dYaw = (e.clientX - dragging.x) * k;
      var dPitch = (e.clientY - dragging.y) * k;
      var now = performance.now();
      var dt = Math.max(0.008, (now - dragging.t) / 1000);
      vel.yaw = vel.yaw * 0.6 + (dYaw / dt) * 0.4;
      vel.pitch = vel.pitch * 0.6 + (dPitch / dt) * 0.4;
      view.yawTo += dYaw;
      view.pitchTo += dPitch;
      dragging = { x: e.clientX, y: e.clientY, t: now };
      clampView();
    } else if (e.pointerType === 'mouse' && !reducedMotion) {         // 마우스를 올리기만 해도 살짝 입체로
      var box = stage.getBoundingClientRect();
      hovering = true;
      sway.xTo = ((e.clientX - box.left) / box.width - 0.5) * 2;
      sway.yTo = -((e.clientY - box.top) / box.height - 0.5) * 2;
    }
  });
  function endPointer(e) {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = null;
    if (dragging) {
      if (reducedMotion || performance.now() - dragging.t > 90) vel.yaw = vel.pitch = 0;   // 멈췄다가 놓으면 그대로 선다
      vel.yaw = Math.max(-220, Math.min(220, vel.yaw));
      vel.pitch = Math.max(-140, Math.min(140, vel.pitch));
    }
    dragging = null;
    root.classList.remove('is-dragging');
  }
  stage.addEventListener('pointerup', endPointer);
  stage.addEventListener('pointercancel', endPointer);
  stage.addEventListener('pointerleave', function () {
    hovering = false;
    if (!tilting) { sway.xTo = 0; sway.yTo = 0; }
  });

  // 휠 확대 — 페이지 스크롤을 뺏지 않게, 크게 보기일 때나 Ctrl 을 누른 때만
  stage.addEventListener('wheel', function (e) {
    if (!root.classList.contains('is-expanded') && !e.ctrlKey) return;
    e.preventDefault();
    touched();
    setFov(view.fovTo * Math.exp(e.deltaY * 0.0015));
  }, { passive: false });

  // 두 번 누르면 확대 ↔ 원래대로
  stage.addEventListener('dblclick', function () {
    touched();
    setFov(view.fovTo < 55 ? FOV_NORMAL : 44);
  });

  var keys = new Set();
  var KEYS = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'KeyW', 'KeyA', 'KeyS', 'KeyD'];
  stage.addEventListener('keydown', function (e) {
    if (e.key === '+' || e.key === '=') { e.preventDefault(); touched(); setFov(view.fovTo - 8); return; }
    if (e.key === '-' || e.key === '_') { e.preventDefault(); touched(); setFov(view.fovTo + 8); return; }
    if (KEYS.indexOf(e.code) < 0) return;
    e.preventDefault();
    keys.add(e.code);
    vel.yaw = vel.pitch = 0;
    touched();
  });
  stage.addEventListener('keyup', function (e) { keys.delete(e.code); });
  stage.addEventListener('blur', function () { keys.clear(); });

  // 폰을 기울이면 살짝 입체로 (허락을 따로 묻는 기기에서는 쓰지 않는다)
  if (!reducedMotion && window.DeviceOrientationEvent && typeof DeviceOrientationEvent.requestPermission !== 'function') {
    window.addEventListener('deviceorientation', function (e) {
      if (e.gamma == null || e.beta == null) return;
      tilting = true;
      sway.xTo = Math.max(-1, Math.min(1, e.gamma / 18));
      sway.yTo = Math.max(-1, Math.min(1, (e.beta - 50) / 18));
    });
  }

  // ── 버튼 ───────────────────────────────────────────────────
  el('reset').addEventListener('click', function () {
    touched();
    vel.yaw = vel.pitch = 0;
    view.yawTo = 0;
    view.pitchTo = 0;
    setFov(FOV_NORMAL);
  });
  var wide = el('wide');
  wide.addEventListener('click', function () {
    touched();
    setFov(view.fovTo >= FOV_WIDE - 1 ? FOV_NORMAL : FOV_WIDE);
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

  new ResizeObserver(build).observe(stage);     // 창 크기 · 크게 보기가 바뀌면 다시 맞춘다
})();
