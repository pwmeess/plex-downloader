(() => {
  "use strict";

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* tryb prywatny */ } },
  };

  const VIDEO_EXTS = [".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".ts", ".m2ts", ".mpg",
    ".mpeg", ".webm", ".flv", ".divx", ".ogm", ".vob"];
  const STATUS = {
    queued: "Oczekuje", downloading: "Pobieranie", paused: "Wstrzymano", finalizing: "Finalizowanie",
    cancelling: "Anulowanie…", done: "Zakończono", error: "Błąd",
  };

  const st = {
    kind: "movie",
    diskId: store.get("plexdl.disk"),
    disks: [],
    jobs: [],
    probe: null,
    dirty: {},          // pola edytowane ręcznie – nie nadpisujemy ich podpowiedzią
    kindTouched: false,
    online: true,
  };

  // ------------------------------------------------------------------ API
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

  // ------------------------------------------------------------------ formatowanie
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
  function sanitize(s) {
    return (s || "").replace(/[<>:"/\\|?*\x00-\x1f]/g, " ").replace(/\s+/g, " ").replace(/^[\s.]+|[\s.]+$/g, "");
  }
  function normExt(e) {
    e = (e || "").trim().toLowerCase();
    if (e && !e.startsWith(".")) e = "." + e;
    return e;
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

  // ------------------------------------------------------------------ formularz
  const urlIn = $("#url"), nameIn = $("#name"), showIn = $("#show"), seasonIn = $("#season"),
    epIn = $("#episode"), epTitleIn = $("#epTitle"), extMovie = $("#extMovie"), extTv = $("#extTv");

  function ext() { return normExt(st.kind === "tv" ? extTv.value : extMovie.value); }
  function setExt(v) { extMovie.value = v; extTv.value = v; }
  [extMovie, extTv].forEach((inp) => inp.addEventListener("input", () => {
    st.dirty.ext = true;
    (inp === extMovie ? extTv : extMovie).value = inp.value;
    updatePreview();
  }));

  function setKind(kind, byUser) {
    st.kind = kind;
    if (byUser) st.kindTouched = true;
    $$(".segmented button").forEach((b) => b.classList.toggle("on", b.dataset.kind === kind));
    $("#movieFields").hidden = kind !== "movie";
    $("#tvFields").hidden = kind !== "tv";
    renderDisks();
    updatePreview();
  }
  $$(".segmented button").forEach((b) => b.addEventListener("click", () => setKind(b.dataset.kind, true)));

  [[nameIn, "name"], [showIn, "show"], [seasonIn, "season"], [epIn, "episode"], [epTitleIn, "epTitle"]]
    .forEach(([inp, key]) => inp.addEventListener("input", () => { st.dirty[key] = true; updatePreview(); }));

  function selectedDisk() { return st.disks.find((d) => d.id === st.diskId); }

  function targetPath() {
    const d = selectedDisk();
    const e = ext();
    if (st.kind === "tv") {
      const show = sanitize(showIn.value);
      if (!show) return null;
      const s = parseInt(seasonIn.value, 10), ep = parseInt(epIn.value, 10);
      if (isNaN(s) || isNaN(ep)) return null;
      const p2 = (n) => String(n).padStart(2, "0");
      let file = `${show} - S${p2(s)}E${p2(ep)}`;
      const t = sanitize(epTitleIn.value);
      if (t) file += " - " + t;
      return { base: d ? d.tv : "…/TV Shows", dir: `${show}/Season ${p2(s)}`, file: file + e };
    }
    const name = sanitize(nameIn.value);
    if (!name) return null;
    return { base: d ? d.movies : "…/Movies", dir: name, file: name + e };
  }

  function updatePreview() {
    const p = targetPath(), box = $("#preview");
    if (!p) { box.hidden = true; return; }
    box.hidden = false;
    box.replaceChildren(document.createTextNode(p.base + "/"), el("b", null, p.dir + "/" + p.file));
    const hint = $("#nameHint");
    if (st.kind === "movie" && !/\(\d{4}\)$/.test(nameIn.value.trim())) {
      hint.replaceChildren(el("span", "warn", "Dodaj rok w nawiasie – Plex lepiej dopasuje film, np. „Tytuł (2015)”."));
    } else hint.replaceChildren();
  }

  // ---- sprawdzanie linku
  let probeTimer = null, probeSeq = 0;
  urlIn.addEventListener("input", () => {
    clearTimeout(probeTimer);
    st.probe = null;
    st.dirty = {};
    st.kindTouched = false;
    const v = urlIn.value.trim();
    if (!/^https?:\/\/\S+/i.test(v)) { $("#probeInfo").replaceChildren(); return; }
    $("#probeInfo").replaceChildren(el("span", null, "Sprawdzam link…"));
    probeTimer = setTimeout(() => runProbe(v), 450);
  });

  async function runProbe(url) {
    const seq = ++probeSeq;
    try {
      const info = await api("/api/probe", { url });
      if (seq !== probeSeq) return;
      st.probe = info;
      applyGuess(info);
      const parts = [];
      if (info.reachable) {
        parts.push(el("span", "ok", "✓ Link działa"));
        if (info.size) parts.push(el("span", null, "Rozmiar: " + fmtSize(info.size)));
        parts.push(info.resumable
          ? el("span", null, "Wznawianie i pobieranie wielowątkowe: tak")
          : el("span", "warn", "Serwer nie obsługuje wznawiania – 1 połączenie"));
      } else {
        parts.push(el("span", "warn", "Nie udało się sprawdzić linku (" + (info.probe_error || "brak odpowiedzi") + "). Możesz spróbować pobrać mimo to."));
      }
      if (info.filename) parts.push(el("span", null, info.filename));
      $("#probeInfo").replaceChildren(...parts);
    } catch (e) {
      if (seq === probeSeq) $("#probeInfo").replaceChildren(el("span", "bad", e.message));
    }
  }

  function applyGuess(info) {
    const g = info.guess || {};
    if (!st.dirty.ext && info.ext) setExt(info.ext);
    if (!st.kindTouched && g.kind) setKind(g.kind, false);
    if (g.kind === "tv") {
      if (!st.dirty.show) showIn.value = g.show || "";
      if (!st.dirty.season && g.season != null) seasonIn.value = g.season;
      if (!st.dirty.episode && g.episode != null) epIn.value = g.episode;
    } else if (!st.dirty.name) {
      nameIn.value = g.name || "";
    }
    updatePreview();
  }

  $("#clearBtn").addEventListener("click", () => {
    $("#addForm").reset();
    seasonIn.value = 1; epIn.value = 1;
    st.probe = null; st.dirty = {}; st.kindTouched = false;
    $("#probeInfo").replaceChildren();
    $("#formMsg").textContent = "";
    setKind("movie", false);
    urlIn.focus();
  });

  // ---- dyski
  function renderDisks() {
    const box = $("#disks");
    box.replaceChildren();
    // zapamiętany dysk niedostępny → wybieramy pierwszy dostępny
    if (!st.disks.some((d) => d.id === st.diskId && d.ok)) {
      const firstOk = st.disks.find((d) => d.ok);
      if (firstOk) st.diskId = firstOk.id;
    }
    st.disks.forEach((d) => {
      const b = el("button", "disk" + (d.id === st.diskId ? " on" : ""));
      b.type = "button";
      b.disabled = !d.ok;
      b.title = st.kind === "tv" ? d.tv : d.movies;
      const ico = el("div", "ico"); ico.appendChild(icon("drive"));
      b.append(ico, el("div", "name", d.label), el("div", "sub", d.subtitle || d.mount));
      if (d.ok) {
        const used = d.total ? (d.total - d.free) / d.total : 0;
        const bar = el("div", "bar" + (d.free / d.total < 0.05 ? " low" : ""));
        const fill = el("i"); fill.style.width = Math.max(2, used * 100).toFixed(1) + "%";
        bar.appendChild(fill);
        b.append(bar, el("div", "free", `Wolne: ${fmtSize(d.free).replace(" GB", "")} / ${fmtSize(d.total)}`));
      } else {
        b.append(el("div", "problem", d.problem || "Niedostępny"));
      }
      b.addEventListener("click", () => { st.diskId = d.id; store.set("plexdl.disk", d.id); renderDisks(); updatePreview(); });
      box.appendChild(b);
    });
  }

  // ---- wysyłka
  $("#addForm").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const msg = $("#formMsg");
    msg.className = "form-msg"; msg.textContent = "";
    const e = ext();
    if (!VIDEO_EXTS.includes(e)) { msg.className = "form-msg bad"; msg.textContent = "Podaj rozszerzenie pliku wideo (np. .mkv lub .mp4)."; return; }
    if (!selectedDisk() || !selectedDisk().ok) { msg.className = "form-msg bad"; msg.textContent = "Wybierz dostępny dysk docelowy."; return; }
    const body = {
      url: urlIn.value.trim(), kind: st.kind, disk_id: st.diskId, ext: e,
      name: nameIn.value, show: showIn.value, season: seasonIn.value, episode: epIn.value,
      episode_title: epTitleIn.value, size: st.probe && st.probe.size,
    };
    const btn = $("#submitBtn");
    btn.disabled = true;
    try {
      const r = await api("/api/jobs", body);
      msg.className = "form-msg ok";
      msg.textContent = "Dodano do kolejki: " + r.job.filename;
      const keepKind = st.kind;
      $("#clearBtn").click();
      msg.className = "form-msg ok";
      msg.textContent = "Dodano do kolejki: " + r.job.filename;
      if (keepKind === "tv") { // przy serialach zostawiamy nazwę i sezon – wygodne przy kolejnych odcinkach
        setKind("tv", true);
        showIn.value = body.show; seasonIn.value = body.season; epIn.value = (parseInt(body.episode, 10) || 0) + 1;
        st.dirty = { show: true, season: true, episode: true };
        updatePreview();
      }
      refresh(true);
    } catch (err) {
      msg.className = "form-msg bad";
      msg.textContent = err.message;
    } finally {
      btn.disabled = false;
    }
  });

  // ------------------------------------------------------------------ lista zadań
  const jobEls = new Map();

  function jobAction(id, action) {
    return api(`/api/jobs/${id}/${action}`, {}).then(() => refresh(true)).catch((e) => alert(e.message));
  }
  function actBtn(label, cls, ico, fn) {
    const b = el("button", cls);
    b.type = "button";
    if (ico) b.appendChild(icon(ico));
    if (label) b.appendChild(document.createTextNode(label));
    b.addEventListener("click", fn);
    return b;
  }

  function buildJob(j) {
    const compact = j.status === "done" || j.status === "error";
    const n = el("div", "job " + j.status + (compact ? " compact" : ""));
    n.dataset.sig = j.status;
    if (compact) {
      const badge = el("span", "badge " + j.status, STATUS[j.status]);
      const title = el("span", "job-title", j.filename);
      const rest = el("span", "rest");
      rest.textContent = j.status === "done"
        ? `${fmtSize(j.total)} · Zapisano na: ${j.disk_label}`
        : j.error;
      const acts = el("div", "job-actions");
      if (j.status === "error") acts.appendChild(actBtn("Ponów", "btn-soft small", "retry", () => jobAction(j.id, "retry")));
      const rm = actBtn("", "icon-btn", "x", () => jobAction(j.id, "remove"));
      rm.title = "Usuń z listy";
      acts.appendChild(rm);
      const txt = el("div", "txt");
      txt.append(title, rest);
      n.append(badge, txt, acts);
      if (j.status === "error") n.title = j.folder + "/" + j.filename;
      return n;
    }
    const title = el("div", "job-title", j.filename);
    const path = el("div", "job-path", j.folder + "/");
    const bar = el("div", "bar"); bar.appendChild(el("i"));
    const stats = el("div", "job-stats");
    const meta = el("div", "job-meta");
    const acts = el("div", "job-actions");
    if (j.status === "paused") acts.appendChild(actBtn("Wznów", "btn-soft small", "play", () => jobAction(j.id, "resume")));
    else if (j.status === "downloading" || j.status === "queued") acts.appendChild(actBtn("Wstrzymaj", "btn-soft small", "pause", () => jobAction(j.id, "pause")));
    if (j.status !== "finalizing" && j.status !== "cancelling") {
      const c = actBtn("Anuluj ", "btn-soft small btn-danger", null, () => {
        if (confirm("Anulować pobieranie „" + j.filename + "”? Pobrane dane zostaną usunięte.")) jobAction(j.id, "cancel");
      });
      c.appendChild(icon("trash"));
      acts.appendChild(c);
    }
    const foot = el("div", "job-foot"); foot.append(meta, acts);
    n.append(title, path, bar, stats, foot);
    return n;
  }

  function updateJob(n, j) {
    if (n.classList.contains("compact")) return;
    n.querySelector(".bar > i").style.width = (j.status === "finalizing" ? 100 : j.percent) + "%";
    const s = n.querySelector(".job-stats");
    const sep = " • ";
    if (j.status === "downloading") {
      s.textContent = `${j.percent}% (${fmtSize(j.completed)} z ${j.total ? fmtSize(j.total) : "?"})` +
        sep + fmtSpeed(j.speed) + sep + "pozostało: " + fmtEta(j.eta);
    } else if (j.status === "finalizing") {
      s.textContent = "Przenoszenie pliku do biblioteki…";
    } else {
      s.textContent = STATUS[j.status] + (j.total ? ` · ${j.percent}% (${fmtSize(j.completed)} z ${fmtSize(j.total)})` : "");
    }
    const meta = n.querySelector(".job-meta");
    meta.replaceChildren(icon("net"), document.createTextNode(
      j.status === "downloading" ? `Połączenia: ${j.connections}/${j.max_connections || "?"}` : j.disk_label));
  }

  function renderJobs() {
    const box = $("#jobs");
    if (!st.jobs.length) {
      jobEls.clear();
      const e = el("div", "empty");
      e.appendChild(icon("down"));
      e.appendChild(el("div", null, "Brak pobierań. Wklej link po lewej, aby zacząć."));
      box.replaceChildren(e);
    } else {
      const seen = new Set();
      const ordered = st.jobs.map((j) => {
        seen.add(j.id);
        let n = jobEls.get(j.id);
        if (!n || n.dataset.sig !== j.status) { n = buildJob(j); jobEls.set(j.id, n); }
        updateJob(n, j);
        return n;
      });
      for (const id of Array.from(jobEls.keys())) if (!seen.has(id)) jobEls.delete(id);
      // podmieniamy kolejność bez niszczenia elementów (zachowuje animację paska)
      const current = Array.from(box.children);
      if (current.length !== ordered.length || current.some((c, i) => c !== ordered[i])) box.replaceChildren(...ordered);
    }
    $("#clearDone").hidden = !st.jobs.some((j) => j.status === "done");
    const active = st.jobs.filter((j) => j.status === "downloading");
    document.title = active.length
      ? `${active.length === 1 ? active[0].percent + "%" : active.length + "×"} · Plex Downloader`
      : "Plex Downloader";
  }
  $("#clearDone").addEventListener("click", () => api("/api/jobs/clear", {}).then(() => refresh(true)));

  // ------------------------------------------------------------------ odświeżanie
  let timer = null, lastDisks = "";
  async function refresh(now) {
    clearTimeout(timer);
    let busy = false;
    try {
      const s = await api("/api/state");
      st.online = true;
      st.jobs = s.jobs;
      const dk = JSON.stringify(s.disks);
      if (dk !== lastDisks) { lastDisks = dk; st.disks = s.disks; renderDisks(); updatePreview(); }
      renderJobs();
      const w = $("#engineWarn");
      w.hidden = s.engine.ok;
      w.textContent = s.engine.ok ? "" : "Silnik pobierania aria2c nie działa: " + s.engine.error;
      busy = s.jobs.some((j) => ["downloading", "queued", "finalizing", "cancelling"].includes(j.status));
    } catch (e) {
      if (e.message === "auth") return;
      st.online = false;
    }
    $("#connDot").classList.toggle("bad", !st.online);
    $("#connText").firstChild.textContent = st.online ? "Połączono z " : "Brak połączenia z ";
    timer = setTimeout(refresh, busy ? 1000 : 4000);
  }
  $("#hostName").textContent = location.hostname;
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(true); });

  // ------------------------------------------------------------------ wylogowanie
  $("#logoutBtn").addEventListener("click", async () => {
    await fetch("/logout", { method: "POST", credentials: "same-origin" });
    location.href = "/login";
  });

  // ------------------------------------------------------------------ ustawienia
  const dlg = $("#settings");
  function addDiskRow(d) {
    const row = $("#diskRowTpl").content.firstElementChild.cloneNode(true);
    $$("[data-k]", row).forEach((inp) => { inp.value = (d && d[inp.dataset.k]) || ""; });
    const title = $(".row-title", row);
    const sync = () => { title.textContent = $("[data-k=label]", row).value || "Nowy dysk"; };
    $("[data-k=label]", row).addEventListener("input", sync);
    sync();
    $(".rm", row).addEventListener("click", () => row.remove());
    $("#diskRows").appendChild(row);
  }
  $("#addDisk").addEventListener("click", () => addDiskRow({ mount: "/", movies: "/", tv: "/" }));

  $("#openSettings").addEventListener("click", async () => {
    $("#setMsg").textContent = ""; $("#pwdMsg").textContent = ""; $("#updMsg").textContent = "";
    try {
      const s = await api("/api/settings");
      $("#diskRows").replaceChildren();
      s.disks.forEach(addDiskRow);
      $("#sConn").value = s.connections_per_file;
      $("#sConc").value = s.max_concurrent;
      $("#sSpeed").value = s.max_speed_mbps;
      $("#sMount").checked = !!s.require_mount;
      $("#aUser").value = s.username; $("#aCur").value = ""; $("#aNew").value = "";
      dlg.showModal();
    } catch (e) { alert(e.message); }
  });

  $("#saveSettings").addEventListener("click", async () => {
    const disks = $$("#diskRows .disk-row").map((row) => {
      const d = {};
      $$("[data-k]", row).forEach((inp) => { d[inp.dataset.k] = inp.value.trim(); });
      return d;
    });
    const m = $("#setMsg");
    try {
      await api("/api/settings", {
        disks, connections_per_file: $("#sConn").value, max_concurrent: $("#sConc").value,
        max_speed_mbps: $("#sSpeed").value, require_mount: $("#sMount").checked,
      });
      dlg.close();
      lastDisks = "";
      refresh(true);
    } catch (e) { m.className = "form-msg bad"; m.textContent = e.message; }
  });

  $("#savePwd").addEventListener("click", async () => {
    const m = $("#pwdMsg");
    try {
      await api("/api/password", { username: $("#aUser").value, current: $("#aCur").value, new: $("#aNew").value });
      m.className = "form-msg ok"; m.textContent = "Zapisano.";
      $("#aCur").value = ""; $("#aNew").value = "";
    } catch (e) { m.className = "form-msg bad"; m.textContent = e.message; }
  });

  $("#checkUpd").addEventListener("click", async () => {
    const m = $("#updMsg");
    m.textContent = "Sprawdzam…";
    try {
      const r = await api("/api/version");
      m.textContent = r.message + (r.commit ? ` (commit ${r.commit})` : "");
      m.style.color = r.available ? "var(--accent)" : "";
    } catch (e) { m.textContent = e.message; }
  });

  // start
  setExt("");
  setKind("movie", false);
  refresh(true);
})();
