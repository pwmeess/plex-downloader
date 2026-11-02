/* Plex Downloader – pływające okno ustawień z zakładkami */
(() => {
  "use strict";
  const { $, $$, api, el, icon, modal, toast, makeDraggable, centerWindow, fmtSize } = window.PD;
  const dlg = $("#settings");
  if (!dlg) return;
  makeDraggable(dlg);

  let cfg = null;      // ustawienia w trakcie edycji
  let tmpSeq = 0;
  const key = (c) => c.id || c.tmp;

  // ------------------------------------------------------------------ zakładki
  function showTab(name) {
    syncFromDom();
    $$(".tabs button", dlg).forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
    $$(".tab-panel", dlg).forEach((p) => { p.hidden = p.dataset.panel !== name; });
    if (name === "disks") renderDisks();
    if (name === "backups") loadBackups();
    if (name === "plex") loadPlexStatus();
    if (name === "preview") renderThumbDisks();
    $(".win-body", dlg).scrollTop = 0;
  }
  $$(".tabs button", dlg).forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
  $$("[data-close]", dlg).forEach((b) => b.addEventListener("click", () => dlg.close()));

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
    const sync = () => { title.textContent = $("[data-k=label]", row).value || "Nowy dysk"; };
    $("[data-k=label]", row).addEventListener("input", sync); sync();
    const paths = $(".cat-paths", row);
    cfg.categories.forEach((c) => {
      const w = el("div", "cat-path");
      const lab = el("label");
      lab.append(icon(window.PD.catIcon(c)), document.createTextNode(" Folder: " + (c.label || "(bez nazwy)")),
        el("span", "kind-badge", c.kind === "tv" ? "serial" : "film"));
      const inp = el("input", "input mono"); inp.dataset.cat = key(c);
      inp.value = (d.paths || {})[key(c)] || "";
      inp.placeholder = "(brak – kategoria niedostępna na tym dysku)";
      w.append(lab, inp);
      paths.appendChild(w);
    });
    $(".rm", row).addEventListener("click", () => {
      syncFromDom(); cfg.disks.splice(idx, 1); renderDisks();
    });
    $(".fill-paths", row).addEventListener("click", () => {
      const inputs = $$("input[data-cat]", row);
      const existing = inputs.map((i) => i.value.trim()).find((v) => v);
      if (!existing) { toast("Najpierw wpisz ścieżkę przynajmniej jednej kategorii, np. Filmów.", true); return; }
      const root = existing.replace(/\/+$/, "").replace(/\/[^/]*$/, "");
      let n = 0;
      inputs.forEach((i) => {
        const c = cfg.categories.find((x) => key(x) === i.dataset.cat);
        if (!i.value.trim() && c && c.folder) { i.value = root + "/" + c.folder; n++; }
      });
      toast(n ? `Uzupełniono ${n} folder(y) – sprawdź i zapisz.` : "Brak pustych pól z domyślną nazwą folderu.");
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
      const name = el("input", "input"); name.value = c.label; name.placeholder = "np. Dla dzieci"; name.dataset.f = "label";
      const kind = el("select", "input"); kind.dataset.f = "kind";
      [["movie", "Film"], ["tv", "Serial"]].forEach(([v, t]) => { const o = el("option", null, t); o.value = v; kind.appendChild(o); });
      kind.value = c.kind;
      const folder = el("input", "input mono"); folder.value = c.folder || ""; folder.placeholder = "np. Kids"; folder.dataset.f = "folder";
      const rm = el("button", "icon-btn"); rm.type = "button"; rm.title = "Usuń kategorię"; rm.appendChild(icon("trash"));
      rm.disabled = cfg.categories.length <= 1;
      rm.addEventListener("click", async () => {
        const ok = await modal({ title: "Usunąć kategorię?", danger: true,
          body: `Kategoria „${c.label}” zniknie z formularza i Menedżera plików. Pliki na dyskach zostaną nietknięte.`,
          buttons: [{ label: "Anuluj", value: false }, { label: "Usuń kategorię", value: true, cls: "btn-accent danger" }] });
        if (!ok) return;
        syncFromDom(); cfg.categories.splice(i, 1); renderCats();
      });
      kind.addEventListener("change", () => { c.kind = kind.value; ic.replaceChildren(icon(window.PD.catIcon(c))); });
      const cell = el("div", "cat-name"); cell.append(ic, name);
      row.append(cell, kind, folder, rm);
      box.appendChild(row);
    });
  }
  $("#addCat").addEventListener("click", () => {
    syncFromDom();
    cfg.categories.push({ id: "", tmp: "new-" + (++tmpSeq), label: "", kind: "movie", folder: "" });
    renderCats();
    const rows = $$("#catRows .cat-row");
    $("input", rows[rows.length - 1]).focus();
  });

  // ------------------------------------------------------------------ serwery Plex
  function renderPlexRows() {
    const box = $("#plexRows");
    box.replaceChildren();
    if (!cfg.plex_servers.length) box.appendChild(el("p", "hint", "Brak – wystarczy automatyczne wykrywanie. Dodaj ręcznie serwer w innej podsieci lub za VPN."));
    cfg.plex_servers.forEach((s, i) => {
      const row = el("div", "plex-row");
      const mk = (f, ph, v) => { const x = el("input", "input" + (f === "name" ? "" : " mono")); x.dataset.f = f; x.placeholder = ph; x.value = v || ""; return x; };
      const rm = el("button", "icon-btn"); rm.type = "button"; rm.appendChild(icon("trash")); rm.title = "Usuń";
      rm.addEventListener("click", () => { syncFromDom(); cfg.plex_servers.splice(i, 1); renderPlexRows(); });
      row.append(mk("name", "Nazwa, np. Salon", s.name), mk("host", "adres IP, np. 192.168.1.20", s.host), mk("port", "32400", s.port), rm);
      row.dataset.id = s.id || "";
      box.appendChild(row);
    });
  }
  $("#addPlex").addEventListener("click", () => { syncFromDom(); cfg.plex_servers.push({ name: "", host: "", port: 32400 }); renderPlexRows(); });
  function renderPlexList(list) {
    const box = $("#plexList");
    box.replaceChildren();
    if (!list.length) { box.appendChild(el("p", "hint", "Nie wykryto żadnego serwera Plex. Sprawdź, czy Plex Media Server działa, albo dodaj go ręcznie poniżej.")); return; }
    list.forEach((p) => {
      const r = el("div", "plex-item");
      r.append(el("span", "dot" + (p.online ? "" : " bad")), el("b", null, p.name),
        el("span", "mono", `${p.display_host}:${p.port}`),
        el("span", "muted", (p.online ? "online" : "offline") + (p.version ? ` · ${p.version}` : "")),
        el("span", "tag", p.source === "manual" ? "ręcznie" : p.source === "local" ? "ten Raspberry Pi" : "wykryty"));
      const a = el("a", null, "Otwórz ↗"); a.href = `http://${p.display_host}:${p.port}/web`; a.target = "_blank"; a.rel = "noopener";
      r.appendChild(a);
      box.appendChild(r);
    });
  }
  async function loadPlexStatus() {
    try { renderPlexList((await api("/api/status")).plex); } catch (e) { /* bez znaczenia */ }
  }
  $("#plexDiscover").addEventListener("click", async (e) => {
    const b = e.currentTarget; b.disabled = true;
    $("#plexList").replaceChildren(el("p", "hint", "Szukam serwerów w sieci…"));
    try {
      const r = await api("/api/plex/discover", {});
      renderPlexList(r.status);
      toast(r.found.length ? `Znaleziono serwerów: ${r.found.length}` : "Nie znaleziono serwerów protokołem GDM.");
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
      $("#thumbMsg").textContent = "Rozpoczęto pobieranie okładek – postęp widać w Menedżerze plików.";
    } catch (e) { $("#thumbMsg").className = "form-msg bad"; $("#thumbMsg").textContent = e.message; }
  });
  $("#thumbDelete").addEventListener("click", async () => {
    const disk = $("#thumbDisk").value;
    const label = $("#thumbDisk").selectedOptions[0] ? $("#thumbDisk").selectedOptions[0].textContent : disk;
    const ok = await modal({ title: "Usunąć okładki?", danger: true,
      body: `Zostaną usunięte wszystkie pliki *.thumb.png / *.thumb.jpg z dysku „${label}”. Filmy zostaną nietknięte.`,
      buttons: [{ label: "Anuluj", value: false }, { label: "Usuń okładki", value: true, cls: "btn-accent danger" }] });
    if (!ok) return;
    try {
      const r = await api("/api/fm/thumbs/delete", { disk });
      $("#thumbMsg").className = "form-msg ok"; $("#thumbMsg").textContent = `Usunięto okładek: ${r.removed}.`;
    } catch (e) { $("#thumbMsg").className = "form-msg bad"; $("#thumbMsg").textContent = e.message; }
  });

  // ------------------------------------------------------------------ kopie zapasowe
  async function loadBackups() {
    const box = $("#backupList");
    box.replaceChildren(el("p", "hint", "Wczytuję…"));
    try {
      const r = await api("/api/backups");
      box.replaceChildren();
      if (!r.backups.length) { box.appendChild(el("p", "hint", "Brak kopii.")); return; }
      r.backups.forEach((b, i) => {
        const row = el("div", "backup-row");
        const dt = new Date(b.mtime * 1000);
        const when = dt.toLocaleDateString("pl-PL") + " " + dt.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
        const info = el("div");
        info.append(el("b", null, when), el("span", "muted", " · " + (b.note || "Zmiana ustawień")));
        if (i === 0) info.appendChild(el("span", "tag ok", "bieżąca"));
        const btn = el("button", "btn-soft small", "Przywróć"); btn.type = "button";
        btn.disabled = i === 0;
        btn.addEventListener("click", async () => {
          const ok = await modal({ title: "Przywrócić ustawienia?",
            body: `Ustawienia zostaną przywrócone do stanu z ${when}. Login i hasło pozostaną bez zmian. Obecny stan też zostanie zapisany jako kopia, więc możesz wrócić.`,
            buttons: [{ label: "Anuluj", value: false }, { label: "Przywróć", value: true, cls: "btn-accent" }] });
          if (!ok) return;
          try {
            await api("/api/backups/restore", { name: b.name });
            toast("Przywrócono ustawienia.");
            await load(); showTab("backups");
            document.dispatchEvent(new CustomEvent("pd:settings-saved"));
          } catch (e) { toast(e.message, true); }
        });
        row.append(info, btn);
        box.appendChild(row);
      });
    } catch (e) { box.replaceChildren(el("p", "hint bad", e.message)); }
  }

  // ------------------------------------------------------------------ konto
  $("#savePwd").addEventListener("click", async () => {
    const m = $("#pwdMsg");
    try {
      await api("/api/password", { username: $("#aUser").value, current: $("#aCur").value, new: $("#aNew").value });
      m.className = "form-msg ok"; m.textContent = "Zapisano.";
      $("#aCur").value = ""; $("#aNew").value = "";
    } catch (e) { m.className = "form-msg bad"; m.textContent = e.message; }
  });

  // ------------------------------------------------------------------ odczyt formularza
  function syncFromDom() {
    if (!cfg) return;
    $$("#catRows .cat-row").forEach((row) => {
      const c = cfg.categories[+row.dataset.idx];
      if (!c) return;
      $$("[data-f]", row).forEach((i) => { c[i.dataset.f] = i.value.trim(); });
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
    $("#pillowNote").textContent = cfg.pillow ? "" :
      "Brak biblioteki Pillow – okładki zapiszą się jako .thumb.jpg (uruchom ./update.sh, aby ją doinstalować).";
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
    u.className = "upd-status"; u.textContent = "sprawdzam aktualizacje…";
    try {
      const r = await api("/api/version");
      if (r.available) { u.className = "upd-status new"; u.textContent = `⬆ Dostępna aktualizacja (${r.behind}) – uruchom ./update.sh`; }
      else if (r.available === false) { u.className = "upd-status ok"; u.textContent = `✓ Wersja ${r.version} jest aktualna`; }
      else { u.textContent = `Wersja ${r.version} · ${r.message}`; }
      u.title = r.commit ? "commit " + r.commit : "";
    } catch (e) { u.textContent = ""; }
  }

  $("#saveSettings").addEventListener("click", async () => {
    syncFromDom();
    const m = $("#setMsg");
    const body = {
      categories: cfg.categories.map((c) => ({ id: c.id, tmp: c.tmp, label: c.label, kind: c.kind, folder: c.folder })),
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
      toast("Zapisano ustawienia (utworzono punkt przywracania).");
      document.dispatchEvent(new CustomEvent("pd:settings-saved"));
      window.PD.refreshStatus();
    } catch (e) { m.className = "form-msg bad"; m.textContent = e.message; }
  });

  $("#openSettings").addEventListener("click", () => open());
  window.PD.openSettings = open;
})();
