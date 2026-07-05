(() => {
  const tg = window.Telegram?.WebApp;
  const $ = (s, r = document) => r.querySelector(s);

  const STATUS_BADGE = {
    new: "new", in_progress: "ok", waiting_info: "neutral",
    resolved: "ok", rejected: "neutral", closed: "neutral",
  };

  const DIAL_KEYS = [
    ["1", ""], ["2", "ABC"], ["3", "DEF"],
    ["4", "GHI"], ["5", "JKL"], ["6", "MNO"],
    ["7", "PQRS"], ["8", "TUV"], ["9", "WXYZ"],
    ["*", ""], ["0", "+"], ["#", ""],
  ];

  const CACHE_MS = 30_000;
  const API_ORIGIN = ($('meta[name="mini-api"]')?.content || "").replace(/\/$/, "");
  const API_PREFIX = API_ORIGIN ? `${API_ORIGIN}/api/mini` : "/api/mini";
  const SCRIPT_BASE = (document.querySelector('script[src*="mini.js"]')?.src || "")
    .replace(/\/mini\.js(?:\?.*)?$/, "") || "/static/mini";

  let bootstrap = null;
  let bootstrapAt = 0;
  let ticketsCache = null;
  let ticketsAt = 0;
  let pendingPreset = null;
  let activeSipId = null;
  let phone = null;
  let softphoneMod = null;
  let wakeLock = null;
  let loadingCount = 0;
  let toastTimer = null;
  let currentTab = "home";

  function esc(text) {
    return String(text ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function authHeaders(json = true) {
    if (!tg?.initData) throw new Error("Откройте из Telegram");
    const h = { Authorization: `tma ${tg.initData}` };
    if (json) h["Content-Type"] = "application/json";
    return h;
  }

  const REQUEST_TIMEOUT_MS = 25_000;

  async function request(path, opts = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const res = await fetch(`${API_PREFIX}/${path.replace(/^\//, "")}`, {
        ...opts,
        signal: controller.signal,
        headers: { ...authHeaders(opts.body != null), ...opts.headers },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = data.detail;
        throw new Error(typeof detail === "string" ? detail : res.statusText);
      }
      return data;
    } catch (e) {
      if (e?.name === "AbortError") {
        throw new Error("Сервер не ответил вовремя. Попробуйте ещё раз.");
      }
      throw e;
    } finally {
      clearTimeout(timer);
    }
  }

  function showToast(msg, isError = false) {
    const el = $("#toast");
    el.textContent = msg;
    el.className = "toast" + (isError ? " error" : "");
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, 3200);
  }

  function setLoading(on) {
    loadingCount = Math.max(0, loadingCount + (on ? 1 : -1));
    const loader = $("#loader");
    if (loader) loader.hidden = loadingCount === 0;
  }

  function forceLoadingOff() {
    loadingCount = 0;
    const loader = $("#loader");
    if (loader) loader.hidden = true;
  }

  function formatDuration(sec) {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  async function requestWakeLock() {
    try {
      if ("wakeLock" in navigator) wakeLock = await navigator.wakeLock.request("screen");
    } catch (_) { /* unsupported */ }
  }

  async function releaseWakeLock() {
    try { await wakeLock?.release(); } catch (_) { /* noop */ }
    wakeLock = null;
  }

  function invalidateCache() {
    bootstrap = null;
    bootstrapAt = 0;
    ticketsCache = null;
    ticketsAt = 0;
  }

  async function loadBootstrap(force = false) {
    if (!force && bootstrap && Date.now() - bootstrapAt < CACHE_MS) return bootstrap;
    setLoading(true);
    try {
      bootstrap = await request("bootstrap");
      bootstrapAt = Date.now();
      return bootstrap;
    } finally {
      setLoading(false);
    }
  }

  function applyBootstrap(data) {
    const u = data.user;
    $("#user-greet").textContent = u.first_name ? `Привет, ${u.first_name}` : "Личный кабинет";
    $("#user-id").textContent = u.internal_id;
    $("#home-stats").innerHTML = `
      <div class="stat"><div class="label">SIP активных</div><div class="value">${data.sips_count}</div></div>
      <div class="stat ${data.open_tickets ? "warn" : ""}"><div class="label">Открытых заявок</div><div class="value">${data.open_tickets}</div></div>`;

    const grid = $("#quick-presets");
    grid.innerHTML = (data.quick_presets || []).map((p) =>
      `<button type="button" class="preset-btn" data-preset="${esc(p.id)}">${esc(p.button)}<br><small>${esc(p.label)}</small></button>`
    ).join("");

    const extra = data.extra_presets || [];
    const extraBtn = $("#more-presets-btn");
    const extraEl = $("#extra-presets");
    if (extra.length) {
      extraBtn.hidden = false;
      extraEl.innerHTML = extra.map((p) =>
        `<button type="button" class="preset-btn" data-preset="${esc(p.id)}">${esc(p.button)}</button>`
      ).join("");
    } else {
      extraBtn.hidden = true;
      extraEl.innerHTML = "";
    }

    renderSipList(data.sips || []);
    renderPhonePanel(data.softphone);
  }

  function renderSipList(items) {
    const list = $("#sip-list");
    if (!items.length) {
      list.innerHTML = `<div class="empty">Нет активных SIP.<br>Обратитесь к администратору.</div>`;
      return;
    }
    list.innerHTML = items.map((s) => `
      <button type="button" class="sip-card" data-sip-id="${s.id}" data-action="open-phone">
        <div class="num">${esc(s.sip_number)}</div>
        <div class="meta">${esc(s.description || "Без описания")}${s.open_ticket_id ? ` · заявка #${s.open_ticket_id}` : ""}</div>
      </button>`).join("");
  }

  function renderTickets(items) {
    const list = $("#ticket-list");
    if (!items.length) {
      list.innerHTML = `<div class="empty">Заявок пока нет.<br>Создайте через «Быстрая заявка».</div>`;
      return;
    }
    list.innerHTML = items.map((t) => {
      const cls = STATUS_BADGE[t.status] || "neutral";
      return `<div class="ticket-card">
        <div class="head"><span class="id">#${t.id}</span><span class="badge ${cls}">${esc(t.status_label || t.status)}</span></div>
        <div class="meta ticket-meta">${esc(t.error_label || "—")} · SIP <code>${esc(t.sip_number || "—")}</code></div>
      </div>`;
    }).join("");
  }

  async function loadTickets(force = false) {
    if (!force && ticketsCache && Date.now() - ticketsAt < CACHE_MS) {
      renderTickets(ticketsCache);
      return;
    }
    setLoading(true);
    try {
      const data = await request("tickets");
      ticketsCache = data.items || [];
      ticketsAt = Date.now();
      renderTickets(ticketsCache);
    } finally {
      setLoading(false);
    }
  }

  function renderPhonePanel(softphoneStatus) {
    if (!softphoneStatus) return;
    const callable = (softphoneStatus.lines || []).filter((l) => l.callable);
    const disabled = !softphoneStatus.enabled || !callable.length;
    $("#phone-disabled").hidden = !disabled;
    $("#phone-ui").hidden = disabled;
    if (disabled) return;

    const select = $("#phone-line");
    select.innerHTML = callable.map((l) =>
      `<option value="${l.id}">${esc(l.sip_number)}${l.description ? " — " + esc(l.description) : ""}</option>`
    ).join("");
    if (!activeSipId || !callable.some((l) => l.id === activeSipId)) {
      activeSipId = callable[0].id;
    }
    select.value = String(activeSipId);
  }

  async function switchTab(name) {
    if (name === currentTab) {
      if (name === "tickets") await loadTickets();
      return;
    }
    currentTab = name;
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
    document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === `panel-${name}`));

    if (name === "tickets") await loadTickets();
    if (name === "phone") {
      if (bootstrap?.softphone) renderPhonePanel(bootstrap.softphone);
      else {
        const data = await request("softphone/status");
        renderPhonePanel(data);
      }
    }
    if (name === "sips" && bootstrap?.sips) renderSipList(bootstrap.sips);
  }

  function setRegDot(kind) {
    $("#reg-dot").className = "reg-dot" + (kind ? ` ${kind}` : "");
  }

  function updatePhoneControls(state) {
    const registered = ["registered", "in_call", "calling", "ringing"].includes(state);
    const inCall = ["in_call", "ringing", "incoming", "calling"].includes(state);
    $("#phone-call").disabled = !registered || inCall;
    $("#phone-connect").textContent = registered ? "Отключить" : "Подключить";
    $("#phone-incall").hidden = !inCall;
    $("#phone-actions").hidden = inCall && state !== "registered";
    if (state === "registered" || inCall) setRegDot("ok");
    else if (state === "connecting") setRegDot("warn");
    else if (state === "error") setRegDot("err");
    else setRegDot("");
  }

  function logCallEvent(evt) {
    if (!activeSipId || !evt?.status) return;
    request("softphone/events", {
      method: "POST",
      body: JSON.stringify({
        sip_id: activeSipId,
        direction: evt.direction || "outbound",
        remote_number: evt.remote_number || "unknown",
        status: evt.status,
        duration_ms: evt.duration_ms ?? null,
      }),
    }).catch(() => { /* audit best-effort */ });
  }

  async function ensureSoftphoneModule() {
    if (softphoneMod) return softphoneMod;
    softphoneMod = await import(`${SCRIPT_BASE}/softphone.mjs`);
    return softphoneMod;
  }

  async function ensurePhone() {
    if (phone) return phone;
    const mod = await ensureSoftphoneModule();
    phone = new mod.SipSoftphone({
      onStateChange: (state, detail) => {
        $("#phone-status-text").textContent = detail || state;
        updatePhoneControls(state);
        if (state === "in_call") requestWakeLock();
        if (["registered", "idle", "error"].includes(state)) releaseWakeLock();
      },
      onIncoming: (num) => {
        $("#incoming-number").textContent = num || "—";
        $("#incoming-overlay").hidden = false;
        tg?.HapticFeedback?.notificationOccurred("warning");
      },
      onDuration: (sec) => {
        const el = $("#call-timer");
        el.hidden = false;
        el.textContent = formatDuration(sec);
      },
      onCallEvent: logCallEvent,
    });
    return phone;
  }

  function buildDialpad() {
    $("#dialpad").innerHTML = DIAL_KEYS.map(([digit, sub]) =>
      `<button type="button" class="dial-key" data-digit="${digit}">${digit}${sub ? `<sub>${sub}</sub>` : ""}</button>`
    ).join("");
  }

  async function connectPhone() {
    const sp = await ensurePhone();
    if (sp.isRegistered()) {
      await sp.disconnect();
      $("#call-timer").hidden = true;
      showToast("SIP отключён");
      return;
    }
    activeSipId = Number($("#phone-line").value);
    setLoading(true);
    try {
      const session = await request(`softphone/session/${activeSipId}`);
      await sp.connect(session);
      showToast(`Линия ${session.display_number} подключена`);
      tg?.HapticFeedback?.notificationOccurred("success");
    } catch (e) {
      showToast(e.message, true);
      tg?.HapticFeedback?.notificationOccurred("error");
    } finally {
      setLoading(false);
    }
  }

  async function placeCall() {
    const num = $("#phone-number").value.trim();
    if (!num) {
      showToast("Введите номер", true);
      return;
    }
    try {
      (await ensurePhone()).call(num);
      tg?.HapticFeedback?.impactOccurred("medium");
    } catch (e) {
      showToast(e.message, true);
    }
  }

  function openSipPicker(presetId) {
    const items = bootstrap?.sips || [];
    if (!items.length) {
      showToast("Нет активных SIP", true);
      return;
    }
    if (items.length === 1) {
      createTicket(items[0].id, presetId);
      return;
    }
    pendingPreset = presetId;
    const overlay = document.createElement("div");
    overlay.className = "sip-picker";
    overlay.innerHTML = `<div class="sip-picker-inner">
      <h3>Выберите SIP</h3>
      <div class="list" id="picker-sips"></div>
      <button type="button" class="btn secondary block" data-action="picker-cancel">Отмена</button>
    </div>`;
    document.body.appendChild(overlay);
    $("#picker-sips", overlay).innerHTML = items.map((s) =>
      `<button type="button" class="sip-card" data-action="picker-sip" data-sip-id="${s.id}">
        <div class="num">${esc(s.sip_number)}</div>
      </button>`
    ).join("");
    overlay.querySelector("[data-action='picker-cancel']").onclick = () => {
      overlay.remove();
      pendingPreset = null;
    };
  }

  let creatingTicket = false;

  async function createTicket(sipId, presetId) {
    if (creatingTicket) return;
    creatingTicket = true;
    setLoading(true);
    try {
      const res = await request("tickets", {
        method: "POST",
        body: JSON.stringify({ sip_id: sipId, preset_id: presetId }),
      });
      showToast(`Заявка #${res.ticket_id} создана`);
      tg?.HapticFeedback?.notificationOccurred("success");
      invalidateCache();
      ticketsCache = null;
      ticketsAt = 0;
      await loadBootstrap(true);
      applyBootstrap(bootstrap);
      await switchTab("tickets");
    } catch (e) {
      showToast(e.message, true);
      tg?.HapticFeedback?.notificationOccurred("error");
    } finally {
      creatingTicket = false;
      forceLoadingOff();
    }
  }

  function onAppClick(e) {
    const presetBtn = e.target.closest("[data-preset]");
    if (presetBtn) {
      openSipPicker(presetBtn.dataset.preset);
      return;
    }
    const pickerSip = e.target.closest("[data-action='picker-sip']");
    if (pickerSip && pendingPreset) {
      pickerSip.closest(".sip-picker")?.remove();
      createTicket(Number(pickerSip.dataset.sipId), pendingPreset);
      pendingPreset = null;
      return;
    }
    const openPhone = e.target.closest("[data-action='open-phone']");
    if (openPhone) {
      activeSipId = Number(openPhone.dataset.sipId);
      switchTab("phone").then(() => {
        if ($("#phone-line")) $("#phone-line").value = String(activeSipId);
      });
    }
  }

  function onDialpadClick(e) {
    const key = e.target.closest("[data-digit]");
    if (!key) return;
    const input = $("#phone-number");
    input.value += key.dataset.digit;
    if (phone?.state === "in_call") phone.sendDtmf(key.dataset.digit);
    tg?.HapticFeedback?.impactOccurred("light");
  }

  async function init() {
    if (!tg) {
      showToast("Откройте приложение из Telegram", true);
      return;
    }
    tg.ready();
    tg.expand();
    tg.setHeaderColor("#222222");
    tg.setBackgroundColor("#1c1c1c");
    if (tg.themeParams?.button_color) {
      document.documentElement.style.setProperty("--tg-theme-button-color", tg.themeParams.button_color);
    }

    buildDialpad();
    document.getElementById("tabs").addEventListener("click", (e) => {
      const tab = e.target.closest(".tab");
      if (tab) switchTab(tab.dataset.tab);
    });
    document.querySelector(".panels").addEventListener("click", onAppClick);
    $("#dialpad").addEventListener("click", onDialpadClick);

    $("#more-presets-btn")?.addEventListener("click", () => {
      const el = $("#extra-presets");
      const hidden = el.hasAttribute("hidden");
      el.toggleAttribute("hidden", !hidden);
      $("#more-presets-btn").textContent = hidden ? "Скрыть доп. типы" : "Ещё типы ошибок";
    });

    $("#phone-connect")?.addEventListener("click", connectPhone);
    $("#phone-call")?.addEventListener("click", placeCall);
    $("#phone-hangup")?.addEventListener("click", async () => {
      if (phone) phone.hangup();
      $("#incoming-overlay").hidden = true;
      $("#call-timer").hidden = true;
    });
    $("#phone-mute")?.addEventListener("click", async (e) => {
      const muted = (await ensurePhone()).toggleMute();
      e.currentTarget.classList.toggle("active", muted);
      e.currentTarget.textContent = muted ? "🔈" : "🔇";
    });
    $("#phone-backspace")?.addEventListener("click", () => {
      const input = $("#phone-number");
      input.value = input.value.slice(0, -1);
    });
    $("#incoming-answer")?.addEventListener("click", async () => {
      (await ensurePhone()).answer();
      $("#incoming-overlay").hidden = true;
      tg?.HapticFeedback?.notificationOccurred("success");
    });
    $("#incoming-decline")?.addEventListener("click", async () => {
      if (phone) phone.hangup();
      $("#incoming-overlay").hidden = true;
    });
    $("#phone-line")?.addEventListener("change", async () => {
      if (phone?.isRegistered()) {
        await phone.disconnect();
        $("#call-timer").hidden = true;
        showToast("Линия сменена — нажмите «Подключить»");
      }
      activeSipId = Number($("#phone-line").value);
    });

    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible" && phone?.ua && !phone.isRegistered()) {
        phone.ua.register();
      }
    });

    try {
      await loadBootstrap();
      applyBootstrap(bootstrap);
    } catch (e) {
      showToast(e.message, true);
    } finally {
      forceLoadingOff();
    }
  }

  init();
})();
