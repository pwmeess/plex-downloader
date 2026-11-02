/* Plex Downloader – pływające okno ustawień z zakładkami */
(() => {
  "use strict";
  const { $, $$, t, LOCALE, api, el, icon, modal, toast, makeDraggable, centerWindow, fmtSize, copyText } = window.PD;
  const dlg = $("#settings");
  if (!dlg) return;
  makeDraggable(dlg);

  let cfg = null;      // ustawienia w trakcie edycji
  let tmpSeq = 0;
  const key = (c) => c.id || c.tmp;
  const KIND = { movie: t("movie"), tv: t("TV show"), other: t("other") };

  // ------------------------------------------------------------------ zakładki
  function showTab(name) {
    syncFromDom();
    $$(".tabs button", dlg).forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
    $$(".tab-panel", dlg).forEach((p) => { p.hidden = p.dataset.panel !== name; });
    if (name === "disks") renderDisks();
    if (name === "backups") loadBackups();
    if (name === "plex") loadPlexStatus();
    if (name === "preview") renderThumbDisks();
    if (name === "account") renderAccount();
    $(".win-body", dlg).scrollTop = 0;
  }
  $$(".tabs button", dlg).forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
  $$("[data-close]", dlg).forEach((b) => b.addEventListener("click", () => dlg.close()));
  $$("[data-goto]", dlg).forEach((b) => b.addEventListener("click", () => showTab(b.dataset.goto)));

  // ------------------------------------------------------------------ dyski
  function renderDisks() {
    const box = $("#diskRows");
    box.replaceChildren();
    cfg.disks.forEach((d, i) => box.appendChild(diskRow(d, i)));
  }
  function diskRow(d, idx) {
    const row = $("#diskRowTpl").content.firstElementChild.cloneNode(true);
    row.dataset.idx = idx;
    $$("[data-k]", row).forEach((inp) => { inp.value = d[inp.dataset.k] || ""; });
    const title = $(".row-title", row);
    const sync = () => { title.textContent = $("[data-k=label]", row).value || t("New disk"); };
    $("[data-k=label]", row).addEventListener("input", sync); sync();
    const paths = $(".cat-paths", row);
    cfg.categories.forEach((c) => {
      const w = el("div", "cat-path");
      const lab = el("label");
      lab.append(icon(window.PD.catIcon(c)), document.createTextNode(" " + t("Folder: {name}", { name: c.label || t("(no name)") })),
        el("span", "kind-badge", KIND[c.kind] || c.kind));
      const inp = el("input", "input mono"); inp.dataset.cat = key(c);
      inp.value = (d.paths || {})[key(c)] || "";
      inp.placeholder = t("(none – category not available on this disk)");
      inp.addEventListener("input", () => { w.classList.remove("bad", "found"); msg.textContent = ""; });
      const msg = el("div", "path-msg");
      w.append(lab, inp, msg);
      paths.appendChild(w);
    });
    $(".rm", row).addEventListener("click", () => { syncFromDom(); cfg.disks.splice(idx, 1); renderDisks(); });
    $(".goto-cats", row).addEventListener("click", () => showTab("cats"));
    $(".fill-paths", row).addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      const mount = $("[data-k=mount]", row).value.trim();
      const current = {};
      $$("input[data-cat]", row).forEach((i) => { current[i.dataset.cat] = i.value.trim(); });
      btn.disabled = true;
      try {
        const r = await api("/api/disks/scan", {
          mount, paths: current,
          categories: cfg.categories.map((c) => ({ id: key(c), label: c.label, folder: c.folder })),
        });
        let found = 0, missing = 0;
        $$(".cat-path", row).forEach((w) => {
          const i = $("input", w), res = r.result[i.dataset.cat], m = $(".path-msg", w);
          w.classList.remove("bad", "found");
          if (!res) return;
          if (res.status === "found") { i.value = res.path; w.classList.add("found"); m.textContent = t("Found – check and save"); found++; }
          else if (res.status === "missing") { w.classList.add("bad"); m.textContent = t("Folder not found on this disk – enter the path manually or leave empty"); missing++; }
          else m.textContent = "";
        });
        if (!found && !missing) toast(t("All paths are correct."));
        else toast(t("Paths updated: {found} found, {missing} not found.", { found, missing }), missing > 0 && !found);
      } catch (err) { toast(err.message, true); }
      btn.disabled = false;
    });
    return row;
  }
  $("#addDisk").addEventListener("click", () => {
    syncFromDom();
    cfg.disks.push({ id: "", label: "", subtitle: "", mount: "", paths: {} });
    renderDisks();
    const rows = $$("#diskRows .disk-row");
    rows[rows.length - 1].scrollIntoView({ behavior: "smooth", block: "center" });
  });

  // ------------------------------------------------------------------ kategorie
  function renderCats() {
    const box = $("#catRows");
    box.replaceChildren();
    cfg.categories.forEach((c, i) => {
      const row = el("div", "cat-row"); row.dataset.idx = i;
      const ic = el("span", "cat-ico"); ic.appendChild(icon(window.PD.catIcon(c)));
      const name = el("input", "input"); name.value = c.label; name.placeholder = t("e.g. Kids"); name.dataset.f = "label";
      const kind = el("select", "input"); kind.dataset.f = "kind";
      [["movie", t("Movie")], ["tv", t("TV show")], ["other", t("Other (keep name)")]].forEach(([v, x]) => { const o = el("option", null, x); o.value = v; kind.appendChild(o); });
      kind.value = c.kind;
      const folder = el("input", "input mono"); folder.value = c.folder || ""; folder.placeholder = t("e.g. Kids"); folder.dataset.f = "folder";
      const tm = el("label", "switch"); const tmIn = el("input"); tmIn.type = "checkbox"; tmIn.dataset.f = "tmdb";
      tmIn.checked = c.tmdb !== false && c.kind !== "other"; tmIn.disabled = c.kind === "other";
      tm.append(tmIn, el("span")); tm.title = t("Search TMDB for posters");
      const rm = el("button", "icon-btn"); rm.type = "button"; rm.title = t("Remove category"); rm.appendChild(icon("trash"));
      rm.disabled = cfg.categories.length <= 1;
      rm.addEventListener("click", async () => {
        const ok = await modal({ title: t("Remove category?"), danger: true,
          body: t("The category “{name}” will disappear from the form and the File manager. Files on the disks stay untouched.", { name: c.label }),
          buttons: [{ label: t("Cancel"), value: false }, { label: t("Remove category"), value: true, cls: "btn-accent danger" }] });
        if (!ok) return;
        syncFromDom(); cfg.categories.splice(i, 1); renderCats();
      });
      kind.addEventListener("change", () => {
        c.kind = kind.value; ic.replaceChildren(icon(window.PD.catIcon(c)));
        tmIn.disabled = c.kind === "other"; if (c.kind === "other") tmIn.checked = false;
      });
      const cell = el("div", "cat-name"); cell.append(ic, name);
      row.append(cell, kind, folder, tm, rm);
      box.appendChild(row);
    });
  }
  $("#addCat").addEventListener("click", () => {
    syncFromDom();
    cfg.categories.push({ id: "", tmp: "new-" + (++tmpSeq), label: "", kind: "movie", folder: "", tmdb: false });
    renderCats();
    const rows = $$("#catRows .cat-row");
    $("input", rows[rows.length - 1]).focus();
  });

  // ------------------------------------------------------------------ serwery Plex
  function renderPlexRows() {
    const box = $("#plexRows");
    box.replaceChildren();
    if (!cfg.plex_servers.length) box.appendChild(el("p", "hint", t("None – automatic discovery is enough. Add a server manually if it is on another subnet or behind a VPN.")));
    cfg.plex_servers.forEach((s, i) => {
      const row = el("div", "plex-row");
      const mk = (f, ph, v) => { const x = el("input", "input" + (f === "name" ? "" : " mono")); x.dataset.f = f; x.placeholder = ph; x.value = v || ""; return x; };
      const rm = el("button", "icon-btn"); rm.type = "button"; rm.appendChild(icon("trash")); rm.title = t("Remove");
      rm.addEventListener("click", () => { syncFromDom(); cfg.plex_servers.splice(i, 1); renderPlexRows(); });
      row.append(mk("name", t("Name, e.g. Living room"), s.name), mk("host", t("IP address, e.g. 192.168.1.20"), s.host), mk("port", "32400", s.port), rm);
      row.dataset.id = s.id || "";
      box.appendChild(row);
    });
  }
  $("#addPlex").addEventListener("click", () => { syncFromDom(); cfg.plex_servers.push({ name: "", host: "", port: 32400 }); renderPlexRows(); });
  function renderPlexList(list) {
    const box = $("#plexList");
    box.replaceChildren();
    if (!list.length) { box.appendChild(el("p", "hint", t("No Plex server found. Check that Plex Media Server is running, or add it manually below."))); return; }
    list.forEach((p) => {
      const r = el("div", "plex-item");
      r.append(el("span", "dot" + (p.online ? "" : " bad")), el("b", null, p.name),
        el("span", "mono", `${p.display_host}:${p.port}`),
        el("span", "muted", (p.online ? "online" : "offline") + (p.version ? ` · ${p.version}` : "")),
        el("span", "tag", p.source === "manual" ? t("manual") : p.source === "local" ? t("this Raspberry Pi") : t("discovered")));
      const a = el("a", null, t("Open") + " ↗"); a.href = `http://${p.display_host}:${p.port}/web`; a.target = "_blank"; a.rel = "noopener";
      r.appendChild(a);
      box.appendChild(r);
    });
  }
  async function loadPlexStatus() {
    try { renderPlexList((await api("/api/status")).plex); } catch (e) { /* bez znaczenia */ }
  }
  $("#plexDiscover").addEventListener("click", async (e) => {
    const b = e.currentTarget; b.disabled = true;
    $("#plexList").replaceChildren(el("p", "hint", t("Searching for servers on the network…")));
    try {
      const r = await api("/api/plex/discover", {});
      renderPlexList(r.status);
      toast(r.found.length ? t("Servers found: {n}", { n: r.found.length }) : t("No servers found via GDM."));
      window.PD.refreshStatus();
    } catch (err) { toast(err.message, true); }
    b.disabled = false;
  });

  // ------------------------------------------------------------------ okładki
  function renderThumbDisks() {
    const sel = $("#thumbDisk");
    const cur = sel.value;
    sel.replaceChildren();
    cfg.disks.filter((d) => d.id).forEach((d) => { const o = el("option", null, d.label); o.value = d.id; sel.appendChild(o); });
    if (cur) sel.value = cur;
  }
  $("#thumbRefresh").addEventListener("click", async () => {
    const disk = $("#thumbDisk").value;
    if (!disk) return;
    try {
      await api("/api/fm/thumbs/refresh", { disk });
      $("#thumbMsg").className = "form-msg ok";
      $("#thumbMsg").textContent = t("Poster download started – progress is shown in the File manager.");
    } catch (e) { $("#thumbMsg").className = "form-msg bad"; $("#thumbMsg").textContent = e.message; }
  });
  $("#thumbDelete").addEventListener("click", async () => {
    const disk = $("#thumbDisk").value;
    const label = $("#thumbDisk").selectedOptions[0] ? $("#thumbDisk").selectedOptions[0].textContent : disk;
    const ok = await modal({ title: t("Delete posters?"), danger: true,
      body: t("All *.thumb.jpg files will be deleted from the disk “{label}”. Movies stay untouched.", { label }),
      buttons: [{ label: t("Cancel"), value: false }, { label: t("Delete posters"), value: true, cls: "btn-accent danger" }] });
    if (!ok) return;
    try {
      const r = await api("/api/fm/thumbs/delete", { disk });
      $("#thumbMsg").className = "form-msg ok"; $("#thumbMsg").textContent = t("Posters deleted: {n}.", { n: r.removed });
    } catch (e) { $("#thumbMsg").className = "form-msg bad"; $("#thumbMsg").textContent = e.message; }
  });

  // ------------------------------------------------------------------ kopie zapasowe
  const fmtDate = (ts) => { const d = new Date(ts * 1000); return d.toLocaleDateString(LOCALE) + " " + d.toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit" }); };
  async function loadBackups() {
    const box = $("#backupList");
    box.replaceChildren(el("p", "hint", t("Loading…")));
    try {
      const r = await api("/api/backups");
      box.replaceChildren();
      if (!r.backups.length) { box.appendChild(el("p", "hint", t("No backups."))); return; }
      r.backups.forEach((b, i) => {
        const row = el("div", "backup-row");
        const when = fmtDate(b.mtime);
        const info = el("div");
        info.append(el("b", null, when), el("span", "muted", " · " + (b.note || t("Settings changed"))));
        if (i === 0) info.appendChild(el("span", "tag ok", t("current")));
        const btn = el("button", "btn-soft small", t("Restore")); btn.type = "button";
        btn.disabled = i === 0;
        btn.addEventListener("click", async () => {
          const ok = await modal({ title: t("Restore settings?"),
            body: t("Settings will be restored to the state from {when}. Username and password stay unchanged. The current state is also saved as a backup, so you can go back.", { when }),
            buttons: [{ label: t("Cancel"), value: false }, { label: t("Restore"), value: true, cls: "btn-accent" }] });
          if (!ok) return;
          try {
            await api("/api/backups/restore", { name: b.name });
            toast(t("Settings restored."));
            await load(); showTab("backups");
            document.dispatchEvent(new CustomEvent("pd:settings-saved"));
          } catch (e) { toast(e.message, true); }
        });
        row.append(info, btn);
        box.appendChild(row);
      });
    } catch (e) { box.replaceChildren(el("p", "hint bad", e.message)); }
  }

  // ------------------------------------------------------------------ konto: interfejs, dziennik, komendy
  async function setInterface(data) {
    try {
      await api("/api/interface", data);
      location.reload();
    } catch (e) { toast(e.message, true); }
  }
  $("#uiLang").addEventListener("change", (e) => setInterface({ language: e.target.value }));
  $$("[data-theme-set]", dlg).forEach((b) => b.addEventListener("click", () => {
    const th = b.dataset.themeSet;
    document.documentElement.dataset.theme = th;
    $$("[data-theme-set]", dlg).forEach((x) => x.classList.toggle("on", x === b));
    api("/api/interface", { theme: th }).catch((e) => toast(e.message, true));
  }));

  function renderAccount() {
    const li = cfg.log || { size: 0, limit: 1048576, backups: [] };
    $("#logInfo").textContent = t("{size} of {limit}", { size: fmtSize(li.size), limit: fmtSize(li.limit) }) +
      (li.backups.length ? " · " + t("log backups: {n}", { n: li.backups.length }) : "");
    const dir = cfg.app_dir || "~/plex-downloader";
    const cmds = [
      [t("Connect from your computer (Terminal / PowerShell)"), `ssh ${cfg.system_user || "pi"}@${cfg.ip || "192.168.1.10"}`],
      [t("Update Plex Downloader"), `cd ${dir} && ./update.sh`],
      [t("Repair menu: update, reinstall, uninstall"), `cd ${dir} && ./fix.sh`],
      [t("Service status"), "systemctl status plex-downloader"],
      [t("Restart the service"), "sudo systemctl restart plex-downloader"],
      [t("Live service logs"), "journalctl -u plex-downloader -f"],
      [t("Reset username and password"), `cd ${dir} && ./venv/bin/python app.py --set-password && sudo systemctl restart plex-downloader`],
      [t("Check library folders"), `cd ${dir} && ./venv/bin/python app.py --check-folders`],
      [t("Free space on the disks"), "df -h"],
    ];
    const box = $("#cmdList");
    box.replaceChildren();
    cmds.forEach(([label, cmd]) => {
      const row = el("div", "cmd");
      const code = el("code", null, cmd);
      const b = el("button", "icon-btn copy"); b.type = "button"; b.title = t("Copy"); b.appendChild(icon("copy"));
      b.addEventListener("click", async () => {
        const ok = await copyText(cmd);
        b.classList.toggle("done", ok);
        b.replaceChildren(icon(ok ? "check" : "copy"));
        toast(ok ? t("Copied to clipboard.") : t("Could not copy – select the text and copy it manually."), !ok);
        setTimeout(() => { b.classList.remove("done"); b.replaceChildren(icon("copy")); }, 1800);
      });
      const pre = el("div", "cmd-code"); pre.append(code, b);
      row.append(el("div", "cmd-label", label), pre);
      box.appendChild(row);
    });
  }

  // okno dziennika (rozmiar i położenie jak okno Ustawień)
  const logWin = $("#logWin");
  makeDraggable(logWin);
  $$("[data-close-log]", logWin).forEach((b) => b.addEventListener("click", () => logWin.close()));
  async function loadLog() {
    const r = await api("/api/log");
    const pre = $("#logText");
    pre.textContent = r.text || t("(the log is empty)");
    $("#logSize").textContent = t("{size} of {limit}", { size: fmtSize(r.size), limit: fmtSize(r.limit) });
    const del = $("#logDelBackups");
    del.hidden = r.backups.length <= 1;
    del.replaceChildren(icon("trash"), document.createTextNode(t("Delete log backups from the system ({n})", { n: r.backups.length })));
    const body = pre.parentElement; body.scrollTop = body.scrollHeight;
    if (cfg) cfg.log = { size: r.size, limit: r.limit, backups: r.backups };
  }
  $("#openLog").addEventListener("click", async () => {
    const r = dlg.getBoundingClientRect();
    if (window.innerWidth >= 560) {
      logWin.style.width = r.width + "px"; logWin.style.height = r.height + "px";
      logWin.style.left = r.left + "px"; logWin.style.top = r.top + "px"; logWin.style.transform = "none";
    }
    logWin.showModal();
    try { await loadLog(); } catch (e) { toast(e.message, true); }
  });
  $("#logClear").addEventListener("click", async () => {
    const ok = await modal({ title: t("Clear the log?"), danger: true, body: t("All entries in the current log will be deleted. Log backups (bcupNN.log) stay."),
      buttons: [{ label: t("Cancel"), value: false }, { label: t("Clear"), value: true, cls: "btn-accent danger" }] });
    if (!ok) return;
    await api("/api/log/clear", {}); await loadLog(); renderAccount();
  });
  $("#logDelBackups").addEventListener("click", async () => {
    const ok = await modal({ title: t("Delete log backups?"), danger: true, body: t("All bcupNN.log files will be deleted. The current log stays."),
      buttons: [{ label: t("Cancel"), value: false }, { label: t("Delete"), value: true, cls: "btn-accent danger" }] });
    if (!ok) return;
    const r = await api("/api/log/delete-backups", {});
    toast(t("Log backups deleted: {n}", { n: r.removed })); await loadLog(); renderAccount();
  });

  $("#savePwd").addEventListener("click", async () => {
    const m = $("#pwdMsg");
    try {
      await api("/api/password", { username: $("#aUser").value, current: $("#aCur").value, new: $("#aNew").value });
      m.className = "form-msg ok"; m.textContent = t("Saved.");
      $("#aCur").value = ""; $("#aNew").value = "";
    } catch (e) { m.className = "form-msg bad"; m.textContent = e.message; }
  });

  // ------------------------------------------------------------------ odczyt formularza
  function syncFromDom() {
    if (!cfg) return;
    $$("#catRows .cat-row").forEach((row) => {
      const c = cfg.categories[+row.dataset.idx];
      if (!c) return;
      $$("[data-f]", row).forEach((i) => { c[i.dataset.f] = i.type === "checkbox" ? i.checked : i.value.trim(); });
    });
    $$("#diskRows .disk-row").forEach((row) => {
      const d = cfg.disks[+row.dataset.idx];
      if (!d) return;
      $$("[data-k]", row).forEach((i) => { d[i.dataset.k] = i.value.trim(); });
      d.paths = d.paths || {};
      $$("input[data-cat]", row).forEach((i) => { d.paths[i.dataset.cat] = i.value.trim(); });
    });
    const rows = $$("#plexRows .plex-row");
    if (rows.length || $("#plexRows").childElementCount) {
      cfg.plex_servers = rows.map((row) => {
        const s = { id: row.dataset.id };
        $$("[data-f]", row).forEach((i) => { s[i.dataset.f] = i.value.trim(); });
        return s;
      });
    }
  }

  // ------------------------------------------------------------------ otwarcie / zapis
  async function load() {
    cfg = await api("/api/settings");
    cfg.categories.forEach((c) => { c.tmp = c.id; });
    renderCats(); renderDisks(); renderPlexRows(); renderThumbDisks();
    $("#sConn").value = cfg.connections_per_file;
    $("#sConc").value = cfg.max_concurrent;
    $("#sSpeed").value = cfg.max_speed_mbps;
    $("#sMount").checked = !!cfg.require_mount;
    $("#sAutodisc").checked = !!cfg.plex_autodiscover;
    $("#sTmdb").value = cfg.tmdb_api_key || "";
    $$("input[name=thumbs]").forEach((r) => { r.checked = r.value === cfg.thumbs_mode; });
    $("#aUser").value = cfg.username; $("#aCur").value = ""; $("#aNew").value = "";
  }

  async function open(tab) {
    $("#setMsg").textContent = ""; $("#pwdMsg").textContent = ""; $("#thumbMsg").textContent = "";
    try { await load(); } catch (e) { toast(e.message, true); return; }
    if (!dlg.open) { centerWindow(dlg); dlg.showModal(); }
    showTab(tab || "disks");
    checkVersion();
  }
  async function checkVersion() {
    const u = $("#updStatus");
    u.className = "upd-status"; u.textContent = t("checking for updates…");
    try {
      const r = await api("/api/version");
      if (r.available) { u.className = "upd-status new"; u.textContent = "⬆ " + t("Update available ({n}) – run ./update.sh", { n: r.behind }); }
      else if (r.available === false) { u.className = "upd-status ok"; u.textContent = "✓ " + t("Version {v} is up to date", { v: r.version }); }
      else { u.textContent = `${t("Version")} ${r.version} · ${r.message}`; }
      u.title = r.commit ? "commit " + r.commit : "";
    } catch (e) { u.textContent = ""; }
  }

  $("#saveSettings").addEventListener("click", async () => {
    syncFromDom();
    const m = $("#setMsg");
    const body = {
      categories: cfg.categories.map((c) => ({ id: c.id, tmp: c.tmp, label: c.label, kind: c.kind, folder: c.folder, tmdb: c.tmdb })),
      disks: cfg.disks.map((d) => ({ id: d.id, label: d.label, subtitle: d.subtitle, mount: d.mount, paths: d.paths })),
      plex_servers: cfg.plex_servers,
      plex_autodiscover: $("#sAutodisc").checked,
      connections_per_file: $("#sConn").value, max_concurrent: $("#sConc").value,
      max_speed_mbps: $("#sSpeed").value, require_mount: $("#sMount").checked,
      tmdb_api_key: $("#sTmdb").value,
      thumbs_mode: ($("input[name=thumbs]:checked") || {}).value || "online",
    };
    try {
      await api("/api/settings", body);
      dlg.close();
      toast(t("Settings saved (restore point created)."));
      document.dispatchEvent(new CustomEvent("pd:settings-saved"));
      window.PD.refreshStatus();
    } catch (e) { m.className = "form-msg bad"; m.textContent = e.message; }
  });

  $("#openSettings").addEventListener("click", () => open());
  window.PD.openSettings = open;
})();
