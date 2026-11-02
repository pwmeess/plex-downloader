/* Plex Downloader – strona główna: formularz pobierania, kolejka, podgląd filmu */
(() => {
  "use strict";
  const { $, $$, store, api, fmtSize, fmtSpeed, fmtEta, el, icon, catIcon, toast } = window.PD;

  const VIDEO_EXTS = [".mkv", ".mp4", ".avi", ".m4v", ".mov", ".wmv", ".ts", ".m2ts", ".mpg",
    ".mpeg", ".webm", ".flv", ".divx", ".ogm", ".vob"];
  const STATUS = {
    queued: "Oczekuje", downloading: "Pobieranie", paused: "Wstrzymano", finalizing: "Finalizowanie",
    cancelling: "Anulowanie…", done: "Zakończono", error: "Błąd",
  };

  const st = {
    cat: store.get("plexdl.cat") || "movies",
    categories: [],
    diskId: store.get("plexdl.disk"),
    disks: [],
    jobs: [],
    probe: null,
    dirty: {},          // pola edytowane ręcznie – nie nadpisujemy ich podpowiedzią
    catTouched: false,
    infoItem: null,
    detectedEdition: "",
  };
  const category = () => st.categories.find((c) => c.id === st.cat) || st.categories[0] || { id: "movies", kind: "movie", label: "Filmy" };
  const isTv = () => category().kind === "tv";

  function sanitize(s) {
    return (s || "").replace(/[<>:"/\\|?*\x00-\x1f]/g, " ").replace(/\s+/g, " ").replace(/^[\s.]+|[\s.]+$/g, "");
  }
  const cleanTag = (s, n) => sanitize((s || "").replace(/[{}]/g, " ")).slice(0, n || 32).trim();
  const stripTags = (s) => (s || "").replace(/\s*\{(edition|imdb|tmdb|tvdb)-[^}]*\}/gi, "").trim();
  function normExt(e) {
    e = (e || "").trim().toLowerCase();
    if (e && !e.startsWith(".")) e = "." + e;
    return e;
  }

  // ------------------------------------------------------------------ formularz
  const urlIn = $("#url"), nameIn = $("#name"), showIn = $("#show"), seasonIn = $("#season"),
    epIn = $("#episode"), epTitleIn = $("#epTitle"), extMovie = $("#extMovie"), extTv = $("#extTv");
  const advOn = $("#advOn"), advEdition = $("#advEdition"), advVersion = $("#advVersion"), advId = $("#advId");

  function ext() { return normExt(isTv() ? extTv.value : extMovie.value); }
  function setExt(v) { extMovie.value = v; extTv.value = v; }
  [extMovie, extTv].forEach((inp) => inp.addEventListener("input", () => {
    st.dirty.ext = true;
    (inp === extMovie ? extTv : extMovie).value = inp.value;
    updatePreview();
  }));

  function renderCats() {
    const box = $("#catTabs");
    box.replaceChildren();
    if (!st.categories.some((c) => c.id === st.cat) && st.categories.length) st.cat = st.categories[0].id;
    st.categories.forEach((c) => {
      const b = el("button", c.id === st.cat ? "on" : "");
      b.type = "button"; b.dataset.cat = c.id;
      b.append(icon(catIcon(c)), document.createTextNode(c.label));
      b.title = c.kind === "tv" ? "Serial – nazewnictwo Serial/Season 01/…" : "Film – nazewnictwo Tytuł (Rok)/…";
      b.addEventListener("click", () => setCat(c.id, true));
      box.appendChild(b);
    });
  }
  function setCat(id, byUser) {
    const prevTv = isTv();
    st.cat = id;
    if (byUser) { st.catTouched = true; store.set("plexdl.cat", id); }
    $$("#catTabs button").forEach((b) => b.classList.toggle("on", b.dataset.cat === id));
    $("#movieFields").hidden = isTv();
    $("#tvFields").hidden = !isTv();
    $("#advEditionBox").hidden = isTv();
    $("#advVersionBox").hidden = isTv();
    if (prevTv !== isTv()) st.infoItem = null;
    renderDisks();
    updatePreview();
  }

  [[nameIn, "name"], [showIn, "show"], [seasonIn, "season"], [epIn, "episode"], [epTitleIn, "epTitle"]]
    .forEach(([inp, key]) => inp.addEventListener("input", () => { st.dirty[key] = true; updatePreview(); }));
  [advEdition, advVersion, advId].forEach((i) => i.addEventListener("input", updatePreview));
  advOn.addEventListener("change", () => { $("#advBody").hidden = !advOn.checked; updatePreview(); });

  function selectedDisk() { return st.disks.find((d) => d.id === st.diskId); }
  const diskPath = (d) => (d && d.paths ? d.paths[st.cat] : "") || "";

  function tags() {
    if (!advOn.checked) return { folder: "", version: "" };
    const parts = [];
    if (advId.checked && st.infoItem) parts.push(`{tmdb-${st.infoItem.id}}`);
    const ed = isTv() ? "" : cleanTag(advEdition.value);
    if (ed) parts.push(`{edition-${ed}}`);
    return { folder: parts.length ? " " + parts.join(" ") : "", version: isTv() ? "" : cleanTag(advVersion.value, 40) };
  }

  function targetPath() {
    const d = selectedDisk();
    const base = diskPath(d) || `…/${category().folder || category().label}`;
    const e = ext(), t = tags();
    if (isTv()) {
      const show = sanitize(stripTags(showIn.value));
      if (!show) return null;
      const s = parseInt(seasonIn.value, 10), ep = parseInt(epIn.value, 10);
      if (isNaN(s) || isNaN(ep)) return null;
      const p2 = (n) => String(n).padStart(2, "0");
      let file = `${show} - S${p2(s)}E${p2(ep)}`;
      const tt = sanitize(epTitleIn.value);
      if (tt) file += " - " + tt;
      return { base, dir: `${show}${t.folder}/Season ${p2(s)}`, file: file + e };
    }
    const name = sanitize(stripTags(nameIn.value));
    if (!name) return null;
    const folder = name + t.folder;
    return { base, dir: folder, file: folder + (t.version ? " - " + t.version : "") + e };
  }

  function updatePreview() {
    scheduleInfo();
    $("#advIdVal").textContent = st.infoItem ? `{tmdb-${st.infoItem.id}} – ${st.infoItem.title}` : "(najpierw znajdź film w podglądzie)";
    advId.disabled = !st.infoItem;
    const p = targetPath(), box = $("#preview");
    const hint = $("#nameHint");
    hint.replaceChildren();
    if (!isTv() && nameIn.value.trim() && !/\(\d{4}\)/.test(nameIn.value)) {
      hint.appendChild(el("span", "warn", "Dodaj rok w nawiasie – Plex lepiej dopasuje film, np. „Tytuł (2015)”."));
    }
    if (!isTv() && st.detectedEdition && cleanTag(advEdition.value) !== st.detectedEdition) {
      const s = el("span", "ed-hint");
      s.append(`W nazwie pliku wykryto edycję: ${st.detectedEdition}. `);
      const b = el("button", "linklike", "Użyj"); b.type = "button";
      b.addEventListener("click", () => { advOn.checked = true; $("#advBody").hidden = false; advEdition.value = st.detectedEdition; updatePreview(); });
      s.appendChild(b);
      hint.appendChild(s);
    }
    if (!p) { box.hidden = true; return; }
    box.hidden = false;
    box.replaceChildren(document.createTextNode(p.base + "/"), el("b", null, p.dir + "/" + p.file));
  }

  // ---- podgląd filmu z TMDB (tylko poglądowo, nic nie zapisujemy)
  const info = { timer: null, key: "", seq: 0, pickId: null, results: [] };

  function infoQuery() {
    if (isTv()) {
      const t = stripTags(showIn.value);
      return t ? { kind: "tv", title: t, season: seasonIn.value, episode: epIn.value } : null;
    }
    const t = stripTags(nameIn.value);
    return t ? { kind: "movie", title: t } : null;
  }

  function scheduleInfo(force) {
    const q = infoQuery();
    const card = $("#infoCard");
    if (!q) { clearTimeout(info.timer); card.hidden = true; info.key = ""; info.pickId = null; info.seq++; st.infoItem = null; return; }
    const key = JSON.stringify(q);
    if (!force && key === info.key) return; // bez zmian – nie kasujemy zaplanowanego zapytania
    clearTimeout(info.timer);
    const titleOnly = JSON.stringify([q.kind, q.title]);
    if (info.titleKey !== titleOnly) { info.pickId = null; }
    info.titleKey = titleOnly;
    info.key = key;
    info.timer = setTimeout(() => loadInfo(q), force ? 0 : 650);
  }

  function setInfoState(text, cls) {
    const s = $("#infoState");
    s.className = "info-state" + (cls ? " " + cls : "");
    s.replaceChildren();
    if (text instanceof Node) s.appendChild(text); else s.textContent = text || "";
    s.hidden = !text;
  }

  async function loadInfo(q) {
    const seq = ++info.seq;
    const card = $("#infoCard");
    card.hidden = false;
    $("#infoHeading").textContent = q.kind === "tv" ? "Podgląd serialu" : "Podgląd filmu";
    if (!$("#infoBody").hidden) $("#infoBody").style.opacity = ".45";
    setInfoState("Szukam w TMDB…", "loading");
    const params = new URLSearchParams({ kind: q.kind, title: q.title });
    if (q.kind === "tv") { params.set("season", q.season || ""); params.set("episode", q.episode || ""); }
    if (info.pickId) params.set("id", info.pickId);
    let data;
    try {
      data = await api("/api/info?" + params.toString());
    } catch (e) {
      if (seq === info.seq) { showInfoMsg(e.message, true); }
      return;
    }
    if (seq !== info.seq) return;
    $("#infoBody").style.opacity = "";
    if (!data.configured) {
      const f = document.createDocumentFragment();
      f.append("Dodaj darmowy klucz TMDB w ");
      const a = el("a", null, "Ustawieniach");
      a.href = "#"; a.addEventListener("click", (ev) => { ev.preventDefault(); window.PD.openSettings("preview"); });
      f.append(a, ", aby zobaczyć tu opis, plakat i linki do IMDb, Filmwebu i YouTube.");
      showInfoMsg(f);
      return;
    }
    if (data.error) { showInfoMsg(data.error, true); return; }
    info.results = data.results || [];
    if (!data.item) {
      const y = data.query && data.query.year ? ` (${data.query.year})` : "";
      showInfoMsg(`Nie znaleziono „${data.query ? data.query.title : q.title}${y}” w TMDB. Sprawdź pisownię tytułu.`);
      return;
    }
    renderInfo(data.item);
  }

  function showInfoMsg(msg, bad) {
    st.infoItem = null;
    $("#infoBody").hidden = true;
    $("#infoAlts").hidden = true;
    if (bad) { const sp = el("span", "bad", msg); setInfoState(sp); } else setInfoState(msg);
    updatePreviewSoft();
  }
  function updatePreviewSoft() {
    // odświeża podgląd ścieżki bez ponownego zapytania do TMDB
    const k = info.key; updatePreview(); info.key = k;
  }

  function fmtRuntime(min) {
    if (!min) return "";
    const h = Math.floor(min / 60), m = min % 60;
    return h ? `${h} godz. ${m} min` : `${m} min`;
  }

  function renderInfo(it) {
    st.infoItem = it;
    setInfoState("");
    $("#infoBody").hidden = false;
    const poster = $("#infoPoster");
    poster.replaceChildren();
    if (it.poster) {
      const img = document.createElement("img");
      img.src = it.poster; img.alt = "Plakat: " + it.title; img.loading = "lazy";
      img.referrerPolicy = "no-referrer";
      poster.appendChild(img);
    } else poster.appendChild(icon(it.kind === "tv" ? "tv" : "film"));

    $("#infoTitle").textContent = it.title + (it.year ? ` (${it.year})` : "");
    const orig = $("#infoOrig");
    orig.textContent = it.original_title && it.original_title !== it.title ? it.original_title : "";
    orig.hidden = !orig.textContent;

    const meta = $("#infoMeta");
    meta.replaceChildren();
    if (it.rating) {
      const r = el("span", "rating");
      r.append(el("i", null, "★"), String(it.rating).replace(".", ","), el("span", "votes", ` / 10 · ${it.votes.toLocaleString("pl-PL")} głosów`));
      meta.appendChild(r);
    }
    if (it.runtime) meta.appendChild(el("span", null, fmtRuntime(it.runtime) + (it.kind === "tv" ? " / odc." : "")));
    if (it.kind === "tv" && it.seasons) meta.appendChild(el("span", null, `Sezony: ${it.seasons}`));
    if (it.genres && it.genres.length) meta.appendChild(el("span", null, it.genres.slice(0, 3).join(", ")));

    const ep = $("#infoEp");
    if (it.episode && it.episode.name) {
      ep.replaceChildren(el("b", null, `S${String(it.episode.season).padStart(2, "0")}E${String(it.episode.episode).padStart(2, "0")}`), it.episode.name);
      ep.hidden = false;
    } else ep.hidden = true;

    const ov = $("#infoOverview");
    ov.textContent = it.overview || "Brak opisu.";
    ov.classList.remove("open");
    ov.onclick = () => ov.classList.toggle("open");

    const ppl = $("#infoPeople");
    ppl.replaceChildren();
    if (it.people && it.people.length) { const d = el("div"); d.append(el("b", null, it.people_label + ": "), it.people.join(", ")); ppl.appendChild(d); }
    if (it.cast && it.cast.length) { const d = el("div"); d.append(el("b", null, "Obsada: "), it.cast.join(", ")); ppl.appendChild(d); }

    const links = $("#infoLinks");
    links.replaceChildren();
    const link = (href, text, cls, ico) => {
      if (!href) return;
      const a = el("a", cls); a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer";
      if (ico) a.appendChild(icon(ico));
      a.appendChild(document.createTextNode(text));
      links.appendChild(a);
    };
    const q = `${it.title}${it.year ? " " + it.year : ""}`;
    const qOrig = `${it.original_title || it.title}${it.year ? " " + it.year : ""}`;
    link(it.imdb_url, "IMDb", "imdb");
    link(it.filmweb_url, "Filmweb", "filmweb");
    link(it.tmdb_url, "TMDB", "tmdb");
    link("https://www.google.com/search?q=" + encodeURIComponent(q + (it.kind === "tv" ? " serial" : " film")), "Google", "google", "search");
    link("https://www.youtube.com/results?search_query=" + encodeURIComponent(qOrig + " trailer"), "Zwiastun", "youtube", "youtube");

    const alts = $("#infoAlts");
    const others = info.results.filter((r) => r.id !== it.id);
    alts.replaceChildren();
    if (others.length) {
      alts.appendChild(el("span", null, it.kind === "tv" ? "Nie ten serial?" : "Nie ten film?"));
      others.slice(0, 5).forEach((r) => {
        const b = el("button", null, r.title + (r.year ? ` (${r.year})` : ""));
        b.type = "button";
        if (r.original_title && r.original_title !== r.title) b.title = r.original_title;
        b.addEventListener("click", () => { info.pickId = r.id; loadInfo(infoQuery()); });
        alts.appendChild(b);
      });
      alts.hidden = false;
    } else alts.hidden = true;
    updatePreviewSoft();
  }

  // ---- sprawdzanie linku
  let probeTimer = null, probeSeq = 0;
  urlIn.addEventListener("input", () => {
    clearTimeout(probeTimer);
    st.probe = null;
    st.dirty = {};
    st.catTouched = false;
    st.detectedEdition = "";
    $("#formMsg").textContent = "";
    const v = urlIn.value.trim();
    if (!/^https?:\/\/\S+/i.test(v)) { $("#probeInfo").replaceChildren(); return; }
    $("#probeInfo").replaceChildren(el("span", null, "Sprawdzam link…"));
    probeTimer = setTimeout(() => runProbe(v), 450);
  });

  async function runProbe(url) {
    const seq = ++probeSeq;
    try {
      const r = await api("/api/probe", { url });
      if (seq !== probeSeq) return;
      st.probe = r;
      fillLists(r);
      applyGuess(r);
      const parts = [];
      if (r.reachable) {
        parts.push(el("span", "ok", "✓ Link działa"));
        if (r.size) parts.push(el("span", null, "Rozmiar: " + fmtSize(r.size)));
        parts.push(r.resumable
          ? el("span", null, "Wznawianie i pobieranie wielowątkowe: tak")
          : el("span", "warn", "Serwer nie obsługuje wznawiania – 1 połączenie"));
      } else {
        parts.push(el("span", "warn", "Nie udało się sprawdzić linku (" + (r.probe_error || "brak odpowiedzi") + "). Możesz spróbować pobrać mimo to."));
      }
      if (r.filename) parts.push(el("span", null, r.filename));
      $("#probeInfo").replaceChildren(...parts);
    } catch (e) {
      if (seq === probeSeq) $("#probeInfo").replaceChildren(el("span", "bad", e.message));
    }
  }

  function fillLists(r) {
    const fill = (id, items) => {
      const dl = $(id);
      if (dl.childElementCount || !items) return;
      items.forEach((v) => { const o = el("option"); o.value = v; dl.appendChild(o); });
    };
    fill("#editionList", r.editions);
    fill("#versionList", r.versions);
  }

  function applyGuess(r) {
    const g = r.guess || {};
    if (!st.dirty.ext && r.ext) setExt(r.ext);
    if (!st.catTouched && g.kind) {
      // serial → pierwsza kategoria serialowa; film → zostajemy w bieżącej kategorii filmowej (np. Dla dzieci)
      if (g.kind === "tv" && !isTv()) { const c = st.categories.find((x) => x.kind === "tv"); if (c) setCat(c.id, false); }
      if (g.kind === "movie" && isTv()) {
        const c = st.categories.find((x) => x.id === "movies") || st.categories.find((x) => x.kind === "movie");
        if (c) setCat(c.id, false);
      }
    }
    st.detectedEdition = g.edition || "";
    if (g.kind === "tv") {
      if (!st.dirty.show) showIn.value = g.show || "";
      if (!st.dirty.season && g.season != null) seasonIn.value = g.season;
      if (!st.dirty.episode && g.episode != null) epIn.value = g.episode;
    } else if (!st.dirty.name) {
      nameIn.value = g.name || "";
    }
    updatePreview();
  }

  function resetForm() {
    $("#addForm").reset();
    seasonIn.value = 1; epIn.value = 1;
    st.probe = null; st.dirty = {}; st.catTouched = false; st.detectedEdition = ""; st.infoItem = null;
    $("#advBody").hidden = true;
    $("#probeInfo").replaceChildren();
    $("#formMsg").textContent = "";
    setCat(st.cat, false);
  }
  $("#clearBtn").addEventListener("click", () => { resetForm(); urlIn.focus(); });

  // ---- dyski
  function renderDisks() {
    const box = $("#disks");
    box.replaceChildren();
    const usable = (d) => d.ok && diskPath(d) && d.folders && d.folders[st.cat];
    if (!st.disks.some((d) => d.id === st.diskId && usable(d))) {
      const first = st.disks.find(usable);
      if (first) st.diskId = first.id;
    }
    st.disks.forEach((d) => {
      const can = usable(d);
      const b = el("button", "disk" + (d.id === st.diskId && can ? " on" : ""));
      b.type = "button";
      b.disabled = !can;
      b.title = diskPath(d) || "Brak folderu dla tej kategorii";
      const ico = el("div", "ico"); ico.appendChild(icon("drive"));
      b.append(ico, el("div", "name", d.label), el("div", "sub", d.subtitle || d.mount));
      if (d.ok && d.total) {
        const used = (d.total - d.free) / d.total;
        const bar = el("div", "bar" + (d.free / d.total < 0.05 ? " low" : ""));
        const fill = el("i"); fill.style.width = Math.max(2, used * 100).toFixed(1) + "%";
        bar.appendChild(fill);
        b.append(bar, el("div", "free", `Wolne: ${fmtSize(d.free).replace(" GB", "")} / ${fmtSize(d.total)}`));
      }
      if (!d.ok) b.append(el("div", "problem", d.problem || "Niedostępny"));
      else if (!diskPath(d)) b.append(el("div", "problem muted", `Brak folderu „${category().label}”`));
      else if (!d.folders[st.cat]) b.append(el("div", "problem", "Folder nie istnieje"));
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
    const d = selectedDisk();
    if (!d || !d.ok || !diskPath(d)) { msg.className = "form-msg bad"; msg.textContent = "Wybierz dostępny dysk docelowy."; return; }
    const body = {
      url: urlIn.value.trim(), category: st.cat, disk_id: st.diskId, ext: e,
      name: nameIn.value, show: showIn.value, season: seasonIn.value, episode: epIn.value,
      episode_title: epTitleIn.value, size: st.probe && st.probe.size,
      advanced: advOn.checked ? {
        edition: isTv() ? "" : advEdition.value, version: isTv() ? "" : advVersion.value,
        use_id: advId.checked && !!st.infoItem, tmdb_id: st.infoItem ? st.infoItem.id : null,
      } : null,
    };
    const btn = $("#submitBtn");
    btn.disabled = true;
    try {
      const r = await api("/api/jobs", body);
      const wasTv = isTv();
      resetForm();
      msg.className = "form-msg ok";
      msg.textContent = "Dodano do kolejki: " + r.job.filename;
      if (wasTv) { // przy serialach zostawiamy nazwę i sezon – wygodne przy kolejnych odcinkach
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
    return api(`/api/jobs/${id}/${action}`, {}).then(() => refresh(true)).catch((e) => toast(e.message, true));
  }
  function actBtn(label, cls, ico, fn) {
    const b = el("button", cls);
    b.type = "button";
    if (ico) b.appendChild(icon(ico));
    if (label) b.appendChild(document.createTextNode(label));
    b.addEventListener("click", fn);
    return b;
  }
  const where = (j) => j.disk_label + (j.category_label ? " / " + j.category_label : "");

  function buildJob(j) {
    const compact = j.status === "done" || j.status === "error";
    const n = el("div", "job " + j.status + (compact ? " compact" : ""));
    n.dataset.sig = j.status;
    if (compact) {
      const badge = el("span", "badge " + j.status, STATUS[j.status]);
      const title = el("span", "job-title", j.filename);
      const rest = el("span", "rest");
      rest.textContent = j.status === "done" ? `${fmtSize(j.total)} · Zapisano na: ${where(j)}` : j.error;
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
      const c = actBtn("Anuluj ", "btn-soft small btn-danger", null, async () => {
        const ok = await window.PD.modal({ title: "Anulować pobieranie?", danger: true,
          body: `„${j.filename}” – pobrane dane zostaną usunięte.`,
          buttons: [{ label: "Nie", value: false }, { label: "Anuluj pobieranie", value: true, cls: "btn-accent danger" }] });
        if (ok) jobAction(j.id, "cancel");
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
      j.status === "downloading" ? `Połączenia: ${j.connections}/${j.max_connections || "?"}` : where(j)));
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
  let timer = null, lastDisks = "", lastCats = "";
  async function refresh() {
    clearTimeout(timer);
    let busy = false;
    try {
      const s = await api("/api/state");
      st.jobs = s.jobs;
      const ck = JSON.stringify(s.categories);
      if (ck !== lastCats) { lastCats = ck; st.categories = s.categories; renderCats(); setCat(st.cat, false); }
      const dk = JSON.stringify(s.disks);
      if (dk !== lastDisks) { lastDisks = dk; st.disks = s.disks; renderDisks(); updatePreviewSoft(); }
      renderJobs();
      const w = $("#engineWarn");
      w.hidden = s.engine.ok;
      w.textContent = s.engine.ok ? "" : "Silnik pobierania aria2c nie działa: " + s.engine.error;
      busy = s.jobs.some((j) => ["downloading", "queued", "finalizing", "cancelling"].includes(j.status));
    } catch (e) {
      if (e.message === "auth") return;
    }
    timer = setTimeout(refresh, busy ? 1000 : 4000);
  }
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
  document.addEventListener("pd:settings-saved", () => { lastDisks = ""; lastCats = ""; scheduleInfo(true); refresh(); });

  // start
  setExt("");
  refresh();
})();
