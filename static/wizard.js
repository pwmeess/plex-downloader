/* Plex Downloader – first-run wizard (language, theme, installation type, disks, Plex, TMDB) */
(() => {
  "use strict";
  const { $, $$, t, LANG, api, fmtSize, el, icon, toast, copyText } = window.PD;
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
      servers: (S.plex_servers || []).map((p) => ({ name: p.name, host: p.host, port: p.port })), tmdbKey: null, create: true };
  }
  const cats = () => S.categories || [];
  const baseName = (p) => (p.replace(/\/+$/, "").split("/").pop() || p);

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
        : { use: false, label: baseName(m.mount), mount: m.mount, paths: {}, scanned: false };
    }
    return W.disks[m.mount];
  }
  function chosenDisks() {
    if (W.type === "sd") return W.sd ? [W.sd] : [];
    if (W.type === "network") return Object.values(W.net).filter((d) => d.use);
    return Object.values(W.disks).filter((d) => d.use);
  }
  function allPaths() { return chosenDisks().flatMap((d) => Object.values(d.paths).filter(Boolean)); }

  async function scanDisk(d, after) {
    try {
      const r = await api("/api/wizard/scan", { mount: d.mount });
      cats().forEach((c) => {
        const x = r.result[c.id] || {};
        if (!d.paths[c.id]) d.paths[c.id] = x.path || `${d.mount.replace(/\/$/, "")}/Plex/${c.folder || c.label}`;
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
    $$(".wz-path").forEach((row) => {
      const inp = $("input", row), m = $(".wz-st", row);
      if (!inp || !m) return;   // disk name row has no status
      const [cls, msg] = statusText(status[inp.value.trim()]);
      m.className = "wz-st " + cls; m.textContent = msg;
    });
  }
  function pathRows(d) {
    const box = el("div", "wz-paths");
    cats().forEach((c) => {
      const row = el("div", "wz-path");
      const lab = el("label", null, c.label);
      const inp = el("input", "input mono"); inp.value = d.paths[c.id] || ""; inp.spellcheck = false;
      inp.placeholder = t("(none – category not available on this disk)");
      inp.addEventListener("input", () => { d.paths[c.id] = inp.value.trim(); saveW(); scheduleCheck(); });
      row.append(lab, inp, el("span", "wz-st"));
      box.appendChild(row);
    });
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
    const nm = el("div", "wz-path");
    const ni = el("input", "input"); ni.value = d.label; ni.maxLength = 40;
    ni.addEventListener("input", () => { d.label = ni.value; saveW(); });
    nm.append(el("label", null, t("Button name")), ni, el("span"));
    body.append(nm, pathRows(d));
    card.appendChild(body);
    cb.addEventListener("change", async () => {
      d.use = cb.checked; card.classList.toggle("on", d.use); body.hidden = !d.use; saveW();
      if (d.use && !d.scanned) await scanDisk(d, () => { body.replaceChildren(nm, pathRows(d)); scheduleCheck(); });
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
    cb.addEventListener("change", () => { W.create = cb.checked; saveW(); paintStatus(); });
    lab.append(cb, document.createTextNode(" " + t("Create missing folders when finishing")));
    return lab;
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
          W.type === "network", (v) => { W.type = v; saveW(); }));
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
        const nm = el("div", "wz-path");
        const ni = el("input", "input"); ni.value = W.sd.label; ni.addEventListener("input", () => { W.sd.label = ni.value; saveW(); });
        nm.append(el("label", null, t("Button name")), ni, el("span"));
        box.append(nm, pathRows(W.sd), createBox());
        box.appendChild(p(t("Share the Plex folder over SMB if you want to copy files from your computer – see the guide."), "muted"));
      } else if (W.type === "network") {
        box.append(h(t("Network share"), t("Plex and Plex Downloader must see the same files: Downloader saves into the network share, Plex reads the same folders on its own computer (the paths there may be different). The share has to be mounted on this Raspberry Pi first – the next step shows the commands. Give both devices a fixed IP address in your router.")));
        const nets = (S.mounts || []).filter((m) => m.network);
        if (nets.length) {
          box.appendChild(p(t("Network shares mounted on this Raspberry Pi:")));
          nets.forEach((m) => {
            const d = W.net[m.mount] || (W.net[m.mount] = { use: false, label: baseName(m.mount), mount: m.mount, paths: {}, scanned: false });
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
          W.net[m] = { use: true, manual: true, label: baseName(m), mount: m, paths: {}, scanned: false };
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
          box.appendChild(p(t("Select the disks for the library:")));
          disks.forEach((m) => box.appendChild(diskCard(diskEntry(m), m)));
          box.appendChild(createBox());
        }
        const again = el("button", "btn-soft small", t("Check again")); again.type = "button";
        again.addEventListener("click", async () => { S = await api("/api/wizard/state"); render(); });
        box.appendChild(el("div", "wz-row")).appendChild(again);
      }
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
      box.append(inp, show);
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
      box.appendChild(dl);
      const disks = chosenDisks();
      if (!disks.length) box.appendChild(el("p", "plan-warn", t("No disk selected – go back to “Disks and folders”.")));
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
      box.appendChild(dl2);
      scheduleCheck();
      return box;
    },
  };

  // ------------------------------------------------------------------ validation + finish
  function canLeave(stepId) {
    if (stepId !== "disks") return true;
    const disks = chosenDisks();
    if (!disks.length) { toast(t("Select at least one disk."), true); return false; }
    if (disks.some((d) => !Object.values(d.paths).some(Boolean))) { toast(t("Every selected disk needs at least one category folder."), true); return false; }
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
        plex_servers: W.servers.filter((s) => s.host), plex_autodiscover: W.plexAuto,
        tmdb_api_key: W.tmdbKey ? W.tmdbKey : null, require_mount: true,
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
