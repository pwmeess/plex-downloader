/* Plex Downloader – wspólne narzędzia: API, formatowanie, nagłówek, okna, podpowiedzi ⓘ */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* tryb prywatny */ } },
  };

  async function api(path, body) {
    const opt = body === undefined ? {} : {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-PlexDL": "1" },
      body: JSON.stringify(body),
    };
    const res = await fetch(path, Object.assign({ credentials: "same-origin" }, opt));
    if (res.status === 401) { location.href = "/login"; throw new Error("auth"); }
    let data = {};
    try { data = await res.json(); } catch (e) { /* brak treści */ }
    if (!res.ok) throw new Error(data.error || ("Błąd " + res.status));
    return data;
  }

  const GB = 1024 ** 3, MB = 1024 ** 2;
  function fmtSize(b) {
    if (b == null) return "?";
    if (b >= GB * 100) return Math.round(b / GB) + " GB";
    if (b >= GB) return (b / GB).toFixed(1) + " GB";
    if (b >= MB) return Math.round(b / MB) + " MB";
    return Math.max(0, Math.round(b / 1024)) + " kB";
  }
  function fmtSpeed(b) { return b >= MB ? (b / MB).toFixed(1) + " MB/s" : Math.round(b / 1024) + " kB/s"; }
  function fmtEta(s) {
    if (s == null) return "—";
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
    const p = (n) => String(n).padStart(2, "0");
    return h ? `${h}:${p(m)}:${p(x)} h` : `${p(m)}:${p(x)} min`;
  }
  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function icon(id) {
    const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("class", "i");
    const u = document.createElementNS("http://www.w3.org/2000/svg", "use");
    u.setAttribute("href", "#i-" + id);
    s.appendChild(u);
    return s;
  }
  function catIcon(c) {
    if (!c) return "cat";
    if (c.kind === "tv") return "tv";
    if (c.id === "kids") return "kids";
    if (c.id === "movies") return "film";
    return "cat";
  }

  // ------------------------------------------------------------------ przeciąganie okien
  function makeDraggable(win) {
    const head = win.querySelector("[data-drag]");
    if (!head) return;
    let sx = 0, sy = 0, ox = 0, oy = 0, drag = false;
    head.addEventListener("pointerdown", (e) => {
      if (e.target.closest("button, a, input, select") || window.innerWidth < 760) return;
      const r = win.getBoundingClientRect();
      drag = true; sx = e.clientX; sy = e.clientY; ox = r.left; oy = r.top;
      win.style.left = ox + "px"; win.style.top = oy + "px"; win.style.transform = "none";
      head.setPointerCapture(e.pointerId);
      win.classList.add("dragging");
    });
    head.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const w = win.offsetWidth, h = win.offsetHeight;
      const x = Math.min(Math.max(ox + e.clientX - sx, 40 - w), window.innerWidth - 40);
      const y = Math.min(Math.max(oy + e.clientY - sy, 0), window.innerHeight - 40);
      win.style.left = x + "px"; win.style.top = y + "px";
    });
    const end = () => { drag = false; win.classList.remove("dragging"); };
    head.addEventListener("pointerup", end);
    head.addEventListener("pointercancel", end);
  }
  function centerWindow(win) {
    if (window.innerWidth < 560 && !win.classList.contains("modal")) {
      win.style.left = win.style.top = win.style.transform = ""; return; // telefon: pełny ekran z CSS
    }
    win.style.left = "50%"; win.style.top = "50%"; win.style.transform = "translate(-50%, -50%)";
  }

  // ------------------------------------------------------------------ okno potwierdzenia
  function modal({ title, body, buttons, danger, wide }) {
    return new Promise((resolve) => {
      const d = el("dialog", "window modal" + (wide ? " wide" : ""));
      const head = el("div", "win-head"); head.dataset.drag = "";
      head.appendChild(el("h2", null, title));
      const x = el("button", "icon-btn win-close"); x.type = "button"; x.appendChild(icon("x"));
      head.appendChild(x);
      const bodyEl = el("div", "win-body");
      if (typeof body === "string") bodyEl.appendChild(el("p", null, body)); else if (body) bodyEl.appendChild(body);
      const foot = el("div", "win-foot");
      (buttons || [{ label: "OK", value: true, cls: "btn-accent" }]).forEach((b) => {
        const btn = el("button", b.cls || "btn-soft", b.label); btn.type = "button";
        if (b.disabled) btn.disabled = true;
        btn.addEventListener("click", () => { d.close(); resolve(b.value); });
        foot.appendChild(btn);
      });
      x.addEventListener("click", () => { d.close(); resolve(null); });
      d.addEventListener("cancel", () => resolve(null));
      d.addEventListener("close", () => setTimeout(() => d.remove(), 50));
      if (danger) d.classList.add("danger");
      d.append(head, bodyEl, foot);
      document.body.appendChild(d);
      makeDraggable(d);
      centerWindow(d);
      d.showModal();
    });
  }
  function toast(msg, bad) {
    let box = $("#toasts");
    if (!box) { box = el("div"); box.id = "toasts"; document.body.appendChild(box); }
    const t = el("div", "toast" + (bad ? " bad" : ""), msg);
    box.appendChild(t);
    setTimeout(() => t.classList.add("out"), 3800);
    setTimeout(() => t.remove(), 4300);
  }

  // ------------------------------------------------------------------ podpowiedzi ⓘ
  let tip = null;
  function closeTip() { if (tip) { tip.remove(); tip = null; } }
  document.addEventListener("click", (e) => {
    const b = e.target.closest(".info-i");
    if (!b) { if (tip && !e.target.closest(".tip-pop")) closeTip(); return; }
    e.preventDefault(); e.stopPropagation();
    if (tip && tip._for === b) { closeTip(); return; }
    closeTip();
    tip = el("div", "tip-pop"); tip._for = b;
    const head = el("div", "tip-head");
    head.append(el("b", null, "Podpowiedź"));
    const x = el("button", "icon-btn"); x.type = "button"; x.appendChild(icon("x")); x.addEventListener("click", closeTip);
    head.appendChild(x);
    tip.append(head, el("p", null, b.dataset.tip || ""));
    if (b.dataset.href) {
      const a = el("a", null, "Więcej informacji ↗"); a.href = b.dataset.href; a.target = "_blank"; a.rel = "noopener noreferrer";
      tip.appendChild(a);
    }
    (b.closest("dialog") || document.body).appendChild(tip);
    const r = b.getBoundingClientRect();
    const w = Math.min(320, window.innerWidth - 24);
    tip.style.width = w + "px";
    tip.style.left = Math.max(12, Math.min(r.left - 20, window.innerWidth - w - 12)) + "px";
    const below = r.bottom + 8, h = tip.offsetHeight;
    tip.style.top = (below + h > window.innerHeight - 8 ? Math.max(8, r.top - h - 8) : below) + "px";
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeTip(); });

  // ------------------------------------------------------------------ nagłówek: statusy
  let statusTimer = null;
  async function refreshStatus() {
    clearTimeout(statusTimer);
    try {
      const s = await api("/api/status");
      $("#selfDot").classList.toggle("bad", !s.engine.ok);
      $("#hdrServer").textContent = `${s.server.ip}:${s.server.port}`;
      $("#hdrServer").parentElement.title = s.engine.ok
        ? `Plex Downloader działa na ${s.server.hostname} (${s.server.ip}:${s.server.port})`
        : "Silnik pobierania aria2c nie działa";
      renderPlex(s.plex);
      document.dispatchEvent(new CustomEvent("pd:status", { detail: s }));
    } catch (e) {
      if (e.message === "auth") return;
      $("#selfDot").classList.add("bad");
      $("#hdrServer").textContent = "brak połączenia";
    }
    statusTimer = setTimeout(refreshStatus, 15000);
  }
  function renderPlex(list) {
    const box = $("#plexStatus");
    if (!box) return;
    box.replaceChildren();
    if (!list.length) {
      const b = el("button", "hstat none"); b.type = "button";
      b.append(el("span", "dot off"), el("span", "hs-name", "Plex: nie wykryto"));
      b.title = "Nie wykryto serwera Plex – kliknij, aby dodać lub wyszukać";
      b.addEventListener("click", () => window.PD.openSettings && window.PD.openSettings("plex"));
      box.appendChild(b);
      return;
    }
    list.forEach((p) => {
      const b = el("button", "hstat"); b.type = "button";
      b.append(el("span", "dot" + (p.online ? "" : " bad")), el("span", "hs-name", p.name),
        el("span", "hs-addr", `${p.display_host}:${p.port}`));
      b.title = `Plex Media Server „${p.name}” – ${p.online ? "online" : "offline"}` +
        (p.version ? `, wersja ${p.version}` : "") + ` · ${p.display_host}:${p.port}` +
        (p.source === "manual" ? " (dodany ręcznie)" : " (wykryty automatycznie)");
      b.addEventListener("click", () => window.PD.openSettings && window.PD.openSettings("plex"));
      box.appendChild(b);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const lo = $("#logoutBtn");
    if (lo) lo.addEventListener("click", async () => {
      await fetch("/logout", { method: "POST", credentials: "same-origin" });
      location.href = "/login";
    });
    if ($("#plexStatus")) refreshStatus();
    document.addEventListener("visibilitychange", () => { if (!document.hidden && $("#plexStatus")) refreshStatus(); });
  });

  window.PD = { $, $$, store, api, fmtSize, fmtSpeed, fmtEta, el, icon, catIcon, modal, toast,
    makeDraggable, centerWindow, refreshStatus, openSettings: null };
})();
