/* Plex Downloader – Menedżer plików: dwie kolumny, okładki, przeciąganie, przenoszenie, usuwanie */
(() => {
  "use strict";
  const { $, $$, store, t, api, fmtSize, fmtSpeed, fmtEta, el, icon, catIcon, modal, toast } = window.PD;
  const PAGE = 24;
  const DT = "application/x-plexdl";
  let disks = [], categories = [];
  const panes = {};

  // ------------------------------------------------------------------ kolumna
  class Pane {
    constructor(root) {
      this.root = root;
      this.id = root.dataset.pane;
      root.appendChild($("#paneTpl").content.cloneNode(true));
      const saved = (() => { try { return JSON.parse(store.get("plexdl.fm." + this.id) || "{}"); } catch (e) { return {}; } })();
      this.disk = saved.disk || null;
      this.cat = saved.cat || null;
      this.items = []; this.data = null; this.page = 0; this.query = ""; this.sel = new Set();
      this.grid = $(".fm-grid", root);
      $(".fm-search input", root).addEventListener("input", (e) => { this.query = e.target.value.trim().toLowerCase(); this.page = 0; this.render(); });
      $(".fm-all input", root).addEventListener("change", (e) => {
        this.pageItems().filter((i) => !i.busy).forEach((i) => (e.target.checked ? this.sel.add(i.name) : this.sel.delete(i.name)));
        this.render();
      });
      $(".fm-move", root).addEventListener("click", () => moveItems(this, this.other(), [...this.sel]));
      $(".fm-del", root).addEventListener("click", () => deleteItems(this, [...this.sel]));
      this.grid.addEventListener("dragover", (e) => {
        if (!e.dataTransfer.types.includes(DT) || dragFrom === this) return;
        e.preventDefault(); e.dataTransfer.dropEffect = "move"; this.root.classList.add("drop");
      });
      this.grid.addEventListener("dragleave", (e) => { if (!this.grid.contains(e.relatedTarget)) this.root.classList.remove("drop"); });
      this.grid.addEventListener("drop", (e) => {
        this.root.classList.remove("drop");
        let d; try { d = JSON.parse(e.dataTransfer.getData(DT)); } catch (err) { return; }
        e.preventDefault();
        if (document.activeElement) document.activeElement.blur();
        if (d.from === this.id) return;
        moveItems(panes[d.from], this, d.names);
      });
    }
    other() { return panes[this.id === "left" ? "right" : "left"]; }
    save() { store.set("plexdl.fm." + this.id, JSON.stringify({ disk: this.disk, cat: this.cat })); }
    diskObj() { return disks.find((d) => d.id === this.disk); }
    catObj() { return categories.find((c) => c.id === this.cat); }
    label() { const d = this.diskObj(), c = this.catObj(); return d && c ? `${d.label} / ${c.label}` : "—"; }

    pickDefaults(i) {
      const ok = (d) => d.ok && Object.keys(d.paths || {}).length;
      if (!disks.some((d) => d.id === this.disk && ok(d))) {
        const avail = disks.filter(ok);
        this.disk = (avail[i] || avail[0] || disks[0] || {}).id || null;
      }
      const d = this.diskObj();
      if (d && !(d.paths || {})[this.cat]) {
        const c = categories.find((x) => (d.paths || {})[x.id]);
        this.cat = c ? c.id : null;
      }
    }

    renderHead() {
      const box = $(".fm-disks", this.root);
      box.replaceChildren();
      disks.forEach((d) => {
        const can = d.ok && Object.keys(d.paths || {}).length;
        const b = el("button", "disk mini" + (d.id === this.disk ? " on" : ""));
        b.type = "button"; b.disabled = !can;
        const ico = el("div", "ico"); ico.appendChild(icon("drive"));
        b.append(ico, el("div", "name", d.label));
        if (d.ok && d.total) {
          const bar = el("div", "bar" + (d.free / d.total < 0.05 ? " low" : ""));
          const f = el("i"); f.style.width = Math.max(2, (d.total - d.free) / d.total * 100).toFixed(1) + "%";
          bar.appendChild(f);
          b.append(bar, el("div", "free", t("Free: {free}", { free: fmtSize(d.free) })));
        } else b.append(el("div", "problem", d.problem || t("Unavailable")));
        b.addEventListener("click", () => { this.disk = d.id; this.pickDefaults(0); this.save(); this.reload(); });
        box.appendChild(b);
      });
      const cats = $(".fm-cats", this.root);
      cats.replaceChildren();
      const d = this.diskObj();
      categories.forEach((c) => {
        const has = d && (d.paths || {})[c.id];
        const b = el("button", c.id === this.cat ? "on" : "");
        b.type = "button"; b.disabled = !has;
        b.title = has ? d.paths[c.id] : t("No folder for this category on the selected disk (Settings → Disks)");
        b.append(icon(catIcon(c)), document.createTextNode(c.label));
        b.addEventListener("click", () => { this.cat = c.id; this.save(); this.reload(); });
        cats.appendChild(b);
      });
      const mv = $(".fm-move", this.root);
      mv.replaceChildren();
      if (this.id === "left") mv.append(document.createTextNode(t("Move")), icon("arrow-r"));
      else mv.append(icon("arrow-l"), document.createTextNode(t("Move")));
      mv.title = t("Move selected to: {dst}", { dst: this.other().label() });
    }

    async reload() {
      this.renderHead();
      this.sel.clear(); this.page = 0;
      if (!this.disk || !this.cat) {
        this.items = []; this.data = null;
        this.showMsg(t("Choose a disk and category. If a folder is missing, add it in Settings → Disks."));
        return;
      }
      this.showMsg(t("Loading…"), true);
      try {
        this.data = await api(`/api/fm/list?disk=${encodeURIComponent(this.disk)}&cat=${encodeURIComponent(this.cat)}`);
        this.items = this.data.items;
        $(".fm-path", this.root).textContent = this.data.path;
        this.render();
      } catch (e) {
        this.items = []; this.data = null;
        $(".fm-path", this.root).textContent = "";
        this.showMsg(e.message, false, true);
      }
    }
    showMsg(text, loading, bad) {
      this.grid.replaceChildren(el("div", "fm-msg" + (loading ? " loading" : "") + (bad ? " bad" : ""), text));
      $(".fm-pager", this.root).replaceChildren();
      $(".fm-selbar", this.root).hidden = true;
    }
    filtered() {
      if (!this.query) return this.items;
      return this.items.filter((i) => (i.title + " " + (i.year || "") + " " + i.name).toLowerCase().includes(this.query));
    }
    pageItems() { const f = this.filtered(); return f.slice(this.page * PAGE, (this.page + 1) * PAGE); }

    render() {
      const list = this.filtered();
      const pages = Math.max(1, Math.ceil(list.length / PAGE));
      this.page = Math.min(this.page, pages - 1);
      const items = this.pageItems();
      const hint = el("div", "fm-drop-hint", t("Drop to move to: {dst}", { dst: this.label() }));
      if (!list.length) {
        this.grid.replaceChildren(hint, el("div", "fm-msg", this.query ? t("No search results.") : t("This folder is empty.")));
      } else {
        this.grid.replaceChildren(hint, ...items.map((i) => this.card(i)));
      }
      const pager = $(".fm-pager", this.root);
      pager.replaceChildren();
      if (pages > 1) {
        const prev = el("button", "icon-btn"); prev.type = "button"; prev.appendChild(icon("chev-l")); prev.disabled = this.page === 0;
        const next = el("button", "icon-btn"); next.type = "button"; next.appendChild(icon("chev-r")); next.disabled = this.page >= pages - 1;
        prev.addEventListener("click", () => { this.page--; this.render(); this.grid.scrollIntoView({ block: "nearest" }); });
        next.addEventListener("click", () => { this.page++; this.render(); this.grid.scrollIntoView({ block: "nearest" }); });
        pager.append(prev, el("span", null, `${this.page + 1} / ${pages}`), next);
      }
      pager.appendChild(el("span", "muted", `${pages > 1 ? "· " : ""}${t("{n} items", { n: list.length })} · ${fmtSize(list.reduce((a, i) => a + i.size, 0))}`));
      this.updateSel();
    }
    updateSel() {
      for (const n of [...this.sel]) if (!this.items.some((i) => i.name === n)) this.sel.delete(n);
      const bar = $(".fm-selbar", this.root);
      bar.hidden = !this.sel.size;
      const size = this.items.filter((i) => this.sel.has(i.name)).reduce((a, i) => a + i.size, 0);
      $(".fm-selinfo", this.root).textContent = t("Selected: {n} · {size}", { n: this.sel.size, size: fmtSize(size) });
      const pi = this.pageItems().filter((i) => !i.busy);
      $(".fm-all input", this.root).checked = pi.length > 0 && pi.every((i) => this.sel.has(i.name));
      $$(".fm-card", this.grid).forEach((c) => c.classList.toggle("sel", this.sel.has(c.dataset.name)));
    }

    card(i) {
      const c = el("div", "fm-card" + (i.busy ? " busy" : "") + (this.sel.has(i.name) ? " sel" : ""));
      c.dataset.name = i.name;
      c.draggable = !i.busy;
      const poster = el("div", "poster");
      const mode = this.data ? this.data.thumbs_mode : "off";
      const ph = () => {
        const p = el("div", "ph-poster");
        p.append(icon(catIcon(this.catObj())), el("span", null, i.title));
        return p;
      };
      if (mode !== "off" && (i.thumb || (mode === "online" && this.data.tmdb))) {
        const img = document.createElement("img");
        img.loading = "lazy"; img.alt = i.title; img.draggable = false;
        img.src = `/api/fm/thumb?disk=${encodeURIComponent(this.disk)}&cat=${encodeURIComponent(this.cat)}&name=${encodeURIComponent(i.name)}&v=${i.thumb_v}`;
        img.addEventListener("error", () => img.replaceWith(ph()));
        poster.appendChild(img);
      } else poster.appendChild(ph());
      const chk = el("label", "sel-box"); chk.title = t("Select");
      const cb = el("input"); cb.type = "checkbox"; cb.checked = this.sel.has(i.name); cb.disabled = i.busy;
      cb.addEventListener("change", () => { cb.checked ? this.sel.add(i.name) : this.sel.delete(i.name); this.updateSel(); });
      chk.append(cb, icon("check"));
      poster.appendChild(chk);
      if (i.edition) poster.appendChild(el("span", "ed-badge", i.edition));
      if (!i.is_dir) poster.appendChild(el("span", "loose-badge", t("file")));
      if (i.extras) {
        const x = el("span", "extras-badge"); x.appendChild(icon("extras"));
        x.title = t("The folder contains extras that will be moved too");
        poster.appendChild(x);
      }
      if (i.busy) poster.appendChild(el("span", "busy-badge", t("downloading…")));
      const meta = el("div", "meta");
      const tt = el("div", "t", i.title); tt.title = i.name;
      const kind = this.data ? this.data.kind : "movie";
      const extra = kind === "tv" ? (i.videos ? t("{n} ep.", { n: i.videos }) : "") : "";
      const y = el("div", "y", [i.year, fmtSize(i.size), extra].filter(Boolean).join(" · "));
      const del = el("button", "del"); del.type = "button"; del.title = t("Delete"); del.appendChild(icon("trash"));
      del.disabled = i.busy;
      del.addEventListener("click", (e) => { e.stopPropagation(); deleteItems(this, [i.name]); });
      const txt = el("div", "txt"); txt.append(tt, y);
      meta.append(txt, del);
      c.append(poster, meta);
      poster.addEventListener("click", (e) => {
        if (e.target.closest(".sel-box") || i.busy) return;
        this.sel.has(i.name) ? this.sel.delete(i.name) : this.sel.add(i.name);
        this.updateSel();
      });
      c.addEventListener("dragstart", (e) => {
        if (!this.sel.has(i.name)) { this.sel.clear(); this.sel.add(i.name); this.updateSel(); }
        dragFrom = this;
        const names = [...this.sel];
        e.dataTransfer.setData(DT, JSON.stringify({ from: this.id, names }));
        e.dataTransfer.effectAllowed = "move";
        const g = el("div", "drag-ghost", names.length > 1 ? t("{n} items", { n: names.length }) : i.title);
        document.body.appendChild(g);
        e.dataTransfer.setDragImage(g, 20, 20);
        setTimeout(() => g.remove(), 0);
      });
      c.addEventListener("dragend", () => { dragFrom = null; $$(".fm-pane").forEach((p) => p.classList.remove("drop")); });
      return c;
    }
  }
  let dragFrom = null;

  // ------------------------------------------------------------------ przenoszenie
  function planBody(plan, extraTop) {
    const body = el("div", "plan");
    if (extraTop) body.appendChild(extraTop);
    const route = el("div", "plan-route");
    route.append(el("div", "plan-loc", plan.src.disk_label + " / " + plan.src.category_label), icon("arrow-r"),
      el("div", "plan-loc", plan.dst.disk_label + " / " + plan.dst.category_label));
    body.appendChild(route);
    const how = el("p", "plan-how");
    if (plan.same_fs) how.append(el("b", null, t("Same disk:") + " "), t("instant move (location change, no copying)."));
    else how.append(el("b", null, t("Other disk:") + " "), t("copy → SHA-256 verification → the original is removed only after a correct copy. Large files may take a few minutes."));
    body.appendChild(how);
    const ul = el("ul", "plan-list");
    plan.items.forEach((it) => {
      const li = el("li", it.problem ? "bad" : "");
      li.append(el("span", null, (plan.show ? plan.show + "/" : "") + it.name), el("span", "muted", fmtSize(it.size)));
      if (it.problem) li.appendChild(el("span", "plan-prob", it.problem));
      ul.appendChild(li);
    });
    body.appendChild(ul);
    const sum = el("div", "plan-sum");
    sum.append(el("span", null, t("Total: {n} items · {size}", { n: plan.items.length, size: fmtSize(plan.total) })));
    if (!plan.same_fs && plan.dst.free != null) sum.append(el("span", "muted", t("Free on the target after the operation: {size}", { size: fmtSize(plan.dst.free - plan.total) })));
    body.appendChild(sum);
    plan.problems.filter((p) => !plan.items.some((it) => p.startsWith(it.name + ":"))).forEach((p) => body.appendChild(el("p", "bad", p)));
    if (!plan.ok) body.appendChild(el("p", "plan-warn", t("Fix the problems (e.g. deselect items that already exist at the destination) to continue.")));
    return body;
  }

  // „Pomiń weryfikację SHA-256” – tylko przy przenoszeniu na inny dysk, domyślnie odznaczone
  function skipVerifyBox() {
    const row = el("div", "skip-verify");
    const lab = el("label", "check");
    const cb = el("input"); cb.type = "checkbox";
    lab.append(cb, document.createTextNode(" " + t("Skip SHA-256 verification after moving")));
    const tip = el("button", "info-i", "i"); tip.type = "button";
    tip.dataset.tip = t("About twice as fast: the copy is not read a second time to compare checksums. Only the file sizes are compared before the original is deleted, so a damaged copy may go unnoticed. Recommended only for files you can download again.");
    row.append(lab, tip);
    row.cb = cb;
    return row;
  }

  async function moveItems(src, dst, names) {
    if (!names.length) return;
    if (!dst.disk || !dst.cat) { toast(t("Choose a disk and category in the other column."), true); return; }
    const isTv = src.data && src.data.kind === "tv";
    if (isTv && names.length === 1) return moveShow(src, dst, names[0]);
    const req = { src_disk: src.disk, src_cat: src.cat, names, dst_disk: dst.disk, dst_cat: dst.cat };
    let plan;
    try { plan = await api("/api/fm/plan", req); }
    catch (e) { await modal({ title: t("Cannot move"), body: e.message, danger: true }); return; }
    const body = planBody(plan);
    const sv = skipVerifyBox();
    if (!plan.same_fs) body.appendChild(sv);
    const ok = await modal({ title: t("Move files?"), body, wide: true,
      buttons: [{ label: t("Cancel"), value: false }, { label: t("Confirm"), value: true, cls: "btn-accent", disabled: !plan.ok }] });
    if (!ok) return;
    if (!plan.same_fs && sv.cb.checked) req.skip_verify = true;
    startMove(src, req);
  }

  // serial: cały / wybrany sezon / wybrane odcinki
  async function moveShow(src, dst, show) {
    let eps;
    try { eps = await api(`/api/fm/episodes?disk=${encodeURIComponent(src.disk)}&cat=${encodeURIComponent(src.cat)}&name=${encodeURIComponent(show)}`); }
    catch (e) { await modal({ title: t("Cannot move"), body: e.message, danger: true }); return; }
    const box = el("div", "plan");
    const modeRow = el("div", "ep-mode");
    const sel = el("select", "input");
    [["all", t("Whole show")], ["season", t("Selected season")], ["episodes", t("Selected episodes")]].forEach(([v, x]) => { const o = el("option", null, x); o.value = v; sel.appendChild(o); });
    const seasonSel = el("select", "input"); seasonSel.hidden = true;
    eps.seasons.forEach((s, i) => { const o = el("option", null, `${s.season} · ${s.episodes.length} · ${fmtSize(s.size)}`); o.value = i; seasonSel.appendChild(o); });
    modeRow.append(el("b", null, show), sel, seasonSel);
    const grid = el("div", "ep-grid"); grid.hidden = true;
    const picked = new Set();
    eps.seasons.forEach((s) => {
      grid.appendChild(el("div", "ep-season", s.season));
      s.episodes.forEach((e) => {
        const b = el("button", "ep"); b.type = "button";
        b.append(el("b", null, e.code || "—"), el("span", null, e.name), el("span", "muted", fmtSize(e.size)));
        b.title = e.rel;
        b.addEventListener("click", () => { picked.has(e.rel) ? picked.delete(e.rel) : picked.add(e.rel); b.classList.toggle("on", picked.has(e.rel)); refresh(); });
        grid.appendChild(b);
      });
    });
    const planBox = el("div");
    const sv = skipVerifyBox(); sv.hidden = true;
    box.append(modeRow, grid, planBox, sv);
    let req = null, planOk = false, seq = 0;
    async function refresh() {
      const mode = sel.value;
      seasonSel.hidden = mode !== "season"; grid.hidden = mode !== "episodes";
      if (mode === "all") req = { src_disk: src.disk, src_cat: src.cat, names: [show], dst_disk: dst.disk, dst_cat: dst.cat };
      else {
        const rels = mode === "season" ? (eps.seasons[+seasonSel.value] || { episodes: [] }).episodes.map((e) => e.rel) : [...picked];
        req = { src_disk: src.disk, src_cat: src.cat, show, rels, dst_disk: dst.disk, dst_cat: dst.cat };
      }
      const my = ++seq;
      planOk = false; setBtn();
      if (req.rels && !req.rels.length) { planBox.replaceChildren(el("p", "hint", t("Select at least one episode."))); return; }
      try {
        const plan = await api("/api/fm/plan", req);
        if (my !== seq) return;
        planBox.replaceChildren(planBody(plan)); planOk = plan.ok; setBtn();
        sv.hidden = plan.same_fs;
      } catch (e) { if (my === seq) planBox.replaceChildren(el("p", "bad", e.message)); }
    }
    let dlgRef = null;
    const setBtn = () => { if (dlgRef) dlgRef._buttons[1].disabled = !planOk; };
    box._onOpen = (d) => { dlgRef = d; refresh(); };
    sel.addEventListener("change", refresh);
    seasonSel.addEventListener("change", refresh);
    const ok = await modal({ title: t("Move TV show?"), body: box, wide: true,
      buttons: [{ label: t("Cancel"), value: false }, { label: t("Confirm"), value: () => (planOk ? true : undefined), cls: "btn-accent", disabled: true }] });
    if (!ok) return;
    if (!sv.hidden && sv.cb.checked) req.skip_verify = true;
    startMove(src, req);
  }

  async function startMove(src, req) {
    try {
      await api("/api/fm/move", req);
      src.sel.clear();
      toast(t("Move started – progress is shown under the header."));
      pollOps(true);
    } catch (e) { toast(e.message, true); }
  }

  // ------------------------------------------------------------------ usuwanie
  async function deleteItems(pane, names) {
    if (!names.length) return;
    const items = pane.items.filter((i) => names.includes(i.name));
    const total = items.reduce((a, i) => a + i.size, 0);
    const body = el("div");
    body.appendChild(el("p", null, names.length === 1
      ? (items[0] && items[0].is_dir ? t("The whole folder will be deleted: video file(s), subtitles and poster.") : t("The video file and its poster will be deleted."))
      : t("{n} items will be deleted together with their folders (video files, subtitles, posters).", { n: names.length })));
    const ul = el("ul", "plan-list");
    items.slice(0, 12).forEach((i) => { const li = el("li"); li.append(el("span", null, i.name), el("span", "muted", fmtSize(i.size))); ul.appendChild(li); });
    if (items.length > 12) ul.appendChild(el("li", "muted", t("… and {n} more", { n: items.length - 12 })));
    body.appendChild(ul);
    body.appendChild(el("p", "plan-warn", t("Total {size} from: {where}. This cannot be undone.", { size: fmtSize(total), where: pane.label() })));
    const ok = await modal({ title: names.length === 1 ? t("Delete “{name}”?", { name: items[0] ? items[0].title : names[0] }) : t("Delete selected?"),
      body, danger: true,
      buttons: [{ label: t("Cancel"), value: false }, { label: t("Delete permanently"), value: true, cls: "btn-accent danger" }] });
    if (!ok) return;
    try {
      const r = await api("/api/fm/delete", { disk: pane.disk, cat: pane.cat, names, confirm: "DELETE" });
      if (r.removed.length) toast(t("Deleted: {n}", { n: r.removed.length }));
      if (r.problems.length) await modal({ title: t("Not everything was deleted"), body: r.problems.join("\n"), danger: true });
      names.forEach((n) => pane.sel.delete(n));
      pane.reload();
      const o = pane.other();
      if (o.disk === pane.disk && o.cat === pane.cat) o.reload();
    } catch (e) { toast(e.message, true); }
  }

  // ------------------------------------------------------------------ operacje w tle
  let opsTimer = null, lastActive = 0;
  const PHASE = { copy: t("Copying"), verify: t("SHA-256 verification"), move: t("Moving"), finish: t("Finishing") };
  async function pollOps(force) {
    clearTimeout(opsTimer);
    let active = 0;
    try {
      const r = await api("/api/fm/ops");
      active = r.ops.filter((o) => o.status === "queued" || o.status === "running").length;
      renderOps(r.ops);
      if (lastActive && active < lastActive) { panes.left.reload(); panes.right.reload(); refreshDisks(); }
      lastActive = active;
    } catch (e) { /* bez znaczenia */ }
    opsTimer = setTimeout(pollOps, active || force ? 1000 : 6000);
  }
  function renderOps(ops) {
    const box = $("#opsList");
    $("#fmOps").hidden = !ops.length;
    box.replaceChildren();
    ops.forEach((o) => {
      const row = el("div", "op " + o.status);
      const head = el("div", "op-head");
      const name = o.type === "move" ? `${o.src_label} → ${o.dst_label}` : o.title;
      head.append(el("b", null, name));
      const st = { queued: t("queued"), running: o.type === "move" ? (PHASE[o.phase] || t("In progress")) : t("Downloading posters"),
        done: t("finished"), error: t("finished with errors"), cancelled: t("cancelled") }[o.status];
      head.append(el("span", "badge " + (o.status === "done" ? "done" : o.status === "error" ? "error" : "downloading"), st));
      if (o.status === "running" || o.status === "queued") {
        const c = el("button", "btn-soft small btn-danger", t("Cancel")); c.type = "button";
        c.addEventListener("click", () => api(`/api/fm/ops/${o.id}/cancel`, {}).then(() => pollOps(true)));
        head.appendChild(c);
      }
      row.appendChild(head);
      const pct = o.total ? Math.min(100, (o.done / o.total) * 100) : (o.status === "done" ? 100 : 0);
      const bar = el("div", "bar"); const f = el("i"); f.style.width = pct.toFixed(1) + "%"; bar.appendChild(f);
      row.appendChild(bar);
      const meta = el("div", "op-meta muted");
      const parts = [t("{a}/{b} items", { a: o.items_done, b: o.items_total })];
      if (o.type === "move" && o.total) {
        const size = o.size || o.total;
        if (o.same_fs) parts.push(t("{a} of {b}", { a: fmtSize(o.done), b: fmtSize(o.total) }));
        else if (o.phase === "verify") parts.push(t("Copied {b}", { b: fmtSize(size) }), t("verifying {a} of {b}", { a: fmtSize(o.verified || 0), b: fmtSize(size) }));
        else if (o.status === "running" || o.status === "queued") parts.push(t("copying {a} of {b}", { a: fmtSize(o.copied || 0), b: fmtSize(size) }) + (o.verify === false ? " · " + t("without verification") : ""));
        else parts.push(fmtSize(size) + (o.verify === false ? " · " + t("without verification") : ""));
      }
      if (o.status === "running" && o.speed) parts.push(fmtSpeed(o.speed), t("remaining: {eta}", { eta: fmtEta(o.eta) }) + (o.verify ? " (" + t("copy + verification") + ")" : ""));
      if (o.current) parts.push(o.current);
      meta.textContent = parts.join(" · ");
      row.appendChild(meta);
      // podsumowanie: co i skąd dokąd przeniesiono
      if (o.type === "move") {
        const done = (o.log || []).filter((l) => l.ok);
        if (done.length && o.status !== "running") {
          const ul = el("ul", "op-done");
          const nv = o.verify === false && !o.same_fs ? " (" + t("without verification") + ")" : "";
          done.slice(0, 8).forEach((l) => ul.appendChild(el("li", null, `${o.show ? o.show + "/" : ""}${l.name}: ${o.src_disk} → ${o.dst_disk}${nv}`)));
          if (done.length > 8) ul.appendChild(el("li", "muted", t("… and {n} more", { n: done.length - 8 })));
          row.appendChild(ul);
        }
      }
      const errs = (o.log || []).filter((l) => !l.ok);
      if (errs.length) {
        const ul = el("ul", "op-errs");
        errs.slice(0, 6).forEach((l) => ul.appendChild(el("li", null, `${l.name}: ${l.error}`)));
        row.appendChild(ul);
      }
      box.appendChild(row);
    });
  }
  $("#opsClear").addEventListener("click", () => api("/api/fm/ops/clear", {}).then(() => pollOps()));

  // ------------------------------------------------------------------ dane
  async function refreshDisks() {
    const s = await api("/api/state");
    disks = s.disks; categories = s.categories;
    Object.values(panes).forEach((p) => p.renderHead());
    return s;
  }
  async function init() {
    $$(".fm-pane").forEach((root) => { panes[root.dataset.pane] = new Pane(root); });
    try { await refreshDisks(); } catch (e) { toast(e.message, true); return; }
    panes.left.pickDefaults(0);
    panes.right.pickDefaults(1);
    if (panes.left.disk === panes.right.disk && panes.left.cat === panes.right.cat) {
      const d = panes.right.diskObj();
      const other = d && categories.find((c) => c.id !== panes.left.cat && c.kind === (panes.left.catObj() || {}).kind && (d.paths || {})[c.id]);
      if (other) panes.right.cat = other.id;
    }
    panes.left.reload(); panes.right.reload();
    pollOps();
  }
  $("#fmReload").addEventListener("click", async () => { await refreshDisks(); panes.left.reload(); panes.right.reload(); });
  $("#thumbOpts").addEventListener("click", () => window.PD.openSettings("preview"));
  document.addEventListener("pd:settings-saved", async () => { await refreshDisks(); panes.left.pickDefaults(0); panes.right.pickDefaults(1); panes.left.reload(); panes.right.reload(); pollOps(); });
  init();
})();
