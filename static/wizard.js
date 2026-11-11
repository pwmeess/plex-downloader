/* Plex Downloader – first-run wizard (language, theme, installation type, disks, Plex, TMDB) */
(() => {
  "use strict";
  const { $, $$, t, LANG, api, fmtSize, el, icon, toast, copyText, modal } = window.PD;
  const REPO = "https://github.com/pwmeess/plex-downloader";
  const GUIDE = { en: REPO + "#installation", pl: REPO + "/blob/main/README.pl.md#instalacja" };
  const STEPS = [
    { id: "language", label: () => t("Language") },
    { id: "theme", label: () => t("Theme") },
    { id: "type", label: () => t("Installation") },
    { id: "disks", label: () => t("Disks and folders") },
    { id: "plex", label: () => t("Plex server") },
    { id: "tmdb", label: () => t("TMDB key") },
    { id: "summary", label: () => t("Summary") },
  ];
  const ss = { get(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { sessionStorage.setItem(k, v); } catch (e) { /* */ } } };

  let S = null;          // server state
  let W = null;          // wizard choices (kept in sessionStorage – survives the reload after a language change)
  let checkTimer = null;

  function saveW() { ss.set("plexdl.wizard", JSON.stringify(W)); }
  function freshW() {
    return { step: 0, type: "disks", disks: {}, sd: null, net: {}, manual: "", plexAuto: S.plex_autodiscover !== false,
      servers: (S.plex_servers || []).map((p) => ({ name: p.name, host: p.host, port: p.port })), tmdbKey: null, create: false, createTouched: false };
  }
  // categories can be renamed / added in the wizard (kept in W until Finish)
  const cats = () => W.cats || S.categories || [];
  const KIND = { movie: () => t("movie"), tv: () => t("TV show"), other: () => t("other") };
  const BUILTIN = ["movies", "tv", "kids"];
  const slug = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/ł/g, "l")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 20) || "cat";
  function uniqueId(base) {
    let id = base, n = 2;
    while (cats().some((c) => c.id === id)) id = base.slice(0, 20) + "-" + n++;
    return id;
  }
  const baseName = (p) => (p.replace(/\/+$/, "").split("/").pop() || p);
  // default button name (max. 16 characters; renamed later with the gear on the disk tile)
  const shortName = (p) => baseName(p).replace(/[_]+/g, " ").trim().slice(0, 16);

  // ------------------------------------------------------------------ helpers
  function info(tip) { const b = el("button", "info-i", "i"); b.type = "button"; b.dataset.tip = tip; return b; }
  function h(text, tip) { const x = el("h2", "wz-h", text); if (tip) x.append(" ", info(tip)); return x; }
  function p(text, cls) { return el("p", cls || "wz-p", text); }
  function cmdBlock(lines) {
    const box = el("div", "cmd-list");
    lines.forEach(([label, cmd]) => {
      const row = el("div", "cmd");
      if (label) row.appendChild(el("div", "cmd-label", label));
      const code = el("div", "cmd-code");
      const c = el("button", "copy"); c.type = "button"; c.title = t("Copy"); c.appendChild(icon("copy"));
      c.addEventListener("click", async () => { if (await copyText(cmd)) { c.classList.add("done"); toast(t("Copied to clipboard.")); setTimeout(() => c.classList.remove("done"), 1500); } });
      code.append(el("code", null, cmd), c);
      row.appendChild(code); box.appendChild(row);
    });
    return box;
  }
  function choice(name, value, title, desc, tip, checked, onPick, badge) {
    const lab = el("label", "choice" + (checked ? " on" : ""));
    const r = el("input"); r.type = "radio"; r.name = name; r.value = value; r.checked = checked;
    r.addEventListener("change", () => { $$(`input[name=${name}]`).forEach((x) => x.closest(".choice").classList.toggle("on", x.checked)); onPick(value); });
    const txt = el("div", "choice-txt");
    const tt = el("b", null, title); if (badge) tt.append(" ", el("span", "tag " + (badge.cls || ""), badge.text));
    txt.append(tt, el("span", "muted", desc));
    lab.append(r, txt);
    if (tip) lab.appendChild(info(tip));
    return lab;
  }
  function networkCommands() {
    const user = S.system_user || "pi";
    return [
      [t("1. Install the network share tools"), "sudo apt install -y cifs-utils"],
      [t("2. Create a folder for the share"), "sudo mkdir -p /mnt/plex"],
      [t("3. Mount the share now (replace the IP, share name and user)"),
        `sudo mount -t cifs //192.168.1.10/SHARE /mnt/plex -o username=USER,uid=${user},gid=${user},iocharset=utf8`],
      [t("4. Mount it automatically after every restart – add this line to /etc/fstab (sudo nano /etc/fstab)"),
        `//192.168.1.10/SHARE /mnt/plex cifs credentials=/home/${user}/.smbcredentials,uid=${user},gid=${user},iocharset=utf8,_netdev,nofail 0 0`],
      [t("5. Save the share password in a file only you can read"),
        `printf 'username=USER\\npassword=PASSWORD\\n' > ~/.smbcredentials && chmod 600 ~/.smbcredentials`],
    ];
  }

  // ------------------------------------------------------------------ disk model
  function diskEntry(m) {
    if (!W.disks[m.mount]) {
      // running the wizard again: start from the disks that are already configured
      const cur = (S.disks || []).find((x) => (x.mount || "").replace(/\/+$/, "") === m.mount);
      W.disks[m.mount] = cur ? { use: true, label: cur.label, mount: m.mount, paths: Object.assign({}, cur.paths), scanned: true }
        : { use: false, label: shortName(m.mount), mount: m.mount, paths: {}, scanned: false };
    }
    return W.disks[m.mount];
  }
  function chosenDisks() {
    if (W.skipDisks) return [];
    if (W.type === "sd") return W.sd ? [W.sd] : [];
    if (W.type === "network") return Object.values(W.net).filter((d) => d.use);
    return Object.values(W.disks).filter((d) => d.use);
  }
  function allPaths() { return chosenDisks().flatMap((d) => Object.values(d.paths).filter(Boolean)); }

  async function scanDisk(d, after) {
    try {
      const r = await api("/api/wizard/scan", { mount: d.mount, categories: cats(), hints: W.fileDisks || [] });
      if (r.match && !d.labelSet) d.label = r.match;   // button name of the matching disk from the settings file
      // missing folders go next to the ones that were found (e.g. „Plex 1T/Kids”), otherwise into „Plex/”
      const found = Object.values(r.result).filter((x) => x.status === "found").map((x) => x.path);
      d.foundCount = found.length;
      // no category folder yet: suggest them inside the disk's „Plex” folder (if there is one)
      const root = found.length ? found[0].replace(/\/[^/]+$/, "") : (r.plex_dir || `${d.mount.replace(/\/$/, "")}/Plex`);
      d.root = root;
      cats().forEach((c) => {
        const x = r.result[c.id] || {};
        if (!d.paths[c.id]) d.paths[c.id] = x.path || `${root}/${c.folder || c.label}`;
      });
    } catch (e) {
      cats().forEach((c) => { if (!d.paths[c.id]) d.paths[c.id] = `${d.mount.replace(/\/$/, "")}/Plex/${c.folder || c.label}`; });
    }
    d.scanned = true; saveW();
    if (after) after();
  }

  const status = {};   // path → check result
  function scheduleCheck() {
    clearTimeout(checkTimer);
    checkTimer = setTimeout(async () => {
      const paths = allPaths();
      if (!paths.length) return;
      try {
        const r = await api("/api/wizard/check", { paths });
        r.result.forEach((x) => { status[x.path] = x; });
        paintStatus();
      } catch (e) { /* */ }
    }, 350);
  }
  function statusText(x) {
    if (!x) return ["", ""];
    if (x.problem && x.exists) return ["bad", t("no write permission – fix: sudo chown -R {user}: \"{path}\"", { user: S.system_user || "pi", path: x.path })];
    if (x.problem && !x.exists && x.problem !== t("Folder does not exist")) return ["bad", x.problem];
    if (!x.exists) return [W.create ? "warn" : "bad", W.create ? t("will be created") : t("Folder does not exist")];
    return ["ok", "✓ " + t("OK") + (x.free != null ? " · " + t("Free: {free}", { free: fmtSize(x.free) }) : "")];
  }
  function paintStatus() {
    // „Create missing folders”: ticked by itself only when something is missing (until the user decides)
    const missingNow = allPaths().some((x) => status[x] && !status[x].exists);
    if (!W.createTouched && W.create !== missingNow) {
      W.create = missingNow; saveW();
      $$(".wz-create-row input").forEach((cb) => { cb.checked = W.create; });
    }
    $$(".wz-path").forEach((row) => {
      const inp = $("input", row), m = $(".wz-st", row);
      if (!inp || !m) return;   // disk name row has no status
      const [cls, msg] = statusText(status[inp.value.trim()]);
      m.className = "wz-st " + cls; m.textContent = msg;
    });
    // missing folders and the box unticked → draw attention to „Create missing folders”
    const missing = allPaths().some((x) => status[x] && !status[x].exists);
    $$(".wz-create-row").forEach((r) => r.classList.toggle("attn", missing && !W.create));
  }
  function rootOf(d) {
    if (d.root) return d.root;
    const used = Object.values(d.paths).filter(Boolean);
    return used.length ? used[0].replace(/\/[^/]+$/, "") : `${d.mount.replace(/\/$/, "")}/Plex`;
  }
  const suggest = (d, c) => `${rootOf(d)}/${c.folder || c.label}`;
  // a change in the wizard that needs new folders ticks „Create missing folders” and highlights it
  function wantCreate() {
    W.create = true; saveW();
    setTimeout(() => {
      $$(".wz-create-row").forEach((r) => {
        const cb = $("input", r); if (cb) cb.checked = true;
        r.classList.remove("flash"); void r.offsetWidth; r.classList.add("flash");
      });
    }, 50);
  }
  function rerender() { render(); scheduleCheck(); }
  // disks step: every mounted disk / share is checked once; the ones with library folders are ticked
  let probing = false;
  async function autoProbe() {
    if (probing) return;
    await null;   // the step is in the page now
    const list = (W.type === "network" ? Object.values(W.net) : W.type === "disks" ? Object.values(W.disks) : [])
      .filter((d) => !d.probed && !d.manual);
    if (!list.length) return;
    probing = true;
    const note = $(".wz-probe");
    if (note) note.hidden = false;
    let changed = false;
    for (const d of list) {
      if (!d.scanned) await scanDisk(d);
      d.probed = true;
      if (!d.use && d.foundCount > 0) { d.use = true; changed = true; }
    }
    saveW(); probing = false;
    if (STEPS[W.step] && STEPS[W.step].id === "disks") { render(); scheduleCheck(); }
    else if (changed) saveW();
  }
  // name, folder and type of a category (rename or new)
  async function catDialog(c) {
    const body = el("div", "mkdir-box");
    body.appendChild(el("p", null, c ? t("The new name applies to all disks. Folders that do not exist yet get the new folder name.")
      : t("A new category is a new button on the download page and in the File manager, e.g. Concerts.")));
    const l1 = el("label", "small-label", t("Name")); const name = el("input", "input"); name.maxLength = 40; name.value = c ? c.label : "";
    const l2 = el("label", "small-label", t("Folder name")); const folder = el("input", "input mono"); folder.maxLength = 60; folder.value = c ? (c.folder || c.label) : "";
    const l3 = el("label", "small-label", t("Type"));
    const kind = el("select", "input");
    Object.keys(KIND).forEach((k) => { const o = el("option", null, KIND[k]()); o.value = k; kind.appendChild(o); });
    kind.value = c ? c.kind : "movie";
    let folderTouched = !!c;
    folder.addEventListener("input", () => { folderTouched = true; });
    name.addEventListener("input", () => { if (!folderTouched) folder.value = name.value.trim(); });
    body.append(l1, name, l2, folder, l3, kind);
    body._onOpen = () => { name.focus(); name.select(); };
    const ok = await modal({ title: c ? t("Rename category") : t("Add category"), body,
      buttons: [{ label: t("Cancel"), value: false },
                { label: c ? t("Save") : t("Add"), cls: "btn-accent", value: () => {
                  const n = name.value.trim(), f = folder.value.trim();
                  if (!n || !f || /[/\\]|^\.\.?$/.test(f)) { toast(t("Enter a name and a folder name without /."), true); return undefined; }
                  if (cats().some((x) => x !== c && x.id !== (c && c.id) && x.label.toLowerCase() === n.toLowerCase())) {
                    toast(t("A category with this name already exists."), true); return undefined;
                  }
                  return { label: n, folder: f, kind: kind.value };
                } }] });
    return ok || null;
  }
  function allDisks() { return [W.sd, ...Object.values(W.disks), ...Object.values(W.net)].filter(Boolean); }
  async function renameCat(c) {
    const v = await catDialog(c);
    if (!v) return;
    if (!W.cats) W.cats = JSON.parse(JSON.stringify(S.categories || []));
    const cat = W.cats.find((x) => x.id === c.id);
    const oldFolder = cat.folder || cat.label;
    let id = cat.id;
    // a renamed built-in category (e.g. Kids → Concerts) becomes a new category, so Kids folders are not matched any more
    if (BUILTIN.includes(id) && v.label !== c.label) id = uniqueId(slug(v.label));
    Object.assign(cat, v, { id, tmdb: v.kind !== "other" });
    allDisks().forEach((d) => {
      let p = d.paths[c.id];
      if (id !== c.id) { delete d.paths[c.id]; }
      if (p && p.split("/").pop() === oldFolder && !(status[p] && status[p].exists)) p = p.replace(/[^/]+$/, v.folder);
      if (p !== undefined) d.paths[id] = p;
    });
    wantCreate(); rerender();
  }
  async function addCat(d) {
    const v = await catDialog(null);
    if (!v) return;
    if (!W.cats) W.cats = JSON.parse(JSON.stringify(S.categories || []));
    const c = Object.assign({ id: uniqueId(slug(v.label)), tmdb: v.kind !== "other" }, v);
    W.cats.push(c);
    d.paths[c.id] = suggest(d, c);
    wantCreate(); rerender();
  }
  function pathRows(d) {
    const box = el("div", "wz-paths");
    cats().forEach((c) => {
      const row = el("div", "wz-path");
      const lab = el("div", "wz-cat");
      const gear = el("button", "icon-btn wz-cat-gear"); gear.type = "button"; gear.title = t("Rename category"); gear.appendChild(icon("gear"));
      gear.addEventListener("click", () => renameCat(c));
      lab.append(gear, el("span", null, c.label));
      const inp = el("input", "input mono"); inp.value = d.paths[c.id] || ""; inp.spellcheck = false;
      inp.placeholder = t("(none – category not available on this disk)");
      inp.addEventListener("input", () => { d.paths[c.id] = inp.value.trim(); saveW(); scheduleCheck(); });
      const st = el("span", "wz-st");
      const tool = el("button", "icon-btn wz-cat-x"); tool.type = "button";
      if (inp.value) {
        tool.title = t("Not on this disk"); tool.appendChild(icon("x"));
        tool.addEventListener("click", () => { d.paths[c.id] = ""; saveW(); rerender(); });
      } else {
        tool.title = t("Use on this disk"); tool.appendChild(icon("retry"));
        tool.addEventListener("click", () => { d.paths[c.id] = suggest(d, c); wantCreate(); rerender(); });
        row.classList.add("off");
      }
      row.append(lab, inp, st, tool);
      box.appendChild(row);
    });
    const add = el("button", "btn-ghost small wz-add-cat", "+ " + t("Add category")); add.type = "button";
    add.addEventListener("click", () => addCat(d));
    box.appendChild(add);
    return box;
  }
  function diskCard(d, m, removable) {
    const card = el("div", "wz-disk" + (d.use ? " on" : ""));
    const head = el("div", "wz-disk-head");
    const cb = el("input"); cb.type = "checkbox"; cb.checked = d.use;
    const lab = el("label", "check"); lab.append(cb, el("b", null, " " + d.mount));
    head.appendChild(lab);
    if (m) head.appendChild(el("span", "muted", `${m.fs} · ${t("Free: {free}", { free: fmtSize(m.free) })} / ${fmtSize(m.total)}`));
    card.appendChild(head);
    const body = el("div", "wz-disk-body"); body.hidden = !d.use;
    body.append(pathRows(d));
    card.appendChild(body);
    cb.addEventListener("change", async () => {
      d.use = cb.checked; card.classList.toggle("on", d.use); body.hidden = !d.use; saveW();
      if (d.use && !d.scanned) await scanDisk(d, () => { body.replaceChildren(pathRows(d)); scheduleCheck(); });
      else scheduleCheck();
    });
    if (removable) {
      const x = el("button", "icon-btn"); x.type = "button"; x.title = t("Remove"); x.appendChild(icon("trash"));
      x.addEventListener("click", () => { delete W.net[d.mount]; saveW(); render(); });
      head.appendChild(x);
    }
    return card;
  }
  function createBox() {
    const lab = el("label", "check wz-create");
    const cb = el("input"); cb.type = "checkbox"; cb.checked = W.create;
    cb.addEventListener("change", () => { W.create = cb.checked; W.createTouched = true; saveW(); paintStatus(); });
    lab.append(cb, document.createTextNode(" " + t("Create missing folders when finishing")));
    const row = el("div", "wz-create-row");
    row.append(lab, info(t("Missing folders (status “will be created”) are created when you click Finish. Untick it if you prefer to create them yourself.")));
    return row;
  }

  // ------------------------------------------------------------------ settings file (optional)
  function importBox() {
    const box = el("div", "wz-import");
    if (W.imported) {
      const m = W.imported;
      const ok = el("p", "wz-import-ok");
      ok.append(icon("check"), document.createTextNode(" " + t("Settings loaded from {name} (version {v}, exported {when}).",
        { name: m.name, v: m.version || "?", when: m.exported || "?" })));
      const undo = el("button", "linklike", t("Do not use the file")); undo.type = "button";
      undo.addEventListener("click", () => { const step = W.step; W = freshW(); W.step = step; saveW(); render(); });
      box.append(ok, undo);
      return box;
    }
    const row = el("div", "wz-import-row");
    const b = el("button", "btn-soft small", t("I have a settings file – load it")); b.type = "button";
    b.prepend(icon("up"));
    const file = el("input"); file.type = "file"; file.accept = ".json,application/json"; file.hidden = true;
    b.addEventListener("click", () => { file.value = ""; file.click(); });
    file.addEventListener("change", () => file.files[0] && loadFile(file.files[0]));
    row.append(b, info(t("Optional. A settings file is created in Settings → Backups → Export settings – for example on your other Raspberry Pi or before a clean reinstall.\n\nNo file? No problem – the wizard guides you through everything step by step.\n\nWith a file, the wizard fills in your categories (also your own, e.g. Concerts), Plex servers, download and poster options, language, theme and the TMDB key (if it was exported). Disk paths are matched to the disks of this device, so you only check them in the “Disks and folders” step. Nothing is saved until you click Finish.")), file);
    box.append(row, p(t("Optional – e.g. when you set up a second Raspberry Pi or reinstall."), "muted"));
    return box;
  }
  function fileDisksNote(box) {
    if (!W.fileDisks || !W.fileDisks.length) return;
    const n = el("div", "wz-file-disks");
    n.appendChild(el("p", null, t("Disks in the settings file (paths of the device it was exported from):")));
    const ul = el("ul", "plan-list");
    W.fileDisks.forEach((d) => { const li = el("li"); li.append(el("b", null, d.label), " ", el("span", "mono muted", d.mount)); ul.appendChild(li); });
    n.append(ul, el("p", "muted", t("Tick the matching disks of this device – folders from the file are found and matched automatically.")));
    box.appendChild(n);
  }
  async function loadFile(f) {
    let data;
    try { data = JSON.parse(await f.text()); } catch (e) { toast(t("This is not a Plex Downloader settings file."), true); return; }
    let r;
    try { r = await api("/api/wizard/import", { data }); } catch (e) { toast(e.message, true); return; }
    const d = r.data;
    W.imported = { name: f.name, version: r.meta.version, exported: r.meta.exported };
    if (d.categories) W.cats = d.categories;
    if (d.plex_servers) W.servers = d.plex_servers.map((s) => ({ name: s.name, host: s.host, port: s.port }));
    if ("plex_autodiscover" in d) W.plexAuto = d.plex_autodiscover;
    if (d.tmdb_api_key) W.tmdbKey = d.tmdb_api_key;
    W.opts = {};
    ["connections_per_file", "max_concurrent", "max_speed_mbps", "thumbs_mode"].forEach((k) => { if (k in d) W.opts[k] = d[k]; });
    W.fileDisks = (d.disks || []).map((x) => ({ label: x.label, mount: x.mount, paths: x.paths }));
    // a library on the SD card in the file → suggest the same installation type
    if (W.fileDisks.length && W.fileDisks.every((x) => x.mount === "/")) W.type = "sd";
    W.disks = {}; W.net = {}; W.sd = null;   // disks are matched again with the file in mind
    W.step = 2; saveW();
    toast(t("Settings file loaded – check the next steps."));
    const iface = {};
    if (d.language && d.language !== LANG) iface.language = d.language;
    if (d.theme && d.theme !== (document.documentElement.dataset.theme || "dark")) iface.theme = d.theme;
    if (Object.keys(iface).length) {
      try { await api("/api/interface", iface); } catch (e) { /* */ }
      setTimeout(() => location.reload(), 500);
      return;
    }
    render();
  }

  // ------------------------------------------------------------------ steps
  const VIEWS = {
    language() {
      const box = el("div");
      box.append(h(t("Choose your language")), p(t("You can change it later in Settings → Account.")));
      const pick = el("div", "lang-pick");
      [["en", "English"], ["pl", "Polski"]].forEach(([code, name]) => {
        const b = el("button", "lang-btn" + (code === LANG ? " on" : "")); b.type = "button";
        b.append(el("span", "lang-code", code.toUpperCase()), el("span", null, name));
        if (code === "en") b.appendChild(el("span", "tag", t("default")));
        b.addEventListener("click", async () => {
          W.step = 1; saveW();
          if (code !== LANG) { await api("/api/interface", { language: code }); location.reload(); } else render();
        });
        pick.appendChild(b);
      });
      box.appendChild(pick);
      box.appendChild(importBox());
      return box;
    },
    theme() {
      const box = el("div");
      box.append(h(t("Theme")));
      const cur = document.documentElement.dataset.theme || "dark";
      const row = el("div", "wz-choices");
      [["dark", t("Dark")], ["light", t("Light")]].forEach(([v, name]) => {
        row.appendChild(choice("wzTheme", v, name, v === "dark" ? t("default") : "", null, cur === v, async (val) => {
          document.documentElement.dataset.theme = val;
          try { await api("/api/interface", { theme: val }); } catch (e) { toast(e.message, true); }
        }));
      });
      box.appendChild(row);
      return box;
    },
    type() {
      const box = el("div");
      box.append(h(t("Where is your Plex library?")), p(t("Choose how the library is stored. You can add or change disks later in Settings → Disks.")));
      const list = el("div", "wz-choices col");
      list.append(
        choice("wzType", "disks", t("External disks"), t("USB sticks or SSD/HDD disks connected to this Raspberry Pi."),
          t("Best choice: fast, large and gentle on the SD card. The disks must be mounted permanently (in /etc/fstab), so they are always at the same path after a restart. Folders on each disk are found automatically."),
          W.type === "disks", (v) => { W.type = v; saveW(); }, { text: t("recommended"), cls: "ok" }),
        choice("wzType", "sd", t("Library on the SD card"), t("No disks – folders in your home folder on the SD card. Good for a quick test."),
          t("Not recommended for everyday use: the SD card is small, slower than a disk and wears out faster with large writes. If it fills up completely, the whole system may stop working."),
          W.type === "sd", (v) => { W.type = v; saveW(); }, { text: t("not recommended"), cls: "warn" }),
        choice("wzType", "network", t("Plex on another device"), t("The library is on another computer (e.g. a second Raspberry Pi with Plex) and shared over the network (SMB or NFS)."),
          t("Plex and Plex Downloader must see the same files: Downloader saves into the network share, Plex reads the same folders on its own computer (the paths there may be different). The share has to be mounted on this Raspberry Pi first – the next step shows the commands. Give both devices a fixed IP address in your router."),
          W.type === "network", (v) => { W.type = v; saveW(); }, { text: t("slower downloads"), cls: "warn" }));
      box.appendChild(list);
      return box;
    },
    disks() {
      const box = el("div");
      if (W.type === "sd") {
        box.append(h(t("Library on the SD card"), t("Not recommended for everyday use: the SD card is small, slower than a disk and wears out faster with large writes. If it fills up completely, the whole system may stop working.")));
        box.appendChild(el("p", "plan-warn", t("Keep at least a few GB free on the card.")));
        if (!W.sd) {
          W.sd = { use: true, label: t("SD card"), mount: "/", paths: {}, scanned: true };
          cats().forEach((c) => { W.sd.paths[c.id] = `${S.home}/Plex/${c.folder || c.label}`; });
          saveW();
        }
        const root = (S.mounts || []).find((m) => m.root);
        if (root) box.appendChild(p(t("SD card: {free} free of {total}.", { free: fmtSize(root.free), total: fmtSize(root.total) }), "muted"));
        box.append(pathRows(W.sd), createBox());
        box.appendChild(p(t("Share the Plex folder over SMB if you want to copy files from your computer – see the guide."), "muted"));
      } else if (W.type === "network") {
        box.append(h(t("Network share"), t("Plex and Plex Downloader must see the same files: Downloader saves into the network share, Plex reads the same folders on its own computer (the paths there may be different). The share has to be mounted on this Raspberry Pi first – the next step shows the commands. Give both devices a fixed IP address in your router.")));
        const slow = el("p", "wz-p wz-note");
        slow.append(document.createTextNode(t("Downloads are slower in this setup than with a disk connected directly.") + " "), info(t('Every downloaded byte travels twice over your home network: from the internet to this Raspberry Pi, then to the computer with the disks. Over Wi-Fi (e.g. a Raspberry Pi Zero 2 W, 2.4 GHz only) expect only a few MB/s. A cable connection on both devices – or running Plex Downloader on the computer that has the disks – is much faster.')));
        box.appendChild(slow);
        const nets = (S.mounts || []).filter((m) => m.network);
        if (nets.length) {
          fileDisksNote(box);
          box.appendChild(p(t("Network shares mounted on this Raspberry Pi:")));
          const pr = el("p", "muted wz-probe", t("Looking for library folders…")); pr.hidden = true; box.appendChild(pr);
          nets.forEach((m) => {
            // button name: the share name (“//192.168.1.10/Plex Media Share 1024” → “Plex Media Share 1024”)
            const share = (m.device || "").replace(/\/+$/, "").split("/").pop();
            const d = W.net[m.mount] || (W.net[m.mount] = { use: false, label: share && share.length <= 16 ? share : shortName(m.mount), mount: m.mount, paths: {}, scanned: false });
            box.appendChild(diskCard(d, m));
          });
        } else {
          box.appendChild(el("p", "plan-warn", t("No network share is mounted on this Raspberry Pi yet.")));
        }
        Object.values(W.net).filter((d) => d.manual).forEach((d) => box.appendChild(diskCard(d, null, true)));
        const det = el("details", "wz-howto");
        det.open = !nets.length;
        const sum = el("summary", null, t("How to mount a network share (SMB) – commands to copy"));
        sum.appendChild(info(t("Log in to this Raspberry Pi over SSH, run the commands one by one and replace 192.168.1.10, SHARE, USER and PASSWORD with the details of the computer that shares the library. Then click “Check again”.")));
        det.append(sum, cmdBlock(networkCommands()),
          p(t("After editing /etc/fstab run “sudo mount -a” – if it shows no error, the share will also be mounted after a restart."), "muted"));
        box.appendChild(det);
        const row = el("div", "wz-row");
        const again = el("button", "btn-soft small", t("Check again")); again.type = "button";
        again.addEventListener("click", async () => { S = await api("/api/wizard/state"); render(); });
        const mi = el("input", "input mono"); mi.placeholder = "/mnt/plex"; mi.value = W.manual || "";
        mi.addEventListener("input", () => { W.manual = mi.value.trim(); saveW(); });
        const add = el("button", "btn-soft small", t("Use this folder")); add.type = "button";
        add.addEventListener("click", async () => {
          const m = (W.manual || "").replace(/\/+$/, "");
          if (!m.startsWith("/")) { toast(t("The path “%s” must be absolute (start with /).").replace("%s", m || "?"), true); return; }
          W.net[m] = { use: true, manual: true, label: shortName(m), mount: m, paths: {}, scanned: false };
          await scanDisk(W.net[m]); render();
        });
        row.append(again, mi, add);
        box.appendChild(row);
        box.appendChild(createBox());
      } else {
        box.append(h(t("Disks and folders"), t("Every disk needs a folder for each category (Movies, TV Shows…). Existing folders are found automatically; missing ones can be created. Leave a field empty if a category should not be on that disk.")));
        const disks = (S.mounts || []).filter((m) => !m.root && !m.network);
        if (!disks.length) {
          box.appendChild(el("p", "plan-warn", t("No external disk is mounted. Connect the disk, mount it permanently (see the guide), then click “Check again”.")));
          box.appendChild(cmdBlock([[t("Show disks and their mount points"), "lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT"]]));
        } else {
          fileDisksNote(box);
          box.appendChild(p(t("Select the disks for the library:")));
          const pr = el("p", "muted wz-probe", t("Looking for library folders…")); pr.hidden = true; box.appendChild(pr);
          disks.forEach((m) => box.appendChild(diskCard(diskEntry(m), m)));
          box.appendChild(createBox());
        }
        const again = el("button", "btn-soft small", t("Check again")); again.type = "button";
        again.addEventListener("click", async () => { S = await api("/api/wizard/state"); render(); });
        box.appendChild(el("div", "wz-row")).appendChild(again);
      }
      box.appendChild(p(t("⚙ rename a category · ✕ not on this disk · + add a category. Disk names and their order can be changed later in Settings."), "muted wz-small"));
      // „Skip – set up disks later”: small grey button on the right, just above „Next”
      const skip = el("div", "wz-skip");
      const sb = el("button", "btn-soft small", t("Skip – set up disks later")); sb.type = "button";
      sb.addEventListener("click", () => { W.skipDisks = true; W.step = STEPS.findIndex((x) => x.id === "plex"); saveW(); render(); });
      skip.append(info(t("Finish the wizard without a disk and add disks later in Settings → Disks. Downloading works once at least one disk is set up.")), sb);
      box.appendChild(skip);
      autoProbe();
      scheduleCheck();
      return box;
    },
    plex() {
      const box = el("div");
      box.append(h(t("Plex server"), t("Plex Downloader shows the Plex server status in the header. Servers in your home network are found automatically; add a server by hand if it is on another subnet or behind a VPN. Plex does not have to run on this Raspberry Pi.")));
      const found = el("div", "wz-plex"); found.appendChild(p(t("Searching for servers on the network…"), "muted"));
      box.appendChild(found);
      api("/api/plex/discover", {}).then((r) => {
        found.replaceChildren();
        const list = (r.status || []).filter((x) => x.source !== "manual");
        if (!list.length) found.appendChild(el("p", "plan-warn", W.type === "network"
          ? t("No Plex server found automatically. Add the computer that runs Plex below (its IP address).")
          : t("No Plex server found. You can continue – add the server later in Settings → Plex servers.")));
        list.forEach((x) => {
          const row = el("div", "wz-srv");
          row.append(el("span", "dot" + (x.online ? "" : " bad")), el("b", null, x.name), el("span", "mono muted", `${x.display_host}:${x.port}`));
          found.appendChild(row);
        });
      }).catch(() => found.replaceChildren(el("p", "plan-warn", t("No Plex server found. You can continue – add the server later in Settings → Plex servers."))));
      const auto = el("label", "check");
      const acb = el("input"); acb.type = "checkbox"; acb.checked = W.plexAuto;
      acb.addEventListener("change", () => { W.plexAuto = acb.checked; saveW(); });
      auto.append(acb, document.createTextNode(" " + t("Automatically discover Plex servers on the network")));
      box.appendChild(auto);
      box.appendChild(el("h3", null, t("Added manually")));
      const list = el("div", "wz-manual");
      const draw = () => {
        list.replaceChildren();
        W.servers.forEach((s, i) => {
          const row = el("div", "wz-row");
          const n = el("input", "input"); n.placeholder = t("Name, e.g. Living room"); n.value = s.name || "";
          const ho = el("input", "input mono"); ho.placeholder = t("IP address, e.g. 192.168.1.20"); ho.value = s.host || "";
          const po = el("input", "input mono port"); po.value = s.port || 32400; po.inputMode = "numeric";
          n.addEventListener("input", () => { s.name = n.value; saveW(); });
          ho.addEventListener("input", () => { s.host = ho.value.trim(); saveW(); });
          po.addEventListener("input", () => { s.port = parseInt(po.value, 10) || 32400; saveW(); });
          const x = el("button", "icon-btn"); x.type = "button"; x.title = t("Remove"); x.appendChild(icon("trash"));
          x.addEventListener("click", () => { W.servers.splice(i, 1); saveW(); draw(); });
          row.append(n, ho, po, x); list.appendChild(row);
        });
      };
      draw();
      const add = el("button", "btn-soft small", "+ " + t("Add server")); add.type = "button";
      add.addEventListener("click", () => { W.servers.push({ name: "", host: "", port: 32400 }); saveW(); draw(); });
      box.append(list, add);
      return box;
    },
    tmdb() {
      const box = el("div");
      box.append(h(t("TMDB key (optional)"), t("Free key from themoviedb.org → Settings → API. Used for the movie preview card and posters in the File manager. Stored only locally.")));
      box.appendChild(p(t("With a key you get the preview card (poster, rating, plot) and posters in the File manager. Without it everything else works normally – you can add it later in Settings → Preview & posters.")));
      const a = el("a", "linklike", t("Get a free key at themoviedb.org") + " ↗"); a.href = "https://www.themoviedb.org/settings/api"; a.target = "_blank"; a.rel = "noopener";
      box.appendChild(el("p")).appendChild(a);
      const inp = el("input", "input mono"); inp.type = "password"; inp.autocomplete = "new-password"; inp.spellcheck = false;
      inp.placeholder = S.tmdb_key_set ? t("Saved key: {mask}", { mask: S.tmdb_key_mask }) : t("paste the key from themoviedb.org");
      inp.value = W.tmdbKey || "";
      inp.addEventListener("input", () => { W.tmdbKey = inp.value.trim(); saveW(); updateNext(); });
      const show = el("label", "check"); const scb = el("input"); scb.type = "checkbox";
      scb.addEventListener("change", async () => {
        // „Show key”: the saved key is fetched only now (it is not sent to the browser before)
        if (scb.checked && !inp.value && S.tmdb_key_set) {
          try { inp.value = (await api("/api/settings/tmdb-key")).key || ""; } catch (e) { toast(e.message, true); }
        }
        inp.type = scb.checked ? "text" : "password";
      });
      show.append(scb, document.createTextNode(" " + t("Show key")));
      const st = el("span", "key-st");
      const check = window.PD.tmdbChecker(inp, st);
      box.append(inp, st, show);
      if (inp.value) check(false); else if (S.tmdb_key_set) check(true);   // the saved key is checked too
      // posters from video frames (ffmpeg) – for home videos and when there is no TMDB key / no match
      const fr = el("div", "wz-frames");
      const fl = el("label", "check"); const fcb = el("input"); fcb.type = "checkbox";
      fcb.checked = W.opts && "thumbs_frames" in W.opts ? !!W.opts.thumbs_frames : !!S.thumbs_frames;
      fcb.addEventListener("change", () => { W.opts = W.opts || {}; W.opts.thumbs_frames = fcb.checked; saveW(); });
      fl.append(fcb, document.createTextNode(" " + t("Generate posters myself from video frames (needs ffmpeg)")));
      fr.append(fl, info(t("For home videos and titles without a TMDB match (or without a TMDB key) the File manager makes a poster from a frame of the video: several frames are checked and the clearest one is used. Needs ffmpeg – installed by setup.sh, or with fix.sh → Additional modules.\n\nNot recommended to switch on right away: it takes about 10–15 s per movie on a Pi 4 / Pi 400 (longer on a Pi Zero), so the first opening of a large category is slow.\n\nYou can always make a poster from a frame for a single movie: File manager → pen icon (Edit) → Frame from the video.")));
      if (!S.ffmpeg) fr.appendChild(el("p", "muted small", t("ffmpeg is not installed yet – add it with fix.sh → Additional modules.")));
      box.appendChild(fr);
      return box;
    },
    summary() {
      const box = el("div");
      box.append(h(t("Summary")), p(t("Check the settings and click Finish. Everything can be changed later in Settings.")));
      const dl = el("dl", "wz-sum");
      const add = (k, v) => { dl.append(el("dt", null, k), el("dd", null, v)); };
      add(t("Language"), LANG === "pl" ? "Polski" : "English");
      add(t("Theme"), (document.documentElement.dataset.theme || "dark") === "light" ? t("Light") : t("Dark"));
      add(t("Installation"), { disks: t("External disks"), sd: t("Library on the SD card"), network: t("Plex on another device") }[W.type]);
      if (W.imported) add(t("Settings file"), `${W.imported.name} · ${t("categories, Plex servers and options from the file")}`);
      box.appendChild(dl);
      const disks = chosenDisks();
      if (W.skipDisks) box.appendChild(el("p", "plan-warn", S.wizard_done
        ? t("Disks: skipped – your current disks stay unchanged.")
        : t("Disks: skipped – add them later in Settings → Disks. Downloading needs at least one disk.")));
      else if (!disks.length) box.appendChild(el("p", "plan-warn", t("No disk selected – go back to “Disks and folders”.")));
      disks.forEach((d) => {
        const card = el("div", "wz-disk on");
        card.appendChild(el("div", "wz-disk-head")).append(el("b", null, d.label || d.mount), el("span", "muted mono", d.mount));
        const ul = el("ul", "plan-list");
        cats().forEach((c) => {
          const path = d.paths[c.id];
          if (!path) return;
          const li = el("li");
          const [cls, msg] = statusText(status[path]);
          li.append(el("span", null, `${c.label}: `), el("span", "mono", path), el("span", "wz-st " + cls, msg));
          ul.appendChild(li);
        });
        card.appendChild(ul); box.appendChild(card);
      });
      const srv = W.servers.filter((s) => s.host).map((s) => `${s.name || s.host} (${s.host}:${s.port || 32400})`);
      const dl2 = el("dl", "wz-sum");
      dl2.append(el("dt", null, t("Plex server")), el("dd", null, [W.plexAuto ? t("automatic discovery") : "", ...srv].filter(Boolean).join(" · ") || "—"));
      dl2.append(el("dt", null, t("TMDB key")), el("dd", null, W.tmdbKey ? t("new key entered") : S.tmdb_key_set ? t("saved key kept") : t("none (can be added later)")));
      const frames = W.opts && "thumbs_frames" in W.opts ? W.opts.thumbs_frames : S.thumbs_frames;
      dl2.append(el("dt", null, t("Posters from video frames")), el("dd", null, frames ? t("yes") : t("no")));
      box.appendChild(dl2);
      scheduleCheck();
      return box;
    },
  };

  // ------------------------------------------------------------------ validation + finish
  function canLeave(stepId) {
    if (stepId !== "disks") return true;
    W.skipDisks = false;   // „Next” on the disks step = use the selected disks
    const disks = chosenDisks();
    if (!disks.length) { toast(t("Select at least one disk."), true); return false; }
    if (disks.some((d) => !Object.values(d.paths).some(Boolean))) { toast(t("Every selected disk needs at least one category folder."), true); return false; }
    const dup = disks.find((d) => { const v = Object.values(d.paths).filter(Boolean); return new Set(v).size !== v.length; });
    if (dup) { toast(t("Two categories use the same folder on {disk}.", { disk: dup.mount }), true); return false; }
    const bad = allPaths().map((x) => status[x]).filter((x) => x && x.problem && (x.exists || x.problem !== t("Folder does not exist")));
    if (bad.length) { toast(bad[0].path + ": " + (bad[0].problem || ""), true); return false; }
    if (!W.create && allPaths().some((x) => status[x] && !status[x].exists)) { toast(t("Some folders do not exist – create them or tick “Create missing folders”."), true); return false; }
    return true;
  }
  async function finish(btn) {
    btn.disabled = true;
    try {
      const disks = chosenDisks();
      if (W.create) {
        const missing = allPaths().filter((x) => !status[x] || !status[x].exists);
        if (missing.length) {
          const r = await api("/api/wizard/create", { paths: missing });
          if (r.problems.length) { toast(r.problems[0], true); btn.disabled = false; return; }
        }
      }
      await api("/api/wizard/finish", {
        disks: disks.map((d) => ({ label: d.label || baseName(d.mount), subtitle: "", mount: d.mount, paths: d.paths })),
        categories: W.cats || undefined, options: W.opts || undefined,
        plex_servers: W.servers.filter((s) => s.host), plex_autodiscover: W.plexAuto,
        tmdb_api_key: W.tmdbKey ? W.tmdbKey : null, require_mount: true, skip_disks: !!W.skipDisks,
      });
      ss.set("plexdl.wizard", "");
      toast(t("Setup finished."));
      setTimeout(() => { location.href = "/"; }, 600);
    } catch (e) { toast(e.message, true); btn.disabled = false; }
  }

  // ------------------------------------------------------------------ render
  function render() {
    const step = STEPS[W.step];
    const ol = $("#wzSteps"); ol.replaceChildren();
    STEPS.forEach((s, i) => {
      const li = el("li", (i === W.step ? "on" : "") + (i < W.step ? " done" : ""));
      li.append(el("span", "n", i < W.step ? "✓" : String(i + 1)), el("span", "l", s.label()));
      if (i < W.step) li.addEventListener("click", () => { W.step = i; saveW(); render(); });
      ol.appendChild(li);
    });
    $("#wzBody").replaceChildren(VIEWS[step.id]());
    $("#wzBack").hidden = W.step === 0;
    const next = $("#wzNext");
    updateNext();
    next.hidden = step.id === "language";
    const g = $("#wzGuide"); g.href = GUIDE[LANG] || GUIDE.en; g.textContent = t("Installation guide") + " ↗";
    window.scrollTo({ top: 0 });
  }
  // „Skip” only when there is no key at all (nothing saved, nothing typed)
  function updateNext() {
    const step = STEPS[W.step];
    $("#wzNext").textContent = step.id === "summary" ? t("Finish")
      : step.id === "tmdb" && !W.tmdbKey && !S.tmdb_key_set ? t("Skip") : t("Next");
  }
  $("#wzBack").addEventListener("click", () => { if (W.step > 0) { W.step--; saveW(); render(); } });
  $("#wzNext").addEventListener("click", (e) => {
    const step = STEPS[W.step];
    if (step.id === "summary") { finish(e.currentTarget); return; }
    if (!canLeave(step.id)) return;
    W.step = Math.min(STEPS.length - 1, W.step + 1); saveW(); render();
  });

  async function init() {
    try { S = await api("/api/wizard/state"); } catch (e) { toast(e.message, true); return; }
    try { W = JSON.parse(ss.get("plexdl.wizard") || "null"); } catch (e) { W = null; }
    if (!W || typeof W.step !== "number") W = freshW();
    if (S.wizard_done) { $("#wzRedo").hidden = false; $("#wzExit").hidden = false; }
    render();
  }
  init();
})();
