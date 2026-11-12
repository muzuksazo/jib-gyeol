// ask-widget.js — 물어보기 챗봇 창 (모든 페이지 공통 · templates/_ask_widget.html)
// 질문을 POST /ask/api 로 보내고 답 · '확인해보기' 버튼을 말풍선으로 보여 줘요. 검사와 답은 전부 서버가 해요.
// 대화는 이 탭에서만 기억해요(sessionStorage) — 다른 페이지로 가도 이어지고, 탭을 닫으면 사라져요.
// 사용자 · 모델이 쓴 글은 항상 textContent 로만 넣어요 (태그로 해석되지 않게).
(function () {
  var dialog = document.querySelector("[data-askw]");
  if (!dialog || typeof dialog.showModal !== "function") return;   // 오래된 브라우저 → 버튼이 /ask 링크로 동작

  var log = dialog.querySelector("[data-askw-log]");
  var form = dialog.querySelector("[data-askw-form]");
  var input = form.querySelector("textarea");
  var send = form.querySelector("button");
  var intro = log.innerHTML;                    // 첫 인사 + 예시 질문 (새 대화 때 되돌려요)
  var KEY = "askw-chat";
  var MAX_KEEP = 30;                            // 기억할 말풍선 수
  var chat = load();
  var busy = false;

  function load() {
    try { return JSON.parse(sessionStorage.getItem(KEY)) || []; } catch (e) { return []; }
  }
  function save() {
    try { sessionStorage.setItem(KEY, JSON.stringify(chat.slice(-MAX_KEEP))); } catch (e) { /* 저장 못 해도 그대로 써요 */ }
  }
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }
  function scrollDown() { log.scrollTop = log.scrollHeight; }

  // ── 말풍선 그리기 ──
  function botBubble(data) {
    var box = el("div", "askw-msg bot" + (data.not_found ? " none" : ""));
    if (data.not_found) {
      var p = el("p");
      p.append(el("strong", null, data.answer), "이 내용은 집결 안내 문서에 없어요.");
      box.append(p);
      var next = el("div", "askw-next");
      var a1 = el("a", null, "의뢰서로 조건 남기기"); a1.href = dialog.dataset.requestUrl;
      var a2 = el("a", null, "매물 보러 가기"); a2.href = dialog.dataset.listingsUrl;
      next.append(a1, a2);
      box.append(next);
    } else {
      box.append(el("p", null, data.answer));
      if (data.links && data.links.length) {      // 출처 대신 — 답을 직접 확인할 화면으로 가는 버튼
        box.append(el("p", "askw-check", "확인해보기"));
        var go = el("div", "askw-next");
        data.links.forEach(function (link) {
          var a = el("a", null, link.label + " →");
          a.href = link.url;
          go.append(a);
        });
        box.append(go);
      }
    }
    return box;
  }
  function draw(item) {
    if (item.role === "user") return el("div", "askw-msg user", item.text);
    if (item.role === "error") { var e = el("div", "askw-msg error", item.text); e.setAttribute("role", "alert"); return e; }
    return botBubble(item.data);
  }
  function add(item) {
    var examples = log.querySelector("[data-askw-examples]");
    if (examples) examples.remove();            // 대화가 시작되면 예시는 치워요
    chat.push(item);
    save();
    log.append(draw(item));
    scrollDown();
  }
  function restore() {
    log.innerHTML = intro;
    if (chat.length) {
      var examples = log.querySelector("[data-askw-examples]");
      if (examples) examples.remove();
      chat.forEach(function (item) { log.append(draw(item)); });
    }
    scrollDown();
  }

  // ── 물어보기 ──
  function ask(question) {
    question = question.trim();
    if (!question || busy) return;
    busy = true;
    send.disabled = true;
    add({ role: "user", text: question });
    input.value = "";
    grow();

    var wait = el("div", "askw-msg bot");
    wait.setAttribute("role", "status");
    var dots = el("span", "askw-dots");
    dots.append(el("i"), el("i"), el("i"));
    wait.append(dots, el("span", "sr-only", "문서에서 찾는 중이에요"));
    log.append(wait);
    scrollDown();

    fetch(dialog.dataset.api, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question }),
    })
      .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
      .then(function (r) {
        if (r.ok) add({ role: "bot", data: r.data });
        else add({ role: "error", text: r.data.error || "답을 가져오지 못했어요. 잠시 후 다시 물어봐 주세요." });
      })
      .catch(function () {
        add({ role: "error", text: "서버에 연결하지 못했어요. 인터넷 연결을 확인하고 다시 물어봐 주세요." });
      })
      .finally(function () {
        wait.remove();
        busy = false;
        send.disabled = false;
        input.focus();
      });
  }

  function grow() {                             // 입력칸은 쓴 만큼 커져요 (최대 높이는 CSS)
    input.style.height = "auto";
    input.style.height = input.scrollHeight + 2 + "px";
  }

  // ── 열기 · 닫기 ──
  document.querySelectorAll("[data-askw-open]").forEach(function (opener) {
    opener.addEventListener("click", function (e) {
      if (e.ctrlKey || e.metaKey || e.shiftKey) return;   // 새 탭으로 열기는 그대로 (/ask 페이지)
      e.preventDefault();
      if (!dialog.open) dialog.showModal();
      scrollDown();
      input.focus();
    });
  });
  dialog.querySelector("[data-askw-close]").addEventListener("click", function () { dialog.close(); });
  dialog.addEventListener("click", function (e) {         // 창 바깥(흐린 배경)을 누르면 닫혀요
    if (e.target === dialog) dialog.close();
  });
  dialog.querySelector("[data-askw-reset]").addEventListener("click", function () {
    if (busy) return;
    chat = [];
    save();
    restore();
    input.focus();
  });

  log.addEventListener("click", function (e) {
    var example = e.target.closest("[data-askw-example]");
    if (example) ask(example.textContent);
  });
  form.addEventListener("submit", function (e) { e.preventDefault(); ask(input.value); });
  input.addEventListener("input", grow);
  input.addEventListener("keydown", function (e) {        // Enter = 보내기, Shift+Enter = 줄바꿈
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); ask(input.value); }
  });

  restore();
})();
