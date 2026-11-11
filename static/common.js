/* Plex Downloader – wspólne narzędzia: tłumaczenia, API, formatowanie, nagłówek, okna, podpowiedzi ⓘ */
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* tryb prywatny */ } },
  };
  const CAT = window.I18N || {};
  const LANG = window.LANG || "en";
  // t("Removed: {n}", {n: 3}) – tekst źródłowy po angielsku, tłumaczenie z locales/<lang>.json
  function t(s, vars) {
    let out = CAT[s] || s;
    if (vars) out = out.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
    return out;
  }
  const LOCALE = LANG === "en" ? "en-GB" : LANG;

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
    if (!res.ok) throw new Error(data.error || (t("Error") + " " + res.status));
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

  // kopiowanie do schowka – działa także na zwykłym http (bez HTTPS) w sieci domowej
  async function copyText(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(text); return true; }
    } catch (e) { /* spróbujemy niżej */ }
    const ta = el("textarea"); ta.value = text; ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;top:-1000px;opacity:0";
    (document.querySelector("dialog[open]") || document.body).appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    ta.remove();
    return ok;
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
      const w = win.offsetWidth;
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

  // ------------------------------------------------------------------ TMDB key check (wizard + Settings)
  function tmdbChecker(input, out) {
    let timer = null, seq = 0;
    const set = (cls, text) => { out.className = "key-st " + cls; out.textContent = text; };
    const run = async (useSaved) => {
      const key = input.value.trim();
      if (!key && !useSaved) { set("", ""); return; }
      const my = ++seq;
      set("muted", t("Checking the key…"));
      try {
        const r = await api("/api/tmdb/check", { key });
        if (my !== seq) return;
        if (r.ok === true) set("ok", "✓ " + r.message);
        else if (r.ok === false) set("bad", "✗ " + r.message);
        else set("warn", "! " + r.message);
      } catch (e) { if (my === seq) set("warn", "! " + e.message); }
    };
    input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => run(false), 700); });
    return run;
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
      const btns = [];
      (buttons || [{ label: "OK", value: true, cls: "btn-accent" }]).forEach((b) => {
        const btn = el("button", b.cls || "btn-soft", b.label); btn.type = "button";
        if (b.disabled) { btn.disabled = true; btn.dataset.off = "1"; }
        if (b.id) btn.dataset.id = b.id;
        btn.addEventListener("click", async () => {
          let v = typeof b.value === "function" ? b.value() : b.value;
          if (v && typeof v.then === "function") {   // async action (e.g. a confirmation) – keep the window until done
            btns.forEach((x) => { x.disabled = true; });
            try { v = await v; } finally { btns.forEach((x) => { x.disabled = !!x.dataset.off; }); }
          }
          if (v === undefined) return;
          d.close(); resolve(v);
        });
        foot.appendChild(btn); btns.push(btn);
      });
      x.addEventListener("click", () => { d.close(); resolve(null); });
      d.addEventListener("cancel", () => resolve(null));
      d.addEventListener("close", () => setTimeout(() => d.remove(), 50));
      if (danger) d.classList.add("danger");
      d.append(head, bodyEl, foot);
      d._buttons = btns;
      document.body.appendChild(d);
      makeDraggable(d);
      centerWindow(d);
      d.showModal();
      if (typeof body === "object" && body && body._onOpen) body._onOpen(d);
    });
  }

  // powiadomienia – w „top layer” (popover), więc są widoczne także nad otwartym oknem Ustawień
  function toast(msg, bad) {
    let box = $("#toasts");
    if (!box) {
      box = el("div"); box.id = "toasts";
      if (box.showPopover) box.setAttribute("popover", "manual");
      document.body.appendChild(box);
    }
    if (box.showPopover) { try { box.hidePopover(); } catch (e) { /* */ } try { box.showPopover(); } catch (e) { /* */ } }
    else { const d = $$("dialog[open]").pop(); (d || document.body).appendChild(box); }
    const n = el("div", "toast" + (bad ? " bad" : ""), msg);
    box.appendChild(n);
    setTimeout(() => n.classList.add("out"), 3800);
    setTimeout(() => { n.remove(); if (!box.childElementCount && box.hidePopover) { try { box.hidePopover(); } catch (e) { /* */ } } }, 4300);
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
    head.append(el("b", null, t("Hint")));
    const x = el("button", "icon-btn"); x.type = "button"; x.appendChild(icon("x")); x.addEventListener("click", closeTip);
    head.appendChild(x);
    // "\n\n" in a tooltip = new paragraph
    tip.appendChild(head);
    (b.dataset.tip || "").split(/\n\s*\n/).forEach((part) => tip.appendChild(el("p", null, part.trim())));
    if (b.dataset.href) {
      const a = el("a", null, t("More information") + " ↗"); a.href = b.dataset.href; a.target = "_blank"; a.rel = "noopener noreferrer";
      tip.appendChild(a);
    }
    (b.closest("dialog") || document.body).appendChild(tip);
    const r = b.getBoundingClientRect();
    const host = b.closest("dialog");
    // granice: okno dialogowe (ma overflow: hidden) albo cała strona
    const box = host ? host.getBoundingClientRect() : { left: 0, top: 0, right: window.innerWidth, bottom: window.innerHeight, width: window.innerWidth };
    const w = Math.min(320, box.width - 24);
    tip.style.width = w + "px";
    const tr = host && getComputedStyle(host).transform !== "none";
    const offX = tr ? box.left : 0, offY = tr ? box.top : 0;
    tip.style.left = (Math.max(box.left + 12, Math.min(r.left - 20, box.right - w - 12)) - offX) + "px";
    const below = r.bottom + 8, h = tip.offsetHeight;
    tip.style.top = ((below + h > box.bottom - 8 ? Math.max(box.top + 8, r.top - h - 8) : below) - offY) + "px";
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
        ? t("Plex Downloader is running on {host} ({ip}:{port})", { host: s.server.hostname, ip: s.server.ip, port: s.server.port })
        : t("The aria2c download engine is not running");
      renderPlex(s.plex);
      renderVpn(s.vpn);
      window.PD.status = s;
      document.dispatchEvent(new CustomEvent("pd:status", { detail: s }));
    } catch (e) {
      if (e.message === "auth") return;
      $("#selfDot").classList.add("bad");
      $("#hdrServer").textContent = t("no connection");
    }
    statusTimer = setTimeout(refreshStatus, 15000);
  }
  function renderPlex(list) {
    const box = $("#plexStatus");
    if (!box) return;
    box.replaceChildren();
    if (!list.length) {
      const b = el("button", "hstat none"); b.type = "button";
      b.append(el("span", "dot off"), el("span", "hs-name", t("Plex: not found")));
      b.title = t("No Plex server found – click to add or search");
      b.addEventListener("click", () => window.PD.openSettings && window.PD.openSettings("plex"));
      box.appendChild(b);
      return;
    }
    list.forEach((p) => {
      const b = el("button", "hstat"); b.type = "button";
      b.append(el("span", "dot" + (p.online ? "" : " bad")), el("span", "hs-name", p.name),
        el("span", "hs-addr", `${p.display_host}:${p.port}`));
      b.title = t("Plex Media Server “{name}” – {state}", { name: p.name, state: p.online ? "online" : "offline" }) +
        (p.version ? `, ${t("version")} ${p.version}` : "") + ` · ${p.display_host}:${p.port}` +
        (p.source === "manual" ? ` (${t("added manually")})` : ` (${t("discovered automatically")})`);
      b.addEventListener("click", () => window.PD.openSettings && window.PD.openSettings("plex"));
      box.appendChild(b);
    });
  }

  // VPN badge: grey = not set up, amber = needs attention, green = connected
  function renderVpn(v) {
    const box = $("#vpnStatus");
    if (!box || !v) return;
    const b = el("button", "hstat vpn"); b.type = "button";
    let dot = "off", label = "VPN", tip;
    if (!v.installed) tip = t("VPN is not set up – click to see how to open the panel from outside your home");
    else if (v.state === "Running") {
      dot = ""; tip = t("Tailscale VPN connected · {ip}", { ip: v.ip || "?" }) +
        (v.via_vpn ? " · " + t("you are connected over VPN right now") : "");
    } else if (v.state === "NeedsLogin" || v.state === "NeedsMachineAuth") {
      dot = "warn"; tip = t("Tailscale is installed but not logged in – click to log in");
    } else { dot = "warn"; tip = t("Tailscale is switched off – click for details"); }
    b.append(icon("shield"), el("span", "dot " + dot), el("span", "hs-name", label));
    if (v.state === "Running" && v.ip) b.append(el("span", "hs-addr", v.ip));
    b.classList.add(dot === "" ? "on" : dot);
    if (v.via_vpn) b.classList.add("via");
    b.title = tip;
    b.addEventListener("click", () => window.PD.openSettings && window.PD.openSettings("vpn"));
    box.replaceChildren(b);
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

  // ------------------------------------------------------------------ disk tiles: order (drag & drop) and name (gear)
  const DISK_DT = "application/x-plexdl-disk";
  let dragDisk = null;
  function saveDiskOrder(box) {
    const ids = $$("[data-disk-id]", box).map((x) => x.dataset.diskId);
    return api("/api/disks/order", { ids }).then(() => document.dispatchEvent(new CustomEvent("pd:settings-saved")))
      .catch((e) => toast(e.message, true));
  }
  // tile: a disk button with data-disk-id; box: its container
  function diskTile(tile, d, box) {
    tile.dataset.diskId = d.id;
    tile.draggable = true;
    tile.addEventListener("dragstart", (e) => {
      dragDisk = tile; tile.classList.add("dragging");
      e.dataTransfer.setData(DISK_DT, d.id); e.dataTransfer.effectAllowed = "move";
    });
    tile.addEventListener("dragend", () => {
      tile.classList.remove("dragging");
      if (dragDisk) { dragDisk = null; saveDiskOrder(box); }
    });
    tile.addEventListener("dragover", (e) => {
      if (!dragDisk || dragDisk === tile || dragDisk.parentNode !== box) return;
      e.preventDefault(); e.dataTransfer.dropEffect = "move";
      const r = tile.getBoundingClientRect();
      const after = e.clientX > r.left + r.width / 2;
      box.insertBefore(dragDisk, after ? tile.nextSibling : tile);
    });
    tile.addEventListener("drop", (e) => { if (dragDisk) e.preventDefault(); });
    // gear: rename (max 16 characters) and move left / right (also on phones)
    const g = el("span", "disk-gear"); g.setAttribute("role", "button"); g.tabIndex = 0;
    g.title = t("Disk name and order"); g.appendChild(icon("gear"));
    const open = async (e) => {
      e.preventDefault(); e.stopPropagation();
      const body = el("div");
      const inp = el("input", "input"); inp.value = d.label; inp.maxLength = 16;
      const cnt = el("span", "muted small-count", `${inp.value.length}/16`);
      inp.addEventListener("input", () => { cnt.textContent = `${inp.value.length}/16`; });
      const lab = el("label", "small-label", t("Button name")); lab.append(" ", cnt);
      body.append(lab, inp, el("p", "hint", t("The order can also be changed by dragging the disk tiles.")));
      body._onOpen = () => { inp.focus(); inp.select(); };
      const tiles = $$("[data-disk-id]", box);
      const i = tiles.indexOf(tile);
      const v = await modal({ title: t("Disk: {name}", { name: d.label }), body,
        buttons: [{ label: "◀ " + t("Move left"), value: "left", disabled: i <= 0 },
          { label: t("Move right") + " ▶", value: "right", disabled: i >= tiles.length - 1 },
          { label: t("Cancel"), value: false }, { label: t("Save"), value: "save", cls: "btn-accent" }] });
      if (v === "left" || v === "right") {
        if (v === "left") box.insertBefore(tile, tiles[i - 1]); else box.insertBefore(tile, tiles[i + 1].nextSibling);
        saveDiskOrder(box);
      } else if (v === "save" && inp.value.trim() && inp.value.trim() !== d.label) {
        try {
          await api("/api/disks/rename", { id: d.id, label: inp.value });
          document.dispatchEvent(new CustomEvent("pd:settings-saved"));
        } catch (er) { toast(er.message, true); }
      }
    };
    g.addEventListener("click", open);
    g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") open(e); });
    tile.appendChild(g);
  }

  window.PD = { $, $$, store, t, LANG, LOCALE, api, fmtSize, fmtSpeed, fmtEta, el, icon, catIcon, modal, toast,
    copyText, makeDraggable, centerWindow, refreshStatus, diskTile, tmdbChecker, openSettings: null, status: null };
})();
