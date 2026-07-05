/* SIP CRM admin panel */
(() => {
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];

  const STATUS_RU = {
    new: "Новая", in_progress: "В работе", waiting_info: "Ожидание",
    resolved: "Решена", rejected: "Отклонена", closed: "Закрыта",
    active: "Активен", frozen: "Заморожен", disabled: "Отключён",
  };
  const statusLabel = (s) => STATUS_RU[s] || s;

  const ALLOWED_TRANSITIONS = {
    new: ["in_progress", "waiting_info", "resolved", "rejected"],
    in_progress: ["waiting_info", "resolved", "rejected"],
    waiting_info: ["in_progress", "resolved", "rejected"],
    resolved: ["closed"],
    rejected: [],
    closed: [],
  };

  function allowedNextStatuses(current) {
    return ALLOWED_TRANSITIONS[current] || [];
  }

  function canTransitionTo(current, next) {
    if (current === next) return true;
    return allowedNextStatuses(current).includes(next);
  }

  let modalHandler = null;
  let sdTickets = [];
  let sdSelectedId = null;
  let sdFilter = "all";
  let sdSummary = null;
  let sdKnownIds = new Set();
  let sdActionBusy = false;
  let sdAutoTimer = null;
  let navStats = {};
  let groupFilter = "all";
  let groupSearch = "";
  let groupsCache = [];
  let dashTab = "live";
  let dashStatsCache = null;

  function formatDate(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
  }

  function navigateSection(name) {
    const btn = $(`.nav-item[data-section="${name}"]`);
    if (btn) btn.click();
    else loadSection(name);
  }

  function showToast(msg, isError = false) {
    const toast = $("#toast");
    if (!toast) return;
    toast.textContent = msg;
    toast.className = "toast show" + (isError ? " error" : "");
    setTimeout(() => toast.classList.remove("show"), 3200);
  }

  function formatApiError(data, fallback) {
    const d = data?.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => x.msg || JSON.stringify(x)).join("; ");
    return fallback;
  }

  function goToLogin() {
    if (window.SIPCRM) {
      window.location.replace(SIPCRM.loginUrl());
      return;
    }
    const u = new URL(window.location.href);
    const base = u.pathname.replace(/\/?login\/?$/, "").replace(/\/$/, "") || "";
    u.pathname = (base || "") + "/login";
    u.search = "";
    u.hash = "";
    window.location.replace(u.toString());
  }

  function goToAppHome() {
    if (window.SIPCRM) {
      window.location.replace(SIPCRM.homeUrl());
      return;
    }
    const u = new URL(window.location.href);
    u.pathname = u.pathname.replace(/\/?login\/?$/, "") || "/";
    if (!u.pathname.endsWith("/")) u.pathname += "/";
    u.search = "";
    u.hash = "";
    window.location.replace(u.toString());
  }

  async function api(path, opts = {}) {
    const url = window.SIPCRM
      ? SIPCRM.api(String(path).replace(/^\//, ""))
      : "/api" + path;
    const res = await fetch(url, {
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...opts.headers },
      ...opts,
    });
    if (res.status === 401) {
      goToLogin();
      throw new Error("Unauthorized");
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(formatApiError(data, res.statusText));
    return data;
  }

  function badge(text, kind = "neutral") {
    return `<span class="badge ${kind}">${text}</span>`;
  }

  function slaInfo(createdAt, breach) {
    if (breach === true) return { label: ">3 мин", cls: "danger" };
    if (!createdAt) return { label: "—", cls: "ok" };
    const mins = Math.floor((Date.now() - new Date(createdAt)) / 60000);
    if (mins < 2) return { label: `${mins || "<1"} мин`, cls: "ok" };
    if (mins < 3) return { label: `${mins} мин`, cls: "warn" };
    return { label: `${mins} мин`, cls: "danger" };
  }

  function assigneeLabel(a) {
    if (!a) return null;
    if (a.username) return `@${a.username}`;
    return a.internal_id || a.first_name || `#${a.id}`;
  }

  function filterSdTickets() {
    if (sdFilter === "all") return sdTickets;
    if (sdFilter === "sla_breach") return sdTickets.filter((t) => t.sla_breach);
    return sdTickets.filter((t) => t.status === sdFilter);
  }

  function updateSdChipCounts(summary) {
    const counts = {
      all: summary?.total ?? sdTickets.length,
      new: summary?.new ?? sdTickets.filter((t) => t.status === "new").length,
      in_progress: summary?.in_progress ?? sdTickets.filter((t) => t.status === "in_progress").length,
      waiting_info: summary?.waiting_info ?? sdTickets.filter((t) => t.status === "waiting_info").length,
      sla_breach: summary?.sla_breach ?? sdTickets.filter((t) => t.sla_breach).length,
    };
    $$("[data-sd-count]").forEach((el) => {
      const key = el.dataset.sdCount;
      if (key in counts) el.textContent = counts[key];
    });
  }

  function renderSdSummary(summary) {
    const el = $("#sd-summary");
    if (!el || !summary?.total) {
      el?.setAttribute("hidden", "");
      if (el) el.innerHTML = "";
      return;
    }
    el.removeAttribute("hidden");
    el.innerHTML = `
      <div class="sd-stat"><strong>${summary.total}</strong> в очереди</div>
      <div class="sd-stat"><strong>${summary.new}</strong> новых</div>
      <div class="sd-stat"><strong>${summary.in_progress}</strong> в работе</div>
      <div class="sd-stat"><strong>${summary.waiting_info}</strong> ожидание</div>
      ${summary.sla_breach ? `<div class="sd-stat alert"><strong>${summary.sla_breach}</strong> вне SLA (&gt;3 мин)</div>` : ""}`;
  }

  function clickSdAction(act) {
    $(`#sd-detail-actions [data-act="${act}"]`)?.click();
  }

  function selectNextNewTicket() {
    const next = sdTickets.find((t) => t.status === "new");
    if (!next) {
      showToast("Нет новых заявок");
      return;
    }
    sdSelectedId = next.id;
    sdFilter = "new";
    $$(".chip[data-sd-filter]").forEach((c) => c.classList.toggle("active", c.dataset.sdFilter === "new"));
    renderQueue();
    loadTicketDetail(next.id);
  }

  function renderTicketDetailHtml(t) {
    const sla = slaInfo(t.created_at, t.sla_breach);
    const statusKind = { new: "warn", in_progress: "ok", waiting_info: "neutral" };
    const agent = assigneeLabel(t.assigned_to);
    return `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
        <h2 style="font-size:1.15rem;color:var(--accent)">Заявка #${t.id}</h2>
        <span class="sla ${sla.cls}">⏱ ${sla.label}</span>
      </div>
      <div class="detail-grid">
        <div class="detail-field"><label>Статус</label><span>${badge(t.status_label || statusLabel(t.status), statusKind[t.status] || "neutral")}</span></div>
        <div class="detail-field"><label>Оператор</label><span>${agent || "—"}</span></div>
        <div class="detail-field"><label>Источник</label><span>${t.source_label || t.source || "—"}</span></div>
        <div class="detail-field"><label>SIP</label><span><code>${t.sip_number || "—"}</code></span></div>
        <div class="detail-field"><label>Ошибка</label><span>${t.error_label || "—"}</span></div>
        <div class="detail-field"><label>Группа</label><span>${t.group_name || t.group_chat_id || "—"}</span></div>
        <div class="detail-field"><label>Инициатор</label><span><code>${t.initiator_telegram_id || "—"}</code></span></div>
        <div class="detail-field"><label>Клиент</label><span>${t.user?.internal_id || "—"}</span></div>
        <div class="detail-field"><label>Создана</label><span>${formatDate(t.created_at)}</span></div>
      </div>
      <div class="detail-field"><label>Описание</label><span>${t.description || "—"}</span></div>
      ${t.history?.length ? `<div class="timeline"><h3>История</h3>${t.history.map((h) =>
        `<div class="timeline-item"><time>${formatDate(h.created_at)}</time><br>${h.old_status_label || h.old_status || "—"} → <b>${h.new_status_label || h.new_status}</b>${h.comment ? ` · ${h.comment}` : ""}</div>`
      ).join("")}</div>` : ""}`;
  }

  function ticketActionButtons(t) {
    const canTake = t.status === "new";
    const canResume = t.status === "waiting_info";
    const canResolve = canTransitionTo(t.status, "resolved") && t.status !== "resolved";
    const canReject = canTransitionTo(t.status, "rejected");
    const canWait = canTransitionTo(t.status, "waiting_info");
    return `
      ${canTake ? `<button type="button" class="btn secondary" data-act="take">🔧 Взять</button>` : ""}
      ${canResume ? `<button type="button" class="btn secondary" data-act="in_progress">▶ В работу</button>` : ""}
      ${canWait ? `<button type="button" class="btn secondary" data-act="waiting_info">⏳ Ожидание</button>` : ""}
      ${canResolve ? `<button type="button" class="btn success" data-act="resolved">✅ Решено</button>` : ""}
      ${canReject ? `<button type="button" class="btn danger" data-act="rejected">✗ Отклонить</button>` : ""}
      ${t.is_service_desk && t.is_open ? `<button type="button" class="btn secondary sm" data-act="goto-sd">🚨 В колл-центр</button>` : ""}`;
  }

  function openRejectModal(id, { onRefresh, onFinalized } = {}) {
    openModal(`Отклонить заявку #${id}`, [
      {
        label: "Причина отклонения",
        name: "comment",
        tag: "textarea",
        attrs: 'rows="3" required placeholder="Обязательно укажите причину"',
      },
    ], async (fd) => {
      const comment = String(fd.get("comment") || "").trim();
      if (!comment) throw new Error("Укажите причину отклонения");
      await applyTicketAction(id, "rejected", `Отклонено (Web CRM): ${comment}`, async () => {
        if (onFinalized) await onFinalized();
        else if (onRefresh) await onRefresh();
      });
    });
  }

  async function applyTicketAction(id, status, comment, onDone) {
    const res = await api(`/tickets/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status, comment }),
    });
    const labels = { resolved: "решена", rejected: "отклонена", waiting_info: "ожидание инфо" };
    showToast(res.noop ? "Без изменений" : `Заявка ${labels[status] || "обновлена"}${res.notified === false ? " (уведомление не отправлено)" : ""}`);
    if (onDone) await onDone();
    return res;
  }

  function bindTicketActions(id, actionsEl, { onRefresh, onResolved, onFinalized } = {}) {
    if (!actionsEl) return;
    const finalize = onFinalized || onResolved;
    actionsEl.querySelectorAll("[data-act]").forEach((btn) => {
      btn.onclick = async () => {
        if (sdActionBusy) return;
        const act = btn.dataset.act;
        try {
          if (act === "goto-sd") {
            navigateSection("service-desk");
            sdSelectedId = id;
            return;
          }
          if (act === "take") {
            sdActionBusy = true;
            const res = await api(`/tickets/${id}/take`, { method: "POST" });
            showToast(res.noop ? "Уже в работе" : "Взята в работу");
            if (onRefresh) await onRefresh();
            return;
          }
          if (act === "rejected") {
            openRejectModal(id, { onRefresh, onFinalized: finalize });
            return;
          }
          if (act === "resolved" && !confirm(`Решить заявку #${id}?`)) return;
          sdActionBusy = true;
          const comments = {
            resolved: "Решено (Web CRM)",
            waiting_info: "Ожидание информации (Web CRM)",
            in_progress: "Возобновлено (Web CRM)",
          };
          await applyTicketAction(id, act, comments[act] || null, async () => {
            if ((act === "resolved" || act === "rejected") && finalize) await finalize();
            else if (onRefresh) await onRefresh();
          });
        } catch (e) { showToast(e.message, true); }
        finally { sdActionBusy = false; }
      };
    });
  }

  function openModal(title, fields, onSubmit) {
    $("#modal-title").textContent = title;
    $("#modal-form").innerHTML = fields.map((f) =>
      `<label>${f.label}<${f.tag || "input"} name="${f.name}" ${f.attrs || ""}${f.tag ? ">" + (f.options || "") + `</${f.tag}>` : "/>"}`
    ).join("");
    modalHandler = onSubmit;
    $("#modal").showModal();
  }

  function updateNavBadges() {
    const sd = navStats.service_desk_active ?? 0;
    const sla = navStats.sla_breach ?? 0;
    const grp = navStats.groups_pending ?? 0;
    const elSd = $("#nav-badge-sd");
    const elGrp = $("#nav-badge-groups");
    if (elSd) {
      elSd.textContent = sd;
      elSd.className = "nav-badge" + (sla > 0 ? " alert" : sd > 0 ? " warn" : "");
      elSd.hidden = sd === 0;
    }
    if (elGrp) {
      elGrp.textContent = grp;
      elGrp.hidden = grp === 0;
    }
  }

  function setSyncTime() {
    const el = $("#topbar-sync");
    if (el) el.textContent = "Обновлено " + new Date().toLocaleTimeString("ru-RU");
  }

  function switchDashTab(tab) {
    dashTab = tab;
    $$(".dash-tab").forEach((b) => b.classList.toggle("active", b.dataset.dashTab === tab));
    $("#dash-panel-live")?.toggleAttribute("hidden", tab !== "live");
    $("#dash-panel-analytics")?.toggleAttribute("hidden", tab !== "analytics");
    if (tab === "analytics") {
      if (dashStatsCache) renderDashAnalyticsData(dashStatsCache);
      else loadDashAnalytics().catch((e) => showToast(e.message, true));
    }
  }

  function renderDashHero(d, stats) {
    const el = $("#dash-hero-kpis");
    if (!el) return;
    const rate = stats?.tickets?.resolution_rate_pct;
    el.innerHTML = `
      <div class="dash-kpi ${d.sla_breach ? "alert" : "ok"}">
        <div class="kpi-label">Колл-центр</div>
        <div class="kpi-value">${d.service_desk_active ?? 0}</div>
      </div>
      <div class="dash-kpi ${d.sla_breach ? "alert" : ""}">
        <div class="kpi-label">SLA &gt; 3 мин</div>
        <div class="kpi-value">${d.sla_breach ?? 0}</div>
      </div>
      <div class="dash-kpi">
        <div class="kpi-label">Открытых заявок</div>
        <div class="kpi-value">${d.tickets_open ?? 0}</div>
      </div>
      <div class="dash-kpi ok">
        <div class="kpi-label">% решения (${stats?.period_days || 30} дн.)</div>
        <div class="kpi-value">${rate != null ? rate + "%" : "—"}</div>
      </div>`;
  }

  function renderDashLiveCards(d) {
    const breach = d.sla_breach ?? 0;
    $("#dash-cards").innerHTML = `
      <div class="card featured clickable" data-goto="service-desk">
        <div class="label">🚨 Колл-центр</div>
        <div class="value ${breach ? "danger" : d.service_desk_active ? "warn" : "ok"}">${d.service_desk_active ?? 0}</div>
      </div>
      <div class="card clickable" data-goto="tickets">
        <div class="label">Открытых заявок</div>
        <div class="value ${d.tickets_open ? "warn" : "ok"}">${d.tickets_open ?? 0}</div>
      </div>
      <div class="card">
        <div class="label">Новые / в работе</div>
        <div class="value" style="font-size:1.2rem">${d.tickets_new ?? 0} / ${d.tickets_in_progress ?? 0}</div>
      </div>
      <div class="card">
        <div class="label">Ожидание инфо</div>
        <div class="value">${d.tickets_waiting_info ?? 0}</div>
      </div>
      <div class="card clickable span-4" data-goto="groups">
        <div class="label">Группы · активные / ожидают / заморожены</div>
        <div class="value" style="font-size:1.15rem">${d.groups_active ?? 0} · ${d.groups_pending ?? 0} · ${d.groups_frozen ?? 0}</div>
      </div>
      <div class="card clickable" data-goto="sips">
        <div class="label">SIP активных</div>
        <div class="value ok">${d.sips_active ?? 0}</div>
      </div>
      <div class="card clickable" data-goto="users">
        <div class="label">Пользователей</div>
        <div class="value">${d.users_total}</div>
      </div>
      <div class="card clickable" data-dash-tab="analytics">
        <div class="label">Аналитика SIP</div>
        <div class="value" style="font-size:1.05rem">📈 Отчёты</div>
      </div>
      <div class="card">
        <div class="label">Тест-меню бота</div>
        <div class="value" style="font-size:1rem">${d.test_mode ? "ВКЛ" : "ВЫКЛ"}</div>
      </div>`;
    $$("[data-goto]", $("#dash-cards")).forEach((c) => {
      c.onclick = () => $(`[data-section="${c.dataset.goto}"]`)?.click();
    });
    $$("[data-dash-tab]", $("#dash-cards")).forEach((c) => {
      c.onclick = () => switchDashTab(c.dataset.dashTab);
    });
  }

  async function loadDashAnalytics() {
    const days = Number($("#dash-days")?.value || 30);
    const exportBtn = $("#dash-export-btn");
    if (exportBtn) exportBtn.href = SIPCRM.api(`stats/sip-work/export?days=${days}`);
    $("#dash-analytics-cards").innerHTML = `<div class="card"><div class="label">Загрузка…</div><div class="value loading-pulse">—</div></div>`;
    const r = await api(`/stats/sip-work?days=${days}`);
    dashStatsCache = r;
    renderDashAnalyticsData(r);
    setSyncTime();
  }

  function renderDashAnalyticsData(r) {
    if (!r) return;
    const t = r.tickets;
    const s = r.sips;
    $("#dash-analytics-cards").innerHTML = `
      <div class="card"><div class="label">SIP активных</div><div class="value ok">${s.active}</div></div>
      <div class="card"><div class="label">SIP всего</div><div class="value">${s.total}</div></div>
      <div class="card"><div class="label">Заявок за ${r.period_days} дн.</div><div class="value">${t.created_in_period}</div></div>
      <div class="card"><div class="label">Решено за период</div><div class="value ok">${t.resolved_in_period}</div></div>
      <div class="card"><div class="label">Среднее время решения</div><div class="value" style="font-size:1.05rem">${t.avg_resolution_human || "—"}</div></div>
      <div class="card"><div class="label">Открыто сейчас</div><div class="value ${t.open ? "warn" : "ok"}">${t.open}</div></div>
      <div class="card"><div class="label">% решения</div><div class="value">${t.resolution_rate_pct != null ? t.resolution_rate_pct + "%" : "—"}</div></div>
      <div class="card"><div class="label">SIP отключено</div><div class="value danger">${s.disabled}</div></div>`;
    renderBarList($("#dash-errors"), r.by_error_type.map((x) => ({ label: x.label, count: x.count })));
    renderBarList($("#dash-sources"), r.by_source.map((x) => ({ label: x.label, count: x.count })));
    $("#dash-top-sips").innerHTML = r.top_sips.map((row) =>
      `<tr><td><code>${row.sip_number}</code></td><td>${row.total}</td><td>${row.open ? badge(row.open, "warn") : "0"}</td></tr>`
    ).join("") || `<tr><td colspan="3">Нет заявок</td></tr>`;
    $("#dash-open-sips").innerHTML = r.sips_with_open_tickets.map((row) =>
      `<tr><td><code>${row.sip_number}</code></td><td>${badge(row.open, "warn")}</td></tr>`
    ).join("") || `<tr><td colspan="2">Нет открытых заявок</td></tr>`;
    $("#dash-agents").innerHTML = r.agents.map((row) =>
      `<tr><td>${row.name}</td><td><code>${row.internal_id || "—"}</code></td><td>${row.taken}</td><td>${row.resolved}</td></tr>`
    ).join("") || `<tr><td colspan="4">Нет данных по агентам</td></tr>`;
    $("#dash-daily").innerHTML = [...r.daily].reverse().map((row) =>
      `<tr><td>${row.date}</td><td>${row.created}</td><td>${row.resolved}</td></tr>`
    ).join("") || `<tr><td colspan="3">Нет данных</td></tr>`;
    const hero = navStats;
    if (hero) renderDashHero(hero, r);
  }

  async function loadDashboard() {
    dashStatsCache = null;
    const days = Number($("#dash-days")?.value || 30);
    const [d, stats] = await Promise.all([
      api("/dashboard"),
      api(`/stats/sip-work?days=${days}`).catch(() => null),
    ]);
    navStats = d;
    dashStatsCache = stats;
    updateNavBadges();
    renderDashHero(d, stats);
    renderDashLiveCards(d);
    if (dashTab === "analytics") {
      if (stats) renderDashAnalyticsData(stats);
      else await loadDashAnalytics();
    }
    setSyncTime();
  }

  function renderBarList(el, items) {
    if (!el) return;
    if (!items?.length) {
      el.innerHTML = `<p class="hint">Нет данных за выбранный период</p>`;
      return;
    }
    const max = Math.max(...items.map((i) => i.count));
    el.innerHTML = items.map((i) => `
      <div class="bar-row">
        <span class="bar-label">${i.label}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${max ? Math.round(i.count / max * 100) : 0}%"></div></div>
        <span class="bar-value">${i.count}</span>
      </div>`).join("");
  }

  async function loadStats() {
    switchDashTab("analytics");
    await loadDashAnalytics();
  }

  async function loadServiceDesk() {
    showQueueLoading();
    const data = await api("/tickets/service-desk");
    const items = data.items || [];
    const summary = data.summary || null;
    const prevIds = sdKnownIds;
    sdKnownIds = new Set(items.map((t) => t.id));
    const brandNew = items.filter((t) => t.status === "new" && !prevIds.has(t.id));
    if (brandNew.length && prevIds.size) {
      showToast(brandNew.length === 1 ? `Новая заявка #${brandNew[0].id}` : `Новых заявок: ${brandNew.length}`);
    }
    sdTickets = items;
    sdSummary = summary;
    navStats.service_desk_active = summary?.total ?? items.length;
    navStats.sla_breach = summary?.sla_breach ?? items.filter((t) => t.sla_breach).length;
    updateNavBadges();
    updateSdChipCounts(summary);
    renderSdSummary(summary);
    const filtered = filterSdTickets();
    if (!sdSelectedId && filtered.length) sdSelectedId = filtered[0].id;
    else if (sdSelectedId && !sdTickets.some((t) => t.id === sdSelectedId)) sdSelectedId = filtered[0]?.id ?? null;
    renderQueue();
    if (sdSelectedId) await loadTicketDetail(sdSelectedId, false);
    else {
      $("#sd-detail-body").innerHTML = `<div class="empty-state"><div class="empty-icon">👈</div><p>Выберите заявку из очереди</p></div>`;
      $("#sd-detail-actions").innerHTML = "";
    }
    setSyncTime();
    $("#sd-queue-count").textContent = summary?.total ?? items.length;
  }

  function renderQueue() {
    const filtered = filterSdTickets();
    const list = $("#sd-queue");
    if (!filtered.length) {
      list.innerHTML = `<div class="empty-state"><div class="empty-icon">✅</div><p>Нет активных заявок</p></div>`;
      return;
    }
    list.innerHTML = filtered.map((t) => {
      const sla = slaInfo(t.created_at, t.sla_breach);
      const active = t.id === sdSelectedId ? " active" : "";
      const breach = t.sla_breach ? " sla-breach" : "";
      const agent = assigneeLabel(t.assigned_to);
      return `<div class="queue-item${active}${breach}" data-id="${t.id}">
        <div class="queue-item-top">
          <span class="queue-item-id">#${t.id}</span>
          <span class="sla ${sla.cls}">${sla.label}</span>
        </div>
        <div class="queue-item-error">${t.error_label || "—"}</div>
        <div class="queue-item-meta">
          <span class="queue-item-sip">${t.sip_number || "—"}</span>
          <span>${badge(statusLabel(t.status), t.status === "new" ? "warn" : t.status === "waiting_info" ? "neutral" : "ok")}</span>
        </div>
        ${agent ? `<div class="queue-item-assignee">👤 ${agent}</div>` : ""}
      </div>`;
    }).join("");
    $$(".queue-item", list).forEach((el) => {
      el.onclick = () => {
        sdSelectedId = Number(el.dataset.id);
        renderQueue();
        loadTicketDetail(sdSelectedId);
      };
    });
  }

  async function loadTicketDetail(id, scroll = true) {
    const panel = $("#sd-detail-body");
    const actions = $("#sd-detail-actions");
    try {
      const t = await api(`/tickets/${id}`);
      panel.innerHTML = renderTicketDetailHtml(t);
      actions.innerHTML = ticketActionButtons(t) + `<button type="button" class="btn secondary sm" id="sd-refresh-detail">↻</button>`;
      const onFinalized = async () => {
        sdSelectedId = null;
        await loadServiceDesk();
        panel.innerHTML = `<div class="empty-state"><div class="empty-icon">✅</div><p>Заявка #${id} закрыта</p></div>`;
        actions.innerHTML = "";
      };
      bindTicketActions(id, actions, {
        onRefresh: async () => { await loadServiceDesk(); await loadTicketDetail(id, false); },
        onFinalized,
      });
      $("#sd-refresh-detail")?.addEventListener("click", () => loadTicketDetail(id));
      if (scroll) panel.scrollTop = 0;
    } catch (e) {
      showToast(e.message, true);
    }
  }

  async function openTicketDialog(id) {
    const dlg = $("#ticket-dialog");
    const body = $("#ticket-dialog-body");
    const actions = $("#ticket-dialog-actions");
    $("#ticket-dialog-title").textContent = `Заявка #${id}`;
    body.innerHTML = `<p class="loading-pulse">Загрузка…</p>`;
    actions.innerHTML = "";
    dlg.showModal();
    try {
      const t = await api(`/tickets/${id}`);
      body.innerHTML = renderTicketDetailHtml(t);
      actions.innerHTML = ticketActionButtons(t);
      bindTicketActions(id, actions, {
        onRefresh: async () => {
          const fresh = await api(`/tickets/${id}`);
          body.innerHTML = renderTicketDetailHtml(fresh);
          actions.innerHTML = ticketActionButtons(fresh);
          bindTicketActions(id, actions, { onRefresh: () => openTicketDialog(id) });
          loadTickets($("#ticket-filter")?.value || "");
          loadDashboard().catch(() => {});
        },
        onResolved: () => { dlg.close(); loadTickets($("#ticket-filter")?.value || ""); },
      });
    } catch (e) {
      body.innerHTML = `<p class="hint">${e.message}</p>`;
    }
  }

  async function loadUsers(search = "") {
    const q = search ? "?search=" + encodeURIComponent(search) : "";
    const { items } = await api("/users" + q);
    $("#users-body").innerHTML = items.map((u) => `
      <tr>
        <td>${u.id}</td><td><code>${u.telegram_id}</code></td><td><code>${u.internal_id}</code></td>
        <td>${u.first_name || "—"} ${u.username ? "(@" + u.username + ")" : ""}</td>
        <td>${u.role}</td>
        <td>${u.is_banned ? badge("Бан", "danger") : badge("OK", "ok")}</td>
        <td>
          ${u.is_banned ? `<button class="btn sm secondary" data-unban="${u.id}">Разбан</button>` : `<button class="btn sm danger" data-ban="${u.id}">Бан</button>`}
          <button class="btn sm secondary" data-role="${u.id}">Роль</button>
        </td>
      </tr>`).join("") || "<tr><td colspan='7'>Нет данных</td></tr>";

    $$("[data-ban]", $("#users-body")).forEach((btn) => btn.onclick = () => openModal("Блокировка", [{ label: "Причина", name: "reason", attrs: "required" }],
      async (fd) => { await api("/users/" + btn.dataset.ban + "/ban", { method: "POST", body: JSON.stringify({ reason: fd.get("reason") }) }); showToast("Заблокирован"); loadUsers(search); }));
    $$("[data-unban]", $("#users-body")).forEach((btn) => btn.onclick = async () => { await api("/users/" + btn.dataset.unban + "/unban", { method: "POST" }); showToast("Разблокирован"); loadUsers(search); });
    $$("[data-role]", $("#users-body")).forEach((btn) => btn.onclick = () => openModal("Смена роли", [{ label: "Роль", name: "role", tag: "select", attrs: "required", options: ["user","support","admin","superadmin"].map((r) => `<option value="${r}">${r}</option>`).join("") }],
      async (fd) => { await api("/users/" + btn.dataset.role + "/role", { method: "POST", body: JSON.stringify({ role: fd.get("role") }) }); showToast("Роль изменена"); loadUsers(search); }));
  }

  async function loadSips() {
    const search = $("#sip-search")?.value.trim() || "";
    const status = $("#sip-status-filter")?.value || "";
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    const q = params.toString() ? `?${params}` : "";
    const { items } = await api("/sips" + q);
    const statusKind = { active: "ok", frozen: "warn", disabled: "danger" };
    $("#sips-body").innerHTML = items.map((s) => {
      let actions = "";
      if (s.status === "disabled") actions = `<button class="btn sm success" data-enable="${s.id}">Активировать</button>`;
      else if (s.status === "active") actions = `<button class="btn sm danger" data-disable="${s.id}">Отключить</button>`;
      actions += ` <button class="btn sm secondary" data-creds="${s.id}">Auth</button>`;
      const openBadge = s.open_tickets ? badge(s.open_tickets, "warn") : "0";
      const credBadge = s.has_credentials ? badge("SIP auth", "ok") : badge("нет auth", "warn");
      return `<tr>
        <td><code>${s.sip_number}</code></td>
        <td>${s.user ? s.user.internal_id + " (" + s.user.telegram_id + ")" : "—"}</td>
        <td>${s.description || "—"}</td>
        <td>${badge(statusLabel(s.status), statusKind[s.status] || "neutral")} ${credBadge}</td>
        <td>${openBadge}</td>
        <td>${actions || "—"}</td></tr>`;
    }).join("") || "<tr><td colspan='6'>Нет SIP</td></tr>";
    $$("[data-disable]", $("#sips-body")).forEach((btn) => btn.onclick = async () => {
      if (!confirm("Отключить SIP?")) return;
      await api("/sips/" + btn.dataset.disable + "/disable", { method: "POST" });
      showToast("SIP отключён"); loadSips();
    });
    $$("[data-enable]", $("#sips-body")).forEach((btn) => btn.onclick = async () => {
      if (!confirm("Активировать SIP?")) return;
      await api("/sips/" + btn.dataset.enable + "/enable", { method: "POST" });
      showToast("SIP активирован"); loadSips();
    });
    $$("[data-creds]", $("#sips-body")).forEach((btn) => btn.onclick = () => {
      const id = btn.dataset.creds;
      openModal("SIP credentials (Device)", [
        { label: "SIP login", name: "auth_username", attrs: 'placeholder="username Device"' },
        { label: "SIP password", name: "auth_password", attrs: 'type="password" required autocomplete="new-password"' },
      ], async (fd) => {
        await api("/sips/" + id + "/credentials", {
          method: "PATCH",
          body: JSON.stringify({
            auth_username: fd.get("auth_username")?.trim() || null,
            auth_password: fd.get("auth_password"),
          }),
        });
        showToast("SIP auth сохранён"); loadSips();
      });
    });
  }

  async function loadTickets(status = "") {
    const q = status ? "?status=" + encodeURIComponent(status) : "";
    const { items } = await api("/tickets" + q);
    const statusKind = { new: "warn", in_progress: "ok", resolved: "ok", rejected: "danger", waiting_info: "neutral", closed: "neutral" };
    $("#tickets-body").innerHTML = items.map((t) => `
      <tr class="clickable-row" data-ticket-row="${t.id}">
        <td>${t.id}</td>
        <td>${badge(t.status_label || statusLabel(t.status), statusKind[t.status] || "neutral")}</td>
        <td>${t.error_label || "—"}</td>
        <td>${t.source_label || t.source || "—"}</td>
        <td><code>${t.sip_number || "—"}</code></td>
        <td>${t.user?.internal_id || "—"}</td>
        <td>${formatDate(t.created_at)}</td>
        <td>
          <button class="btn sm secondary" data-ticket-view="${t.id}">Открыть</button>
          <button class="btn sm secondary" data-ticket="${t.id}" data-cur="${t.status}">Статус</button>
        </td>
      </tr>`).join("") || "<tr><td colspan='8'>Нет заявок</td></tr>";

    $$("[data-ticket-view]", $("#tickets-body")).forEach((btn) => {
      btn.onclick = (e) => { e.stopPropagation(); openTicketDialog(Number(btn.dataset.ticketView)); };
    });
    $$("[data-ticket-row]", $("#tickets-body")).forEach((row) => {
      row.onclick = () => openTicketDialog(Number(row.dataset.ticketRow));
    });
    $$("[data-ticket]", $("#tickets-body")).forEach((btn) => btn.onclick = (e) => {
      e.stopPropagation();
      const cur = btn.dataset.cur;
      const next = allowedNextStatuses(cur);
      if (!next.length) {
        showToast(`Из статуса «${statusLabel(cur)}» переходы недоступны`, true);
        return;
      }
      openModal("Статус #" + btn.dataset.ticket, [
        { label: "Статус", name: "status", tag: "select", attrs: "required",
          options: next.map((s) => `<option value="${s}">${statusLabel(s)}</option>`).join("") },
        { label: "Комментарий", name: "comment", tag: "textarea", attrs: "rows='2'" },
      ], async (fd) => {
        const res = await api("/tickets/" + btn.dataset.ticket + "/status", {
          method: "POST",
          body: JSON.stringify({ status: fd.get("status"), comment: fd.get("comment") || null }),
        });
        showToast(res.noop ? "Статус без изменений" : "Статус обновлён");
        loadTickets($("#ticket-filter").value);
        loadDashboard().catch(() => {});
      });
    });
  }

  const GROUP_STATUS_KIND = { active: "ok", pending: "warn", frozen: "warn", banned: "danger", deleted: "neutral" };

  function groupMatchesFilter(g) {
    if (groupFilter === "pending") return g.status === "pending";
    if (groupFilter === "active") return g.status === "active";
    if (groupFilter === "frozen") return g.status === "frozen";
    if (groupFilter === "banned") return g.status === "banned";
    return true;
  }

  function groupMatchesSearch(g) {
    if (!groupSearch) return true;
    const q = groupSearch.toLowerCase();
    return [g.display_name, g.group_name, g.call_center_label, g.tariff, String(g.telegram_group_id)]
      .filter(Boolean)
      .some((s) => String(s).toLowerCase().includes(q));
  }

  function renderGroupCards() {
    const items = groupsCache.filter((g) => groupMatchesFilter(g) && groupMatchesSearch(g));
    const box = $("#group-cards");
    if (!items.length) {
      box.innerHTML = `<div class="empty-state"><div class="empty-icon">👥</div><p>Нет групп по фильтру</p></div>`;
      return;
    }
    box.innerHTML = items.map((g) => {
      const st = badge(g.status_label, GROUP_STATUS_KIND[g.status] || "neutral");
      const tariff = g.tariff ? badge(g.tariff, "neutral") : "";
      const tickets = g.open_tickets ? badge(g.open_tickets + " заявок", "warn") : "";
      return `<article class="group-card ${g.status}" data-group-id="${g.id}">
        <div class="group-card-head">
          <div class="group-card-title">${g.display_name}</div>
          <div class="group-card-sub">${g.telegram_group_id}</div>
        </div>
        <div class="group-card-body">
          <div>${st} ${tariff} ${tickets}</div>
          <div><strong>Владелец:</strong> ${g.owner?.internal_id || "—"}</div>
          <div><strong>Контакт:</strong> ${g.contact_info ? g.contact_info.split("\n")[0] : "—"}</div>
        </div>
        <div class="group-card-foot">
          <button type="button" class="btn sm secondary" data-g-open="${g.id}">Открыть</button>
          ${g.status === "pending" ? `<button type="button" class="btn sm success" data-g-approve="${g.id}">✓</button>` : ""}
          ${g.status === "active" && !g.is_frozen ? `<button type="button" class="btn sm secondary" data-g-freeze="${g.id}">⏸</button>` : ""}
          ${g.is_frozen ? `<button type="button" class="btn sm secondary" data-g-unfreeze="${g.id}">▶</button>` : ""}
        </div>
      </article>`;
    }).join("");
    bindGroupCardActions();
  }

  function switchGroupFormTab(tab) {
    $$("[data-gf-tab]").forEach((b) => b.classList.toggle("active", b.dataset.gfTab === tab));
    $$("[data-gf-panel]").forEach((p) => p.toggleAttribute("hidden", p.dataset.gfPanel !== tab));
  }

  function fillGroupForm(g) {
    const form = $("#group-dialog-form");
    if (!form) return;
    const set = (name, val) => {
      const el = form.elements[name];
      if (el) el.value = val ?? "";
    };
    set("telegram_group_id", g.telegram_group_id);
    set("group_name", g.group_name);
    set("call_center_label", g.call_center_label);
    set("notes", g.notes);
    set("participants_info", g.participants_info);
    set("contact_info", g.contact_info);
    set("tariff", g.tariff);
    set("tariff_notes", g.tariff_notes);
    set("work_conditions", g.work_conditions);
    const tgInput = form.elements.telegram_group_id;
    if (tgInput) tgInput.readOnly = true;
  }

  function renderGroupDialogActions(g) {
    const actions = $("#group-dialog-actions");
    if (!actions) return;
    let html = "";
    if (g.status === "pending") {
      html += `<button type="button" class="btn success sm" data-g-approve="${g.id}">Одобрить</button>`;
      html += `<button type="button" class="btn danger sm" data-g-reject="${g.id}">Отклонить</button>`;
    }
    if (!g.is_banned && g.status !== "pending") {
      html += g.is_frozen
        ? `<button type="button" class="btn secondary sm" data-g-unfreeze="${g.id}">Разморозить</button>`
        : `<button type="button" class="btn secondary sm" data-g-freeze="${g.id}">Заморозить</button>`;
    }
    if (!g.is_banned) html += `<button type="button" class="btn danger sm" data-g-ban="${g.id}">Бан</button>`;
    else html += `<button type="button" class="btn secondary sm" data-g-unban="${g.id}">Разбан</button>`;
    html += `<button type="button" class="btn secondary sm" data-g-owner="${g.id}">Владелец</button>`;
    html += `<button type="button" class="btn danger sm" data-g-delete="${g.id}">Удалить</button>`;
    actions.innerHTML = html;
    bindGroupCardActions(actions);
  }

  async function openGroupDialog(id) {
    const dlg = $("#group-dialog");
    try {
      const g = await api(`/groups/${id}`);
      $("#group-dialog-title").textContent = g.display_name;
      fillGroupForm(g);
      switchGroupFormTab("main");
      $("#group-dialog-meta").innerHTML = `
        Статус: ${badge(g.status_label, GROUP_STATUS_KIND[g.status] || "neutral")}
        · Создана: ${formatDate(g.created_at)}
        ${g.approved_at ? ` · Одобрена: ${formatDate(g.approved_at)}` : ""}
        ${g.frozen_at ? ` · Заморожена: ${formatDate(g.frozen_at)}` : ""}`;
      renderGroupDialogActions(g);
      dlg.dataset.groupId = String(id);
      dlg.showModal();
    } catch (e) {
      showToast(e.message, true);
    }
  }

  function openGroupCreate() {
    const dlg = $("#group-dialog");
    $("#group-dialog-title").textContent = "Новый колл-центр";
    const form = $("#group-dialog-form");
    form.reset();
    form.elements.telegram_group_id.readOnly = false;
    $("#group-dialog-meta").innerHTML = "Укажите Telegram ID группы и заполните сведения.";
    $("#group-dialog-actions").innerHTML = "";
    switchGroupFormTab("main");
    dlg.dataset.groupId = "";
    dlg.showModal();
  }

  function bindGroupCardActions(root = document) {
    const scope = root === document ? $("#group-cards") || document : root;
    $$("[data-g-open]", scope).forEach((b) => b.onclick = () => openGroupDialog(Number(b.dataset.gOpen)));
    $$("[data-g-approve]", scope).forEach((b) => b.onclick = async () => {
      await api("/groups/" + b.dataset.gApprove + "/approve", { method: "POST" });
      showToast("Одобрено"); loadGroups(); loadDashboard().catch(() => {});
      $("#group-dialog")?.close();
    });
    $$("[data-g-reject]", scope).forEach((b) => b.onclick = async () => {
      if (!confirm("Отклонить заявку группы?")) return;
      await api("/groups/" + b.dataset.gReject + "/reject", { method: "POST" });
      showToast("Отклонено"); loadGroups(); $("#group-dialog")?.close();
    });
    $$("[data-g-freeze]", scope).forEach((b) => b.onclick = () => openModal("Заморозить колл-центр", [
      { label: "Причина (необязательно)", name: "reason", tag: "textarea", attrs: "rows='2'" },
    ], async (fd) => {
      await api("/groups/" + b.dataset.gFreeze + "/freeze", {
        method: "POST",
        body: JSON.stringify({ reason: fd.get("reason") || null }),
      });
      showToast("Заморожена"); loadGroups(); openGroupDialog(Number(b.dataset.gFreeze));
    }));
    $$("[data-g-unfreeze]", scope).forEach((b) => b.onclick = async () => {
      await api("/groups/" + b.dataset.gUnfreeze + "/unfreeze", { method: "POST" });
      showToast("Разморожена"); loadGroups(); openGroupDialog(Number(b.dataset.gUnfreeze));
    });
    $$("[data-g-ban]", scope).forEach((b) => b.onclick = () => openModal("Бан группы", [
      { label: "Причина", name: "reason", attrs: "required" },
    ], async (fd) => {
      await api("/groups/" + b.dataset.gBan + "/ban", { method: "POST", body: JSON.stringify({ reason: fd.get("reason") }) });
      showToast("Заблокирована"); loadGroups(); $("#group-dialog")?.close();
    }));
    $$("[data-g-unban]", scope).forEach((b) => b.onclick = async () => {
      await api("/groups/" + b.dataset.gUnban + "/unban", { method: "POST" });
      showToast("Разблокирована"); loadGroups();
    });
    $$("[data-g-owner]", scope).forEach((b) => b.onclick = () => openModal("Владелец группы", [
      { label: "Telegram ID", name: "telegram_id", attrs: 'type="number" required' },
    ], async (fd) => {
      await api("/groups/" + b.dataset.gOwner + "/owner", {
        method: "POST",
        body: JSON.stringify({ telegram_id: Number(fd.get("telegram_id")) }),
      });
      showToast("Владелец назначен"); loadGroups(); openGroupDialog(Number(b.dataset.gOwner));
    }));
    $$("[data-g-delete]", scope).forEach((b) => b.onclick = async () => {
      if (!confirm("Удалить/отключить колл-центр? Бот покинет группу.")) return;
      await api("/groups/" + b.dataset.gDelete + "/delete", { method: "POST" });
      showToast("Удалена"); loadGroups(); $("#group-dialog")?.close();
    });
  }

  async function saveGroupDialog(e) {
    e.preventDefault();
    const dlg = $("#group-dialog");
    const id = dlg?.dataset.groupId;
    const fd = new FormData($("#group-dialog-form"));
    const payload = {
      group_name: fd.get("group_name") || null,
      call_center_label: fd.get("call_center_label") || null,
      notes: fd.get("notes") || null,
      participants_info: fd.get("participants_info") || null,
      contact_info: fd.get("contact_info") || null,
      tariff: fd.get("tariff") || null,
      tariff_notes: fd.get("tariff_notes") || null,
      work_conditions: fd.get("work_conditions") || null,
    };
    try {
      if (id) {
        await api("/groups/" + id, { method: "PATCH", body: JSON.stringify(payload) });
        showToast("Сохранено");
        await loadGroups();
        dlg.close();
      } else {
        const body = {
          ...payload,
          telegram_group_id: Number(fd.get("telegram_group_id")),
        };
        const created = await api("/groups", { method: "POST", body: JSON.stringify(body) });
        showToast("Группа создана");
        await loadGroups();
        dlg.close();
        openGroupDialog(created.id);
      }
    } catch (err) {
      showToast(err.message, true);
    }
  }

  async function loadGroups() {
    const { items } = await api("/groups");
    groupsCache = items;
    navStats.groups_pending = items.filter((g) => g.status === "pending").length;
    updateNavBadges();
    renderGroupCards();
    setSyncTime();
  }

  const EVENT_FLAG_LABELS = {
    support_chats: "Чаты поддержки",
    admin_chats: "Администраторы",
    user_dm: "Пользователю в ЛС",
    source_group: "Исходная группа",
  };

  const EVENT_SCHEMA = {
    ticket_new: ["support_chats", "admin_chats"],
    ticket_status: ["user_dm", "source_group"],
    ticket_resolved: ["user_dm", "source_group"],
    group_pending: ["support_chats", "admin_chats"],
    deposit_new: ["support_chats", "admin_chats"],
  };

  let nfData = null;

  function parseChatIds(raw) {
    return [...new Set(String(raw || "").split(/[\s,;]+/).map((s) => s.trim()).filter(Boolean).map(Number).filter((n) => !Number.isNaN(n)))];
  }

  function formatChatIds(ids) {
    return (ids || []).join("\n");
  }

  function renderNotificationEvents(config, labels) {
    const box = $("#nf-events");
    if (!box) return;
    const events = config.events || {};
    box.innerHTML = `<h2>События</h2><div class="event-grid">${
      Object.entries(EVENT_SCHEMA).map(([key, flags]) => `
        <div class="event-row" data-event="${key}">
          <strong>${labels[key] || key}</strong>
          ${flags.map((flag) => `
            <label>
              <input type="checkbox" data-flag="${flag}" ${events[key]?.[flag] ? "checked" : ""}>
              ${EVENT_FLAG_LABELS[flag] || flag}
            </label>
          `).join("")}
        </div>
      `).join("")
    }</div>`;
  }

  function collectNotificationForm() {
    const events = {};
    $$(".event-row", $("#nf-events")).forEach((row) => {
      const key = row.dataset.event;
      events[key] = {};
      $$("input[data-flag]", row).forEach((inp) => {
        events[key][inp.dataset.flag] = inp.checked;
      });
    });
    return {
      support_chat_ids: parseChatIds($("#nf-support-ids")?.value),
      admin_chat_ids: parseChatIds($("#nf-admin-ids")?.value),
      events,
    };
  }

  function fillNotificationForm(config) {
    $("#nf-support-ids").value = formatChatIds(config.support_chat_ids);
    $("#nf-admin-ids").value = formatChatIds(config.admin_chat_ids);
    renderNotificationEvents(config, nfData?.event_labels || {});
  }

  async function loadNotifications() {
    nfData = await api("/settings/notifications");
    fillNotificationForm(nfData.config);
  }

  let spData = null;

  function parseStunList(raw) {
    return [...new Set(String(raw || "").split(/[\s,;]+/).map((s) => s.trim()).filter(Boolean))];
  }

  function formatStunList(list) {
    return (list || []).join("\n");
  }

  function updateSoftphoneStatusLine() {
    const el = $("#sp-status-line");
    if (!el || !spData) return;
    const parts = [];
    if (spData.ready) parts.push('<span class="badge ok">Транк готов</span>');
    else parts.push('<span class="badge warn">Транк не настроен</span>');
    if (spData.env_enabled) parts.push('<span class="badge neutral">SIP_TRUNK_ENABLED в .env</span>');
    if (spData.config?.enabled) parts.push('<span class="badge ok">Softphone включён</span>');
    else parts.push('<span class="badge neutral">Softphone выключен</span>');
    el.innerHTML = parts.join(" ");
  }

  function fillSoftphoneForm(config) {
    $("#sp-enabled").checked = !!config.enabled;
    $("#sp-display-name").value = config.display_name || "";
    $("#sp-session-ttl").value = config.session_ttl_seconds ?? 300;
    $("#sp-wss-url").value = config.wss_url || "";
    $("#sp-sip-domain").value = config.sip_domain || "";
    $("#sp-outbound-proxy").value = config.outbound_proxy || "";
    $("#sp-dial-prefix").value = config.dial_prefix || "";
    $("#sp-stun-servers").value = formatStunList(config.stun_servers);
    $("#sp-turn-url").value = config.turn_url || "";
    $("#sp-turn-username").value = config.turn_username || "";
    $("#sp-turn-credential").value = "";
    const hint = $("#sp-turn-cred-hint");
    if (hint) {
      hint.textContent = config.turn_credential_set ? "— задан, оставьте пустым чтобы сохранить" : "";
    }
  }

  function collectSoftphoneForm() {
    const ttl = Number($("#sp-session-ttl")?.value || 300);
    const body = {
      enabled: $("#sp-enabled")?.checked || false,
      display_name: $("#sp-display-name")?.value.trim() || "SIP CRM",
      session_ttl_seconds: Number.isFinite(ttl) ? Math.min(900, Math.max(60, ttl)) : 300,
      wss_url: $("#sp-wss-url")?.value.trim() || "",
      sip_domain: $("#sp-sip-domain")?.value.trim() || "",
      outbound_proxy: $("#sp-outbound-proxy")?.value.trim() || "",
      dial_prefix: $("#sp-dial-prefix")?.value.trim() || "",
      stun_servers: parseStunList($("#sp-stun-servers")?.value),
      turn_url: $("#sp-turn-url")?.value.trim() || "",
      turn_username: $("#sp-turn-username")?.value.trim() || "",
      turn_credential: $("#sp-turn-credential")?.value || "",
    };
    return body;
  }

  async function loadSoftphoneSettings() {
    spData = await api("/settings/softphone");
    fillSoftphoneForm(spData.config);
    updateSoftphoneStatusLine();
  }

  async function saveSoftphoneSettings(e) {
    e.preventDefault();
    const body = collectSoftphoneForm();
    const res = await api("/settings/softphone", { method: "PUT", body: JSON.stringify(body) });
    spData.config = res.config;
    spData.ready = res.ready;
    fillSoftphoneForm(res.config);
    updateSoftphoneStatusLine();
    showToast(res.ready ? "Транк сохранён и готов" : "Сохранено — проверьте WSS URL и SIP domain");
  }

  const DEPOSIT_STATUS_RU = {
    pending: "Ожидает", awaiting_review: "На проверке", confirmed: "Подтверждено",
    rejected: "Отклонено", expired: "Истекло", cancelled: "Отменено",
  };
  let finTab = "wallets";

  function switchFinTab(name) {
    finTab = name;
    $$(".dash-tab[data-fin-tab]").forEach((b) => b.classList.toggle("active", b.dataset.finTab === name));
    ["wallets", "deposits", "balances", "config"].forEach((t) => {
      const p = $(`#fin-panel-${t}`);
      if (p) p.hidden = t !== name;
    });
    if (name === "wallets") loadFinanceWallets();
    else if (name === "deposits") loadFinanceDeposits();
    else if (name === "balances") loadFinanceBalances();
    else if (name === "config") loadFinanceConfig();
  }

  async function loadFinanceWallets() {
    const data = await api("/finance/wallets");
    const body = $("#fin-wallets-body");
    if (!body) return;
    body.innerHTML = (data.items || []).map((w) => `
      <tr>
        <td>${w.id}</td>
        <td><code>${w.address}</code></td>
        <td>${w.label || "—"}</td>
        <td>${w.network}</td>
        <td>${w.is_active ? badge("Да", "ok") : badge("Нет", "neutral")}</td>
        <td>${w.notes || "—"}</td>
        <td>
          <button type="button" class="btn-link" data-fin-wallet-edit="${w.id}">✎</button>
          <button type="button" class="btn-link danger" data-fin-wallet-del="${w.id}">✕</button>
        </td>
      </tr>`).join("") || `<tr><td colspan="7" class="empty-cell">Нет кошельков</td></tr>`;
    body.querySelectorAll("[data-fin-wallet-edit]").forEach((btn) => {
      btn.onclick = () => {
        const w = data.items.find((x) => x.id === Number(btn.dataset.finWalletEdit));
        if (!w) return;
        openModal("Редактировать кошелёк", [
          { label: "Адрес", name: "address", attrs: `required value="${w.address}"` },
          { label: "Метка", name: "label", attrs: `value="${w.label || ""}"` },
          { label: "Сеть", name: "network", attrs: `value="${w.network}"` },
          { label: "Активен", name: "is_active", attrs: `type="checkbox"${w.is_active ? " checked" : ""}` },
          { label: "Заметки", name: "notes", attrs: `value="${w.notes || ""}"` },
        ], async (fd) => {
          await api(`/finance/wallets/${w.id}`, { method: "PATCH", body: JSON.stringify({
            address: fd.get("address"),
            label: fd.get("label") || null,
            network: fd.get("network") || "TRC20",
            is_active: fd.get("is_active") === "on",
            notes: fd.get("notes") || null,
          })});
          showToast("Кошелёк обновлён");
          loadFinanceWallets();
        });
      };
    });
    body.querySelectorAll("[data-fin-wallet-del]").forEach((btn) => {
      btn.onclick = async () => {
        if (!confirm("Удалить кошелёк?")) return;
        await api(`/finance/wallets/${btn.dataset.finWalletDel}`, { method: "DELETE" });
        showToast("Удалено");
        loadFinanceWallets();
      };
    });
  }

  async function loadFinanceDeposits() {
    const status = $("#fin-deposit-filter")?.value || "";
    const q = status ? `?status=${encodeURIComponent(status)}` : "";
    const data = await api(`/finance/deposits${q}`);
    const body = $("#fin-deposits-body");
    if (!body) return;
    body.innerHTML = (data.items || []).map((d) => {
      const canAct = ["pending", "awaiting_review"].includes(d.status);
      return `<tr>
        <td>${d.id}</td>
        <td>${d.user_internal_id || d.user_id}</td>
        <td><b>${d.amount_usdt}</b></td>
        <td>${badge(DEPOSIT_STATUS_RU[d.status] || d.status, d.status === "confirmed" ? "ok" : "neutral")}</td>
        <td><code>${d.wallet?.address?.slice(0, 12) || "—"}…</code></td>
        <td>${d.tx_hash ? `<code>${d.tx_hash.slice(0, 10)}…</code>` : "—"}</td>
        <td>${formatDate(d.created_at)}</td>
        <td>${canAct ? `
          <button type="button" class="btn-link" data-fin-dep-ok="${d.id}">✓</button>
          <button type="button" class="btn-link danger" data-fin-dep-no="${d.id}">✕</button>` : "—"}</td>
      </tr>`;
    }).join("") || `<tr><td colspan="8" class="empty-cell">Нет заявок</td></tr>`;
    body.querySelectorAll("[data-fin-dep-ok]").forEach((btn) => {
      btn.onclick = async () => {
        await api(`/finance/deposits/${btn.dataset.finDepOk}/confirm`, { method: "POST", body: "{}" });
        showToast("Заявка подтверждена, баланс зачислен");
        loadFinanceDeposits();
      };
    });
    body.querySelectorAll("[data-fin-dep-no]").forEach((btn) => {
      btn.onclick = async () => {
        const note = prompt("Причина отклонения (необязательно):") || null;
        await api(`/finance/deposits/${btn.dataset.finDepNo}/reject`, {
          method: "POST", body: JSON.stringify({ admin_note: note }),
        });
        showToast("Заявка отклонена");
        loadFinanceDeposits();
      };
    });
  }

  async function loadFinanceBalances() {
    const data = await api("/finance/balances");
    const body = $("#fin-balances-body");
    if (!body) return;
    body.innerHTML = (data.items || []).map((b) => `
      <tr>
        <td>${b.user_id}</td>
        <td>${b.internal_id}</td>
        <td>${b.telegram_id}</td>
        <td><b>${b.balance_usdt}</b></td>
        <td><button type="button" class="btn-link" data-fin-bal-edit="${b.user_id}" data-bal="${b.balance_usdt}">✎</button></td>
      </tr>`).join("") || `<tr><td colspan="5" class="empty-cell">Нет данных</td></tr>`;
    body.querySelectorAll("[data-fin-bal-edit]").forEach((btn) => {
      btn.onclick = () => {
        openModal("Изменить баланс", [
          { label: "Баланс USDT", name: "balance_usdt", attrs: `required value="${btn.dataset.bal}"` },
        ], async (fd) => {
          await api(`/finance/balances/${btn.dataset.finBalEdit}`, {
            method: "PATCH", body: JSON.stringify({ balance_usdt: fd.get("balance_usdt") }),
          });
          showToast("Баланс обновлён");
          loadFinanceBalances();
        });
      };
    });
  }

  async function loadFinanceConfig() {
    const cfg = await api("/finance/config");
    const form = $("#fin-config-form");
    if (!form) return;
    form.min_deposit_usdt.value = cfg.min_deposit_usdt;
    form.max_deposit_usdt.value = cfg.max_deposit_usdt;
    form.deposit_ttl_hours.value = cfg.deposit_ttl_hours;
    form.instruction_text.value = cfg.instruction_text || "";
  }

  async function loadFinance() {
    switchFinTab(finTab);
  }

  async function loadAudit() {
    const cat = $("#audit-category")?.value || "";
    const q = cat ? `?category=${encodeURIComponent(cat)}` : "";
    const data = await api(`/audit${q}`);
    const body = $("#audit-body");
    if (!body) return;
    body.innerHTML = (data.items || []).map((e) => `
      <tr>
        <td>${e.id}</td>
        <td>${formatDate(e.created_at)}</td>
        <td>${e.category}</td>
        <td><code>${e.action}</code></td>
        <td>${e.actor_label || e.actor_user_id || "—"}</td>
        <td>${e.entity_type || "—"} #${e.entity_id ?? "—"}</td>
        <td><code class="audit-details">${JSON.stringify(e.details || {}).slice(0, 120)}</code></td>
      </tr>`).join("") || `<tr><td colspan="7" class="empty-cell">Пусто</td></tr>`;
  }

  async function loadSystemRegistry() {
    const data = await api("/system/settings");
    const body = $("#system-body");
    if (!body) return;
    body.innerHTML = (data.items || []).map((r) => `
      <tr data-sys-key="${r.key}">
        <td><code>${r.key}</code></td>
        <td class="sys-value" title="Двойной клик для редактирования"><pre>${JSON.stringify(r.value, null, 2)}</pre></td>
        <td>${r.description || "—"}</td>
        <td>${formatDate(r.updated_at)}</td>
      </tr>`).join("") || `<tr><td colspan="4" class="empty-cell">Пусто</td></tr>`;
    body.querySelectorAll(".sys-value").forEach((cell) => {
      cell.ondblclick = async () => {
        const row = cell.closest("tr");
        const key = row?.dataset.sysKey;
        if (!key) return;
        const current = cell.querySelector("pre")?.textContent || "{}";
        const next = prompt(`JSON для ключа «${key}»:`, current);
        if (next === null) return;
        let parsed;
        try { parsed = JSON.parse(next); } catch { showToast("Некорректный JSON", true); return; }
        await api(`/system/settings/${encodeURIComponent(key)}`, {
          method: "PUT", body: JSON.stringify({ value: parsed }),
        });
        showToast("Сохранено");
        loadSystemRegistry();
      };
    });
  }

  let notionTab = "guide";
  let notionGuideData = null;
  let notionWizardStep = 0;
  const NOTION_WIZARD_STEPS = [
    { id: "integration", title: "1. Интеграция" },
    { id: "token", title: "2. Токен" },
    { id: "test", title: "3. Проверка" },
    { id: "databases", title: "4. Базы" },
    { id: "finish", title: "5. Запуск" },
  ];

  function switchNotionTab(name) {
    notionTab = name;
    $$(".dash-tab[data-notion-tab]").forEach((b) => b.classList.toggle("active", b.dataset.notionTab === name));
    ["guide", "wizard", "ledger", "settings", "explorer"].forEach((t) => {
      const p = $(`#notion-panel-${t}`);
      if (p) p.hidden = t !== name;
    });
    if (name === "guide") renderNotionGuide();
    else if (name === "wizard") renderNotionWizard();
    else if (name === "ledger") renderNotionLedger();
    else if (name === "settings") fillNotionSettingsForm();
    else if (name === "explorer") { /* on demand */ }
  }

  function updateNotionStatusBar(guide) {
    const tokenPill = $("#notion-pill-token");
    const activePill = $("#notion-pill-active");
    const verPill = $("#notion-pill-version");
    if (!guide) return;
    if (tokenPill) {
      tokenPill.textContent = guide.has_token ? "Токен: задан" : "Токен: не задан";
      tokenPill.className = "notion-pill " + (guide.has_token ? "ok" : "err");
    }
    if (activePill) {
      activePill.textContent = guide.active ? "Статус: активна" : "Статус: выключена";
      activePill.className = "notion-pill " + (guide.active ? "ok" : "warn");
    }
    if (verPill) verPill.textContent = `API: ${guide.api_version || "—"}`;
  }

  function renderNotionGuide() {
    const box = $("#notion-guide-content");
    if (!box || !notionGuideData) return;
    const g = notionGuideData;
    const envHtml = Object.entries(g.env || {}).map(([key, meta]) => `
      <div class="notion-env-row">
        <div>
          <div class="notion-env-key">${key}</div>
          <div>${meta.label}</div>
          <div class="notion-env-hint">${meta.hint}</div>
        </div>
        ${badge(meta.set ? "OK" : (meta.required ? "Нужно" : "—"), meta.set ? "ok" : (meta.required ? "neutral" : "neutral"))}
      </div>`).join("");
    const algoHtml = (g.algorithm || []).map((s) => `
      <li><strong>${s.title}</strong> — ${s.body}</li>`).join("");
    const flowHtml = (g.flow || []).map((line) => `<div>${line}</div>`).join("");
    box.innerHTML = `
      <div class="notion-guide-card" style="grid-column: 1 / -1">
        <h3>Переменные окружения (.env на сервере)</h3>
        ${envHtml}
      </div>
      <div class="notion-guide-card">
        <h3>Алгоритм подключения</h3>
        <ol>${algoHtml}</ol>
      </div>
      <div class="notion-guide-card">
        <h3>Поток синхронизации</h3>
        <div class="notion-flow">${flowHtml}</div>
      </div>
      <div class="notion-guide-card">
        <h3>Слоты баз данных</h3>
        <ul>${Object.entries(g.database_slots || {}).map(([k, v]) => `<li><code>${k}</code> — ${v}</li>`).join("")}</ul>
      </div>
      <div class="notion-guide-card">
        <h3>События</h3>
        <ul>${Object.entries(g.sync_event_labels || {}).map(([k, v]) => `<li><code>${k}</code> — ${v}</li>`).join("")}</ul>
      </div>`;
  }

  function renderNotionWizardSteps() {
    const steps = $("#notion-wizard-steps");
    if (!steps) return;
    steps.innerHTML = NOTION_WIZARD_STEPS.map((s, i) => `
      <span class="notion-wizard-step-pill ${i === notionWizardStep ? "active" : ""} ${i < notionWizardStep ? "done" : ""}">${s.title}</span>
    `).join("");
    $("#notion-wiz-prev").disabled = notionWizardStep === 0;
    $("#notion-wiz-next").textContent = notionWizardStep >= NOTION_WIZARD_STEPS.length - 1 ? "Готово" : "Далее →";
  }

  function renderNotionWizard() {
    renderNotionWizardSteps();
    const body = $("#notion-wizard-body");
    if (!body || !notionGuideData) return;
    const g = notionGuideData;
    const step = NOTION_WIZARD_STEPS[notionWizardStep]?.id;

    if (step === "integration") {
      body.innerHTML = `
        <h3>Создайте Internal Integration в Notion</h3>
        <p class="hint">Откройте <a href="https://www.notion.so/my-integrations" target="_blank" rel="noopener">notion.so/my-integrations</a> → New integration → скопируйте Secret.</p>
        <div class="notion-wizard-checklist">
          <label><input type="checkbox" id="nw-chk-1"> Интеграция создана</label>
          <label><input type="checkbox" id="nw-chk-2"> К нужным базам подключена через Connections</label>
        </div>`;
    } else if (step === "token") {
      body.innerHTML = `
        <h3>Токен на сервере</h3>
        <p class="hint">Добавьте в <code>/opt/sipcrm/.env</code> (или локальный .env) и перезапустите контейнеры:</p>
        <pre class="notion-flow">NOTION_API_TOKEN=secret_ваш_токен
NOTION_ENABLED=true
NOTION_DATABASE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx</pre>
        <p class="hint">Текущий статус токена: <b>${g.has_token ? "задан ✓" : "не обнаружен ✗"}</b></p>`;
    } else if (step === "test") {
      body.innerHTML = `
        <h3>Проверка подключения</h3>
        <p class="hint">Вызов Notion API <code>GET /users/me</code> с токеном из .env.</p>
        <button type="button" class="btn" id="notion-wiz-test-btn">Проверить подключение</button>
        <div id="notion-wiz-test-result"></div>`;
      $("#notion-wiz-test-btn")?.addEventListener("click", async () => {
        const out = $("#notion-wiz-test-result");
        out.innerHTML = `<div class="notion-test-result">Проверка…</div>`;
        try {
          const res = await api("/notion/test", { method: "POST", body: "{}" });
          out.innerHTML = `<div class="notion-test-result ok">✓ Подключено: ${res.workspace_name || res.bot_type || "OK"}</div>`;
        } catch (e) {
          out.innerHTML = `<div class="notion-test-result err">✗ ${e.message}</div>`;
        }
      });
    } else if (step === "databases") {
      const cfg = g.config || {};
      const dbs = cfg.databases || {};
      body.innerHTML = `
        <h3>Database ID</h3>
        <p class="hint">ID из URL базы Notion. Сохраняется в CRM (app_settings → notion).</p>
        <label class="field"><span>База по умолчанию</span>
          <input id="nw-default-db" value="${cfg.default_database_id || ""}"></label>
        <label class="field"><span>Заявки</span><input id="nw-db-tickets" value="${dbs.tickets || ""}"></label>
        <label class="field"><span>Депозиты</span><input id="nw-db-deposits" value="${dbs.deposits || ""}"></label>
        <label class="field"><span>Пользователи</span><input id="nw-db-users" value="${dbs.users || ""}"></label>
        <button type="button" class="btn secondary" id="notion-wiz-save-db">Сохранить базы</button>`;
      $("#notion-wiz-save-db")?.addEventListener("click", async () => {
        await api("/notion/config", { method: "PUT", body: JSON.stringify({
          default_database_id: $("#nw-default-db")?.value?.trim() || "",
          databases: {
            tickets: $("#nw-db-tickets")?.value?.trim() || "",
            deposits: $("#nw-db-deposits")?.value?.trim() || "",
            users: $("#nw-db-users")?.value?.trim() || "",
          },
        })});
        showToast("Базы сохранены");
        await loadNotion();
      });
    } else if (step === "finish") {
      const events = g.sync_event_labels || {};
      const cfgEv = (g.config || {}).sync_events || {};
      body.innerHTML = `
        <h3>Включение синхронизации</h3>
        <label class="field checkbox-field">
          <input type="checkbox" id="nw-enabled" ${(g.config || {}).enabled ? "checked" : ""}>
          <span>Интеграция активна в CRM</span>
        </label>
        <div class="notion-sync-grid" id="nw-sync-events">
          ${Object.entries(events).map(([k, label]) => `
            <label><input type="checkbox" data-nw-sync="${k}" ${cfgEv[k] ? "checked" : ""}> ${label}</label>
          `).join("")}
        </div>
        <button type="button" class="btn" id="notion-wiz-finish-btn">Сохранить и завершить</button>
        <button type="button" class="btn secondary" id="notion-wiz-verify-db">Проверить базу по умолчанию</button>
        <div id="notion-wiz-verify-result"></div>`;
      $("#notion-wiz-finish-btn")?.addEventListener("click", async () => {
        await saveNotionConfigFromWizard(true);
        showToast("Интеграция настроена");
        await loadNotion();
      });
      $("#notion-wiz-verify-db")?.addEventListener("click", async () => {
        const dbId = $("#nw-default-db")?.value || $("#notion-default-db")?.value || (g.config || {}).default_database_id;
        const out = $("#notion-wiz-verify-result");
        if (!dbId) { showToast("Укажите Database ID", true); return; }
        try {
          const schema = await api(`/notion/databases/${encodeURIComponent(dbId.trim())}`);
          const props = Object.keys(schema.properties || {});
          out.innerHTML = `<div class="notion-test-result ok">✓ База доступна. Колонки: ${props.join(", ") || "—"}</div>`;
        } catch (e) {
          out.innerHTML = `<div class="notion-test-result err">✗ ${e.message}</div>`;
        }
      });
    }
  }

  async function saveNotionConfigFromWizard(includeEvents = false) {
    const body = {
      default_database_id: ($("#nw-default-db") || $("#notion-default-db"))?.value?.trim() || "",
      databases: {
        tickets: ($("#nw-db-tickets") || $("#notion-db-tickets"))?.value?.trim() || "",
        deposits: ($("#nw-db-deposits") || $("#notion-db-deposits"))?.value?.trim() || "",
        users: ($("#nw-db-users") || $("#notion-db-users"))?.value?.trim() || "",
      },
    };
    if ($("#nw-enabled")) body.enabled = $("#nw-enabled").checked;
    if (includeEvents) {
      body.sync_events = {};
      $$("[data-nw-sync]").forEach((inp) => { body.sync_events[inp.dataset.nwSync] = inp.checked; });
      if (!Object.keys(body.sync_events).length) {
        $$("[data-notion-sync]").forEach((inp) => { body.sync_events[inp.dataset.notionSync] = inp.checked; });
      }
    }
    await api("/notion/config", { method: "PUT", body: JSON.stringify(body) });
  }

  function fillNotionSettingsForm() {
    if (!notionGuideData?.config) return;
    const cfg = notionGuideData.config;
    const en = $("#notion-enabled");
    if (en) en.checked = !!cfg.enabled;
    const def = $("#notion-default-db");
    if (def) def.value = cfg.default_database_id || "";
    const dbs = cfg.databases || {};
    if ($("#notion-db-tickets")) $("#notion-db-tickets").value = dbs.tickets || "";
    if ($("#notion-db-deposits")) $("#notion-db-deposits").value = dbs.deposits || "";
    if ($("#notion-db-finance-ledger")) $("#notion-db-finance-ledger").value = dbs.finance_ledger || "";
    if ($("#notion-db-users")) $("#notion-db-users").value = dbs.users || "";
    const box = $("#notion-sync-events");
    if (box) {
      const labels = notionGuideData.sync_event_labels || {};
      const ev = cfg.sync_events || {};
      box.innerHTML = Object.entries(labels).map(([k, label]) => `
        <label><input type="checkbox" data-notion-sync="${k}" ${ev[k] ? "checked" : ""}> ${label}</label>
      `).join("");
    }
  }

  async function notionSearch() {
    const q = $("#notion-search-q")?.value?.trim() || "";
    const list = $("#notion-search-results");
    if (!list) return;
    list.innerHTML = `<div class="empty-state"><p>Поиск…</p></div>`;
    try {
      const res = await api("/notion/search", { method: "POST", body: JSON.stringify({ query: q, page_size: 20 }) });
      const items = res.results || [];
      list.innerHTML = items.length ? items.map((item) => {
        const title = item.title?.[0]?.plain_text || item.properties?.Name?.title?.[0]?.plain_text || item.id;
        return `<button type="button" class="notion-explorer-item" data-notion-id="${item.id}" data-notion-type="${item.object}">
          ${title}<small>${item.object} · ${item.id}</small>
        </button>`;
      }).join("") : `<div class="empty-state"><p>Ничего не найдено</p></div>`;
      list.querySelectorAll(".notion-explorer-item").forEach((btn) => {
        btn.onclick = () => {
          $("#notion-explore-db-id").value = btn.dataset.notionId;
          if (btn.dataset.notionType === "database") loadNotionDbSchema(btn.dataset.notionId);
        };
      });
    } catch (e) {
      list.innerHTML = `<div class="empty-state"><p>${e.message}</p></div>`;
    }
  }

  async function loadNotionDbSchema(dbId) {
    const out = $("#notion-explore-output");
    if (!out || !dbId) return;
    out.textContent = "Загрузка…";
    try {
      const data = await api(`/notion/databases/${encodeURIComponent(dbId.trim())}`);
      out.textContent = JSON.stringify(data, null, 2);
    } catch (e) {
      out.textContent = e.message;
    }
  }

  async function loadNotionDbQuery(dbId) {
    const out = $("#notion-explore-output");
    if (!out || !dbId) return;
    out.textContent = "Загрузка…";
    try {
      const data = await api(`/notion/databases/${encodeURIComponent(dbId.trim())}/query`, {
        method: "POST", body: JSON.stringify({ page_size: 10 }),
      });
      out.textContent = JSON.stringify(data, null, 2);
    } catch (e) {
      out.textContent = e.message;
    }
  }

  function renderNotionLedger() {
    const g = notionGuideData;
    const fl = g?.finance_ledger;
    const status = $("#notion-ledger-status");
    if (status && fl) {
      status.innerHTML = fl.database_id
        ? `Подключена: <code>${fl.database_id}</code> · ${fl.title || "XanaXGSM"}`
        : "База не подключена. Создайте новую или привяжите существующую.";
    }
    const cols = $("#notion-ledger-columns");
    if (cols && fl?.expected_columns) {
      cols.innerHTML = fl.expected_columns.map((c) => `<li><code>${c}</code></li>`).join("");
    }
    if (fl?.database_id) {
      const linkInp = $("#notion-ledger-link-id");
      if (linkInp && !linkInp.value) linkInp.value = fl.database_id;
    }
  }

  let sipGuidesData = null;
  let sipGuideFilter = "all";
  let sipGuideSearch = "";
  let sipGuideSelectedId = null;

  async function loadSipGuides() {
    sipGuidesData = await api("/guides/sip-integration");
    const disc = $("#sip-guides-disclaimer");
    if (disc && sipGuidesData.disclaimer) disc.textContent = sipGuidesData.disclaimer;
    renderSipGuideChips();
    renderSipGuideNav();
    if (!sipGuideSelectedId && sipGuidesData.guides?.length) {
      sipGuideSelectedId = sipGuidesData.guides[0].id;
    }
    renderSipGuideDetail();
    setSyncTime();
  }

  function filteredSipGuides() {
    if (!sipGuidesData?.guides) return [];
    return sipGuidesData.guides.filter((g) => {
      if (sipGuideFilter !== "all" && g.category !== sipGuideFilter) return false;
      if (!sipGuideSearch) return true;
      const q = sipGuideSearch.toLowerCase();
      const hay = [g.title, g.summary, ...(g.steps || []).map((s) => s.title + " " + s.body)].join(" ").toLowerCase();
      return hay.includes(q);
    });
  }

  function renderSipGuideChips() {
    const box = $("#sip-guides-chips");
    if (!box || !sipGuidesData) return;
    const cats = sipGuidesData.categories || {};
    box.innerHTML = [
      `<button type="button" class="chip ${sipGuideFilter === "all" ? "active" : ""}" data-sg-filter="all">Все</button>`,
      ...Object.entries(cats).map(([id, meta]) =>
        `<button type="button" class="chip ${sipGuideFilter === id ? "active" : ""}" data-sg-filter="${id}">${meta.icon || ""} ${meta.label}</button>`
      ),
    ].join("");
    box.querySelectorAll("[data-sg-filter]").forEach((btn) => {
      btn.onclick = () => {
        sipGuideFilter = btn.dataset.sgFilter;
        renderSipGuideChips();
        renderSipGuideNav();
        const list = filteredSipGuides();
        if (!list.find((g) => g.id === sipGuideSelectedId)) {
          sipGuideSelectedId = list[0]?.id || null;
        }
        renderSipGuideDetail();
      };
    });
  }

  function renderSipGuideNav() {
    const nav = $("#sip-guides-nav");
    if (!nav) return;
    const list = filteredSipGuides();
    if (!list.length) {
      nav.innerHTML = `<div class="empty-state"><p>Ничего не найдено</p></div>`;
      return;
    }
    const cats = sipGuidesData.categories || {};
    nav.innerHTML = list.map((g) => {
      const cat = cats[g.category]?.label || g.category;
      return `<button type="button" class="sip-guide-nav-item ${g.id === sipGuideSelectedId ? "active" : ""}" data-guide-id="${g.id}">
        ${g.title}<small>${cat}</small>
      </button>`;
    }).join("");
    nav.querySelectorAll("[data-guide-id]").forEach((btn) => {
      btn.onclick = () => {
        sipGuideSelectedId = btn.dataset.guideId;
        renderSipGuideNav();
        renderSipGuideDetail();
      };
    });
  }

  function renderSipGuideDetail() {
    const box = $("#sip-guide-detail");
    if (!box || !sipGuidesData) return;
    const guide = sipGuidesData.guides.find((g) => g.id === sipGuideSelectedId);
    if (!guide) {
      box.innerHTML = `<div class="empty-state"><p>Выберите руководство</p></div>`;
      return;
    }
    const stepsHtml = (guide.steps || []).map((s) => `
      <li>
        <h3>${s.title}</h3>
        <p>${s.body}</p>
        ${s.menu ? `<span class="sip-guide-menu">${s.menu}</span>` : ""}
        ${s.note ? `<div class="sip-guide-note">${s.note}</div>` : ""}
      </li>`).join("");
    const sourcesHtml = (guide.sources || []).map((src) =>
      `<li><a href="${src.url}" target="_blank" rel="noopener noreferrer">${src.title}</a></li>`
    ).join("");
    box.innerHTML = `
      <h2>${guide.title}</h2>
      <p class="guide-summary">${guide.summary || ""}</p>
      <ol class="sip-guide-steps">${stepsHtml}</ol>
      <div class="sip-guide-sources">
        <h3>Официальные источники Kolmisoft</h3>
        <ul>${sourcesHtml}</ul>
      </div>`;
  }

  let operationGuidesData = null;
  let operationGuideFilter = "all";
  let operationGuideSearch = "";
  let operationGuideSelectedId = null;

  async function loadOperationGuides() {
    operationGuidesData = await api("/guides/operations");
    const disc = $("#operation-guides-disclaimer");
    if (disc && operationGuidesData.disclaimer) disc.textContent = operationGuidesData.disclaimer;
    renderOperationRoadmap();
    renderOperationGuideChips();
    renderOperationGuideNav();
    operationGuideSelectedId = operationGuidesData.featured_guide_id
      || operationGuidesData.guides?.[0]?.id
      || null;
    renderOperationGuideDetail();
    setSyncTime();
  }

  function renderOperationRoadmap() {
    const box = $("#operation-guides-roadmap");
    if (!box || !operationGuidesData?.workflow_roadmap?.length) {
      if (box) box.hidden = true;
      return;
    }
    box.hidden = false;
    box.innerHTML = `
      <div class="operation-roadmap-header">
        <h2>Маршрут работы</h2>
        <p>Порядок взаимодействия с продуктом для максимальной пользы</p>
      </div>
      <div class="operation-roadmap-grid">
        ${operationGuidesData.workflow_roadmap.map((p) => `
          <button type="button" class="operation-roadmap-card" data-goto-section="${p.web_section || ""}" data-goto-guide="workflow-max-value">
            <span class="operation-roadmap-title">${p.title}</span>
            <span class="operation-roadmap-summary">${p.summary}</span>
          </button>`).join("")}
      </div>`;
    box.querySelectorAll("[data-goto-section]").forEach((btn) => {
      btn.onclick = () => {
        const sec = btn.dataset.gotoSection;
        if (sec) navigateSection(sec);
        operationGuideFilter = "workflow";
        operationGuideSelectedId = operationGuidesData.featured_guide_id || "workflow-max-value";
        renderOperationGuideChips();
        renderOperationGuideNav();
        renderOperationGuideDetail();
      };
    });
  }

  function filteredOperationGuides() {
    if (!operationGuidesData?.guides) return [];
    return operationGuidesData.guides.filter((g) => {
      if (operationGuideFilter !== "all" && g.audience !== operationGuideFilter) return false;
      if (!operationGuideSearch) return true;
      const q = operationGuideSearch.toLowerCase();
      const hay = [g.title, g.summary, ...(g.steps || []).map((s) => s.title + " " + s.body + (s.menu || "") + (s.note || ""))].join(" ").toLowerCase();
      return hay.includes(q);
    });
  }

  function renderOperationGuideChips() {
    const box = $("#operation-guides-chips");
    if (!box || !operationGuidesData) return;
    const auds = operationGuidesData.audiences || {};
    box.innerHTML = [
      `<button type="button" class="chip ${operationGuideFilter === "all" ? "active" : ""}" data-og-filter="all">Все</button>`,
      ...Object.entries(auds).map(([id, meta]) =>
        `<button type="button" class="chip ${operationGuideFilter === id ? "active" : ""}" data-og-filter="${id}">${meta.icon || ""} ${meta.label}</button>`
      ),
    ].join("");
    box.querySelectorAll("[data-og-filter]").forEach((btn) => {
      btn.onclick = () => {
        operationGuideFilter = btn.dataset.ogFilter;
        renderOperationGuideChips();
        renderOperationGuideNav();
        const list = filteredOperationGuides();
        if (!list.find((g) => g.id === operationGuideSelectedId)) {
          operationGuideSelectedId = list[0]?.id || null;
        }
        renderOperationGuideDetail();
      };
    });
  }

  function renderOperationGuideNav() {
    const nav = $("#operation-guides-nav");
    if (!nav) return;
    const list = filteredOperationGuides();
    if (!list.length) {
      nav.innerHTML = `<div class="empty-state"><p>Ничего не найдено</p></div>`;
      return;
    }
    const auds = operationGuidesData.audiences || {};
    nav.innerHTML = list.map((g) => {
      const aud = auds[g.audience]?.label || g.audience;
      return `<button type="button" class="sip-guide-nav-item ${g.id === operationGuideSelectedId ? "active" : ""}" data-og-guide-id="${g.id}">
        ${g.title}<small>${aud}</small>
      </button>`;
    }).join("");
    nav.querySelectorAll("[data-og-guide-id]").forEach((btn) => {
      btn.onclick = () => {
        operationGuideSelectedId = btn.dataset.ogGuideId;
        renderOperationGuideNav();
        renderOperationGuideDetail();
      };
    });
  }

  function renderOperationGuideDetail() {
    const box = $("#operation-guide-detail");
    if (!box || !operationGuidesData) return;
    const guide = operationGuidesData.guides.find((g) => g.id === operationGuideSelectedId);
    if (!guide) {
      box.innerHTML = `<div class="empty-state"><p>Выберите руководство</p></div>`;
      return;
    }
    const auds = operationGuidesData.audiences || {};
    const audLabel = auds[guide.audience]?.label || guide.audience;
    const stepsHtml = (guide.steps || []).map((s) => `
      <li>
        <h3>${s.title}</h3>
        <p>${s.body.replace(/\n/g, "<br>")}</p>
        ${s.menu ? `<span class="sip-guide-menu">${s.menu}</span>` : ""}
        ${s.web_section ? `<button type="button" class="btn secondary sm guide-goto-section" data-goto-section="${s.web_section}">Открыть раздел →</button>` : ""}
        ${s.note ? `<div class="sip-guide-note">${s.note}</div>` : ""}
      </li>`).join("");
    box.innerHTML = `
      <p class="guide-audience-badge">${audLabel}</p>
      <h2>${guide.title}</h2>
      <p class="guide-summary">${guide.summary || ""}</p>
      <ol class="sip-guide-steps">${stepsHtml}</ol>`;
    box.querySelectorAll(".guide-goto-section").forEach((btn) => {
      btn.onclick = () => navigateSection(btn.dataset.gotoSection);
    });
  }

  async function loadNotion() {
    notionGuideData = await api("/notion/guide");
    updateNotionStatusBar(notionGuideData);
    if (notionTab === "guide") renderNotionGuide();
    else if (notionTab === "wizard") renderNotionWizard();
    else if (notionTab === "ledger") renderNotionLedger();
    else if (notionTab === "settings") fillNotionSettingsForm();
    setSyncTime();
  }

  async function saveNotifications(e) {
    e.preventDefault();
    const body = collectNotificationForm();
    const res = await api("/settings/notifications", { method: "PUT", body: JSON.stringify(body) });
    nfData.config = res.config;
    fillNotificationForm(res.config);
    showToast("Настройки уведомлений сохранены");
  }

  const SECTION_TITLES = {
    dashboard: "Дашборд", "service-desk": "Очередь колл-центра",
    users: "Пользователи", sips: "SIP-номера", tickets: "Все заявки", groups: "Колл-центры и группы",
    finance: "Финансы USDT", notion: "Интеграция Notion",
    "operation-guides": "Руководства",
    "sip-guides": "SIP-интеграции",
    audit: "Журнал действий", system: "Реестр памяти",
    notifications: "Уведомления", softphone: "SIP-транк",
    stats: "Дашборд",
  };

  function showQueueLoading() {
    const list = $("#sd-queue");
    if (list) {
      list.innerHTML = `<div class="skeleton"></div><div class="skeleton" style="margin-top:.5rem"></div><div class="skeleton" style="margin-top:.5rem"></div>`;
    }
  }

  function loadSection(name) {
    $("#topbar-title").textContent = SECTION_TITLES[name] || "SIP CRM";
    if (name) history.replaceState(null, "", `#${name}`);
    const loaders = {
      dashboard: () => { stopSdAutoRefresh(); loadDashboard().catch((e) => showToast(e.message, true)); },
      stats: () => { stopSdAutoRefresh(); navigateSection("dashboard"); switchDashTab("analytics"); },
      "service-desk": () => { loadServiceDesk(); startSdAutoRefresh(); },
      users: () => { stopSdAutoRefresh(); loadUsers(); },
      sips: () => { stopSdAutoRefresh(); loadSips(); },
      "sip-guides": () => { stopSdAutoRefresh(); loadSipGuides().catch((e) => showToast(e.message, true)); },
      "operation-guides": () => { stopSdAutoRefresh(); loadOperationGuides().catch((e) => showToast(e.message, true)); },
      tickets: () => { stopSdAutoRefresh(); loadTickets(); },
      groups: () => { stopSdAutoRefresh(); loadGroups(); },
      finance: () => { stopSdAutoRefresh(); loadFinance().catch((e) => showToast(e.message, true)); },
      notion: () => { stopSdAutoRefresh(); loadNotion().catch((e) => showToast(e.message, true)); },
      audit: () => { stopSdAutoRefresh(); loadAudit().catch((e) => showToast(e.message, true)); },
      system: () => { stopSdAutoRefresh(); loadSystemRegistry().catch((e) => showToast(e.message, true)); },
      notifications: () => { stopSdAutoRefresh(); loadNotifications(); },
      softphone: () => { stopSdAutoRefresh(); loadSoftphoneSettings().catch((e) => showToast(e.message, true)); },
    };
    if (name !== "service-desk") stopSdAutoRefresh();
    loaders[name]?.();
  }

  function startSdAutoRefresh() {
    stopSdAutoRefresh();
    if ($("#sd-auto")?.checked) {
      sdAutoTimer = setInterval(() => loadServiceDesk(), 20000);
    }
  }
  function stopSdAutoRefresh() {
    if (sdAutoTimer) clearInterval(sdAutoTimer);
    sdAutoTimer = null;
  }

  function init() {
    try {
      bindUi();
      const hash = (location.hash || "").replace(/^#/, "");
      if (hash === "stats") {
        navigateSection("dashboard");
        switchDashTab("analytics");
      } else if (hash && SECTION_TITLES[hash]) {
        navigateSection(hash);
      } else {
        loadDashboard().catch((e) => showToast(e.message, true));
      }
    } catch (e) {
      console.error(e);
      showBootError(e.message || String(e));
    }
  }

  function showBootError(msg) {
    const main = $(".content") || document.body;
    const box = document.createElement("div");
    box.className = "boot-error";
    box.innerHTML = `<h2>Не удалось загрузить панель</h2><p>${msg}</p><button type="button" class="btn" id="boot-retry">Повторить</button>`;
    main.prepend(box);
    $("#boot-retry")?.addEventListener("click", () => window.location.reload());
  }

  function bindUi() {
    $$(".nav-item[data-section]").forEach((btn) => {
      btn.onclick = () => {
        $$(".nav-item").forEach((b) => b.classList.remove("active"));
        $$(".section").forEach((s) => s.classList.remove("active"));
        btn.classList.add("active");
        $("#" + btn.dataset.section).classList.add("active");
        loadSection(btn.dataset.section);
      };
    });

    $("#modal-cancel")?.addEventListener("click", () => $("#modal")?.close());
    $("#modal-form")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      try { await modalHandler(new FormData(e.target)); $("#modal").close(); }
      catch (err) { showToast(err.message, true); }
    });

    $("#user-search-btn")?.addEventListener("click", () => loadUsers($("#user-search").value.trim()));
    $("#user-refresh-btn")?.addEventListener("click", () => loadUsers($("#user-search").value.trim()));
    $("#user-search")?.addEventListener("keydown", (e) => { if (e.key === "Enter") loadUsers($("#user-search").value.trim()); });
    $("#ticket-filter-btn")?.addEventListener("click", () => loadTickets($("#ticket-filter").value));
    $("#ticket-refresh-btn")?.addEventListener("click", () => loadTickets($("#ticket-filter").value));
    $("#sip-filter-btn")?.addEventListener("click", () => loadSips());
    $("#sip-refresh-btn")?.addEventListener("click", () => loadSips());
    $("#sip-search")?.addEventListener("keydown", (e) => { if (e.key === "Enter") loadSips(); });
    $("#operation-guides-search")?.addEventListener("input", (e) => {
      operationGuideSearch = e.target.value.trim();
      renderOperationGuideNav();
      const list = filteredOperationGuides();
      if (!list.find((g) => g.id === operationGuideSelectedId)) {
        operationGuideSelectedId = list[0]?.id || null;
      }
      renderOperationGuideDetail();
    });
    $("#sip-guides-search")?.addEventListener("input", (e) => {
      sipGuideSearch = e.target.value.trim();
      renderSipGuideNav();
      const list = filteredSipGuides();
      if (!list.find((g) => g.id === sipGuideSelectedId)) {
        sipGuideSelectedId = list[0]?.id || null;
      }
      renderSipGuideDetail();
    });
    $("#groups-refresh-btn")?.addEventListener("click", () => loadGroups());
    $("#group-create-btn")?.addEventListener("click", () => openGroupCreate());
    $("#group-search")?.addEventListener("input", (e) => {
      groupSearch = e.target.value.trim();
      renderGroupCards();
    });
    $("#group-dialog-close")?.addEventListener("click", () => $("#group-dialog")?.close());
    $("#group-dialog-form")?.addEventListener("submit", saveGroupDialog);
    $$("[data-gf-tab]").forEach((b) => b.onclick = () => switchGroupFormTab(b.dataset.gfTab));
    $$(".dash-tab[data-fin-tab]").forEach((b) => b.onclick = () => switchFinTab(b.dataset.finTab));
    $$(".dash-tab[data-notion-tab]").forEach((b) => b.onclick = () => switchNotionTab(b.dataset.notionTab));
    $("#notion-wiz-prev")?.addEventListener("click", () => {
      if (notionWizardStep > 0) { notionWizardStep -= 1; renderNotionWizard(); }
    });
    $("#notion-wiz-next")?.addEventListener("click", () => {
      if (notionWizardStep < NOTION_WIZARD_STEPS.length - 1) {
        notionWizardStep += 1;
        renderNotionWizard();
      } else {
        switchNotionTab("settings");
        showToast("Откройте вкладку «Параметры» для тонкой настройки");
      }
    });
    $("#notion-settings-form")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const sync_events = {};
      $$("[data-notion-sync]").forEach((inp) => { sync_events[inp.dataset.notionSync] = inp.checked; });
      await api("/notion/config", { method: "PUT", body: JSON.stringify({
        enabled: $("#notion-enabled")?.checked ?? false,
        default_database_id: $("#notion-default-db")?.value?.trim() || "",
        databases: {
          tickets: $("#notion-db-tickets")?.value?.trim() || "",
          deposits: $("#notion-db-deposits")?.value?.trim() || "",
          finance_ledger: $("#notion-db-finance-ledger")?.value?.trim() || "",
          users: $("#notion-db-users")?.value?.trim() || "",
        },
        sync_events,
      })});
      showToast("Параметры Notion сохранены");
      await loadNotion();
    });
    $("#notion-search-btn")?.addEventListener("click", () => notionSearch());
    $("#notion-search-q")?.addEventListener("keydown", (e) => { if (e.key === "Enter") notionSearch(); });
    $("#notion-db-schema-btn")?.addEventListener("click", () => {
      loadNotionDbSchema($("#notion-explore-db-id")?.value?.trim());
    });
    $("#notion-db-query-btn")?.addEventListener("click", () => {
      loadNotionDbQuery($("#notion-explore-db-id")?.value?.trim());
    });
    $("#notion-ledger-create-btn")?.addEventListener("click", async () => {
      const parentId = $("#notion-ledger-parent-id")?.value?.trim();
      if (!parentId) { showToast("Укажите Parent Page ID", true); return; }
      try {
        const res = await api("/notion/finance-ledger/create", {
          method: "POST", body: JSON.stringify({ parent_page_id: parentId }),
        });
        showToast(`База создана: ${res.database_id}`);
        $("#notion-ledger-validation").textContent = JSON.stringify(res.validation || res, null, 2);
        await loadNotion();
        renderNotionLedger();
      } catch (e) { showToast(e.message, true); }
    });
    $("#notion-ledger-link-btn")?.addEventListener("click", async () => {
      const dbId = $("#notion-ledger-link-id")?.value?.trim();
      if (!dbId) { showToast("Укажите Database ID", true); return; }
      try {
        const res = await api("/notion/finance-ledger/link", {
          method: "POST", body: JSON.stringify({ database_id: dbId }),
        });
        showToast("База привязана");
        $("#notion-ledger-validation").textContent = JSON.stringify(res.validation || res, null, 2);
        await loadNotion();
        renderNotionLedger();
      } catch (e) { showToast(e.message, true); }
    });
    $("#notion-ledger-validate-btn")?.addEventListener("click", async () => {
      const dbId = $("#notion-ledger-link-id")?.value?.trim();
      if (!dbId) { showToast("Укажите Database ID", true); return; }
      try {
        const res = await api(`/notion/finance-ledger/validate?database_id=${encodeURIComponent(dbId)}`);
        $("#notion-ledger-validation").textContent = JSON.stringify(res, null, 2);
        showToast(res.ok ? "Схема совместима" : "Есть расхождения", !res.ok);
      } catch (e) { showToast(e.message, true); }
    });
    $("#notion-ledger-find-btn")?.addEventListener("click", async () => {
      try {
        const res = await api("/notion/search", {
          method: "POST", body: JSON.stringify({ query: "Учет доходов XanaXGSM", page_size: 10 }),
        });
        const hit = (res.results || []).find((r) => r.object === "database");
        if (hit) {
          $("#notion-ledger-link-id").value = hit.id;
          showToast("База найдена");
          $("#notion-ledger-validate-btn")?.click();
        } else {
          showToast("База не найдена в workspace", true);
        }
      } catch (e) { showToast(e.message, true); }
    });
    $("#fin-refresh-wallets")?.addEventListener("click", () => loadFinanceWallets());
    $("#fin-refresh-deposits")?.addEventListener("click", () => loadFinanceDeposits());
    $("#fin-deposit-filter")?.addEventListener("change", () => loadFinanceDeposits());
    $("#fin-refresh-balances")?.addEventListener("click", () => loadFinanceBalances());
    $("#fin-config-form")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      await api("/finance/config", { method: "PUT", body: JSON.stringify({
        min_deposit_usdt: Number(fd.get("min_deposit_usdt")),
        max_deposit_usdt: Number(fd.get("max_deposit_usdt")),
        deposit_ttl_hours: Number(fd.get("deposit_ttl_hours")),
        instruction_text: fd.get("instruction_text"),
      })});
      showToast("Настройки финансов сохранены");
    });
    $("#fin-wallet-add")?.addEventListener("click", () => {
      openModal("Новый USDT-кошелёк", [
        { label: "Адрес", name: "address", attrs: "required" },
        { label: "Метка", name: "label" },
        { label: "Сеть", name: "network", attrs: 'value="TRC20"' },
        { label: "Активен", name: "is_active", attrs: 'type="checkbox" checked' },
        { label: "Заметки", name: "notes" },
      ], async (fd) => {
        await api("/finance/wallets", { method: "POST", body: JSON.stringify({
          address: fd.get("address"),
          label: fd.get("label") || null,
          network: fd.get("network") || "TRC20",
          is_active: fd.get("is_active") === "on",
          notes: fd.get("notes") || null,
        })});
        showToast("Кошелёк добавлен");
        loadFinanceWallets();
      });
    });
    $("#audit-refresh")?.addEventListener("click", () => loadAudit());
    $("#audit-category")?.addEventListener("change", () => loadAudit());
    $("#system-refresh")?.addEventListener("click", () => loadSystemRegistry());
    $$(".dash-tab").forEach((b) => {
      if (!b.dataset.finTab && !b.dataset.notionTab) b.onclick = () => switchDashTab(b.dataset.dashTab);
    });
    $("#dash-refresh-btn")?.addEventListener("click", () => {
      dashStatsCache = null;
      loadDashAnalytics().catch((e) => showToast(e.message, true));
    });
    $("#dash-days")?.addEventListener("change", () => {
      dashStatsCache = null;
      loadDashAnalytics().catch((e) => showToast(e.message, true));
    });
    $$(".chip[data-group-filter]").forEach((c) => c.onclick = () => {
      $$(".chip[data-group-filter]").forEach((x) => x.classList.remove("active"));
      c.classList.add("active");
      groupFilter = c.dataset.groupFilter;
      renderGroupCards();
    });
    $("#ticket-dialog-close")?.addEventListener("click", () => $("#ticket-dialog")?.close());
    $("#sd-refresh-btn")?.addEventListener("click", () => loadServiceDesk());
    $("#sd-next-btn")?.addEventListener("click", () => selectNextNewTicket());
    $("#sd-auto")?.addEventListener("change", startSdAutoRefresh);
    $("#notifications-form")?.addEventListener("submit", saveNotifications);
    $("#softphone-form")?.addEventListener("submit", saveSoftphoneSettings);
    $("#sp-reset-env")?.addEventListener("click", () => {
      if (!spData?.env_defaults) return;
      if (!confirm("Подставить значения из .env? Несохранённые изменения будут потеряны.")) return;
      fillSoftphoneForm(spData.env_defaults);
    });
    $("#nf-reset-env")?.addEventListener("click", () => {
      if (!nfData?.env_defaults) return;
      if (!confirm("Вернуть значения из .env? Несохранённые изменения будут потеряны.")) return;
      fillNotificationForm(nfData.env_defaults);
    });
    $$(".chip[data-sd-filter]").forEach((c) => c.onclick = () => {
      $$(".chip[data-sd-filter]").forEach((x) => x.classList.remove("active"));
      c.classList.add("active");
      sdFilter = c.dataset.sdFilter;
      renderQueue();
    });
    $("#goto-sd")?.addEventListener("click", (e) => { e.preventDefault(); navigateSection("service-desk"); });
    $("#logout-btn")?.addEventListener("click", async () => {
      const logoutUrl = window.SIPCRM ? SIPCRM.api("auth/logout") : "/api/auth/logout";
      await fetch(logoutUrl, { method: "POST", credentials: "same-origin" });
      goToLogin();
    });

    document.addEventListener("keydown", (e) => {
      if (e.target.matches("input, textarea, select") || document.querySelector("dialog[open]")) return;
      if (e.key === "/" && $(".section.active")?.id === "users") {
        e.preventDefault();
        $("#user-search")?.focus();
      }
      if ($(".section.active")?.id !== "service-desk") return;
      const filtered = filterSdTickets();
      const idx = filtered.findIndex((t) => t.id === sdSelectedId);
      const key = e.key.toLowerCase();
      if (key === "j" || e.key === "ArrowDown") {
        if (idx < filtered.length - 1) {
          e.preventDefault();
          sdSelectedId = filtered[idx + 1].id;
          renderQueue();
          loadTicketDetail(sdSelectedId);
        }
      }
      if (key === "k" || e.key === "ArrowUp") {
        if (idx > 0) {
          e.preventDefault();
          sdSelectedId = filtered[idx - 1].id;
          renderQueue();
          loadTicketDetail(sdSelectedId);
        }
      }
      if (!sdSelectedId) return;
      if (key === "t") { e.preventDefault(); clickSdAction("take"); }
      if (key === "w") { e.preventDefault(); clickSdAction("waiting_info"); }
      if (key === "r") { e.preventDefault(); clickSdAction("resolved"); }
      if (key === "x") { e.preventDefault(); clickSdAction("rejected"); }
      if (key === "n") { e.preventDefault(); selectNextNewTicket(); }
    });

    $("#add-sip-btn")?.addEventListener("click", () => openModal("Добавить SIP", [
      { label: "Telegram ID", name: "telegram_id", attrs: 'type="number" required' },
      { label: "SIP-номер", name: "sip_number", attrs: "required" },
      { label: "Описание", name: "description" },
      { label: "SIP login (Device)", name: "auth_username", attrs: 'placeholder="если отличается от номера"' },
      { label: "SIP password", name: "auth_password", attrs: 'type="password" autocomplete="new-password"' },
    ], async (fd) => {
      const body = {
        telegram_id: Number(fd.get("telegram_id")),
        sip_number: fd.get("sip_number"),
        description: fd.get("description") || null,
      };
      const authUser = fd.get("auth_username")?.trim();
      const authPass = fd.get("auth_password");
      if (authUser) body.auth_username = authUser;
      if (authPass) body.auth_password = authPass;
      const res = await api("/sips", { method: "POST", body: JSON.stringify(body) });
      showToast(res.reactivated ? "SIP реактивирован" : "SIP добавлен"); loadSips();
    }));
  }

  window.addEventListener("error", (e) => {
    showToast(e.message || "Ошибка интерфейса", true);
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
