/* Print Log panel - vanilla web component, no external dependencies. */
import {LANGS, makeT} from "./i18n.js";
import {renderSettlements} from "./settlements.js";

const CSS = `
:host{display:block;height:100%;min-height:100vh;overflow:auto;background:var(--primary-background-color);color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,Roboto,sans-serif);color-scheme:light dark}
:host([data-theme="light"]){--primary-background-color:#f3f5f7;--card-background-color:#fff;--primary-text-color:#1f2328;--secondary-text-color:#59636e;--divider-color:#d0d7de;color-scheme:light}
:host([data-theme="dark"]){--primary-background-color:#111418;--card-background-color:#1c2128;--primary-text-color:#e6edf3;--secondary-text-color:#9aa4af;--divider-color:#30363d;color-scheme:dark}
*{box-sizing:border-box}
.wrap{max-width:1200px;margin:0 auto;padding:16px}
.head{display:flex;gap:8px;align-items:center;margin-bottom:12px}.head h1{font-size:22px;margin:0 auto 0 0;font-weight:500}
.card{background:var(--card-background-color,#fff);border-radius:12px;padding:12px 16px;box-shadow:var(--ha-card-box-shadow,0 1px 3px rgba(0,0,0,.2));margin-bottom:12px}
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:end}
label{display:flex;flex-direction:column;font-size:12px;color:var(--secondary-text-color);gap:2px}
label.chk{flex-direction:row;align-items:center;gap:6px;font-size:14px;color:var(--primary-text-color)}
input,select,textarea{font:inherit;padding:6px 8px;border-radius:6px;border:1px solid var(--divider-color,#ccc);background:var(--primary-background-color);color:var(--primary-text-color);min-width:110px}
input[type=checkbox]{min-width:0}
button{font:inherit;padding:7px 14px;border-radius:8px;border:0;cursor:pointer;background:var(--primary-color);color:var(--text-primary-color,#fff)}
button.sec{background:transparent;color:var(--primary-color);border:1px solid var(--primary-color)}
button.danger{background:var(--error-color,#c00)}button.tiny{padding:3px 8px;font-size:12px}button:disabled{opacity:.4;cursor:default}
.tabs{display:flex;gap:4px;margin-bottom:12px;border-bottom:1px solid var(--divider-color);overflow:auto}
.tab{padding:8px 14px;cursor:pointer;border-bottom:3px solid transparent;color:var(--secondary-text-color);white-space:nowrap}
.tab.on{border-color:var(--primary-color);color:var(--primary-text-color);font-weight:500}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--divider-color)}
th{font-weight:500;color:var(--secondary-text-color);white-space:nowrap}th[data-sort]{cursor:pointer}
td.n,th.n{text-align:right}.tot{display:flex;gap:24px;flex-wrap:wrap}.tot b{font-size:20px;display:block}
.badge{font-size:11px;padding:1px 6px;border-radius:8px;background:var(--warning-color,#fa0);color:#000}
.swatch{display:inline-block;width:12px;height:12px;border-radius:50%;border:1px solid var(--divider-color);vertical-align:middle;margin-right:6px}
.ok{color:var(--success-color,#2e7d32)}
.st-cancelled,.st-error{color:var(--error-color,#c00)}.muted{color:var(--secondary-text-color)}.err{color:var(--error-color,#c00);font-size:13px}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:10;overflow:auto}
.modal form{background:var(--card-background-color,#fff);padding:20px;border-radius:12px;min-width:320px;max-width:95vw;max-height:95vh;overflow:auto;display:grid;gap:10px}
.modal .row,.row{display:flex;gap:8px;justify-content:flex-end}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
svg text{fill:var(--primary-text-color);font-size:11px}.pager{display:flex;gap:8px;align-items:center;justify-content:flex-end;margin-top:8px}
h3{margin:0 0 8px;font-weight:500}
`;
const ENTITY_KEYS = ["state_entity", "filename_entity", "filament_entity", "progress_entity", "remaining_entity", "energy_entity"];
const SM_KEYS = ["printing", "paused", "complete", "cancelled", "error", "idle"];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const dur = (s) => (s == null ? "" : `${Math.floor(s / 3600)}h ${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}m`);
const localInput = (iso) => { if (!iso) return ""; const d = new Date(iso); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); };
const fromLocalInput = (v) => (v ? new Date(v).toISOString().replace(/\.\d+Z$/, "Z") : null);
const safeHex = (v) => (/^#[0-9a-fA-F]{3,8}$/.test(String(v || "").trim()) ? String(v).trim() : "");
const PREF_KEY = "print_log";

class PrintLogPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this.tab = "prints"; this.filters = {}; this.sort = "ended_at"; this.order = "desc"; this.page = 0; this.group = "person";
    this.lists = {people: [], roles: [], filaments: [], printers: []}; this.settings = {};
    this.prefs = {theme: "auto", lang: "auto", size: 25}; this.printerId = null;
    this.settle = {person: "", period: "", from: "", to: "", filament: "", q: "", sel: null, final: null};
    this.t = makeT("en");
  }
  set hass(h) { const first = !this._hass; this._hass = h; if (first) this.init(); }
  set narrow(_) {} set panel(_) {} set route(_) {}
  get admin() { return !!this._hass?.user?.is_admin; }
  get lang() { const l = this.prefs.lang === "auto" ? (this._hass?.language || "en") : this.prefs.lang; return LANGS[l.slice(0, 2)] ? l.slice(0, 2) : "en"; }
  get printers() { return this.lists.printers.filter((p) => !p.archived); }
  get printer() { return this.printers.find((p) => p.id == this.printerId) || this.printers[0]; }

  async api(method, path, body) {
    try { return await this._hass.callApi(method, "print_log/" + path, body); }
    catch (e) { throw new Error(e?.body?.error || e?.error || e?.message || "Error"); }
  }
  qs(extra = {}) {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries({...this.filters, ...extra})) if (v !== "" && v != null) p.set(k, v);
    return p.toString();
  }
  async init() {
    try { const r = await this._hass.callWS({type: "frontend/get_user_data", key: PREF_KEY}); this.prefs = {...this.prefs, ...(r?.value || {})}; } catch (e) { /* older HA */ }
    this.applyPrefs();
    this.shadowRoot.innerHTML = `<style>${CSS}</style><div class="wrap" id="root"></div><div id="modal"></div>`;
    await this.loadLists();
    await this.render();
  }
  applyPrefs() { this.t = makeT(this.lang); this.setAttribute("data-theme", this.prefs.theme === "auto" ? "" : this.prefs.theme); if (!this.prefs.theme || this.prefs.theme === "auto") this.removeAttribute("data-theme"); }
  async savePrefs(patch) {
    this.prefs = {...this.prefs, ...patch}; this.applyPrefs();
    try { await this._hass.callWS({type: "frontend/set_user_data", key: PREF_KEY, value: this.prefs}); } catch (e) { /* ignore */ }
    this.render();
  }
  async loadLists() {
    const [people, roles, filaments, printers, settings] = await Promise.all(
      ["people", "roles", "filaments", "printers", "settings"].map((x) => this.api("GET", x)));
    this.lists = {people, roles, filaments, printers}; this.settings = settings;
  }
  opts(list, sel, {empty = "", archived = false} = {}) {
    const items = this.lists[list].filter((x) => archived || !x.archived || x.id == sel);
    return (empty !== null ? `<option value="">${esc(empty)}</option>` : "") +
      items.map((x) => `<option value="${x.id}" ${x.id == sel ? "selected" : ""}>${esc(x.name)}${x.archived ? " (" + this.t("archived").toLowerCase() + ")" : ""}</option>`).join("");
  }
  stLabel(s) { return this.t("s_" + s) || s; }
  get loc() { return this._hass?.locale?.language || this.lang; }
  money(v) { return new Intl.NumberFormat(this.loc, {style: "currency", currency: "EUR", minimumFractionDigits: 2, maximumFractionDigits: 3}).format(v || 0); }
  moneyP(v) { return new Intl.NumberFormat(this.loc, {style: "currency", currency: "EUR", minimumFractionDigits: 2, maximumFractionDigits: 4}).format(v || 0); }
  dt(iso) { return iso ? new Date(iso).toLocaleString(this.loc, {dateStyle: "short", timeStyle: "short"}) : ""; }
  dday(iso) { return iso ? new Date(iso).toLocaleDateString(this.loc, {dateStyle: "short"}) : ""; }

  async render() {
    const t = this.t, root = this.shadowRoot.getElementById("root");
    const tabs = ["prints", "settlements", "stats", "people", "filaments", "roles", "printers", "settings"];
    root.innerHTML = `<div class="head"><h1>${t("title")}</h1>
      <button class="sec tiny" id="theme" title="${t("theme")}">${{auto: "◐", light: "☀", dark: "☾"}[this.prefs.theme] || "◐"}</button></div>${this.currentBar()}
      <div class="tabs">${tabs.map((k) => `<div class="tab ${k === this.tab ? "on" : ""}" data-tab="${k}">${t("t_" + k)}</div>`).join("")}</div><div id="content"></div>
      <datalist id="ents">${Object.keys(this._hass.states).sort().map((e) => `<option value="${e}">`).join("")}</datalist>`;
    root.querySelector("#theme").onclick = () => this.savePrefs({theme: {auto: "light", light: "dark", dark: "auto"}[this.prefs.theme || "auto"]});
    root.querySelectorAll(".tab").forEach((x) => (x.onclick = () => { this.tab = x.dataset.tab; this.page = 0; this.render(); }));
    this.bindCurrent();
    const c = root.querySelector("#content");
    try {
      if (this.tab === "prints") await this.viewPrints(c);
      else if (this.tab === "settlements") await this.viewSettlements(c);
      else if (this.tab === "stats") await this.viewStats(c);
      else if (this.tab === "settings") this.viewSettings(c);
      else if (this.tab === "printers") this.viewPrinters(c);
      else this.viewEntity(c, this.tab);
    } catch (e) { c.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
  }

  currentBar() {
    const t = this.t, p = this.printer, dis = this.admin && p ? "" : "disabled";
    if (!p) return "";
    return `<div class="card bar"><b>${t("next_print")}:</b>
      ${this.printers.length > 1 ? `<label>${t("printer")}<select id="cur_printer">${this.opts("printers", p.id, {empty: null})}</select></label>` : ""}
      <label>${t("person")}<select id="cur_person" ${dis}>${this.opts("people", p.current_person_id, {empty: t("choose")})}</select></label>
      <label>${t("role")}<select id="cur_role" ${dis}>${this.opts("roles", p.current_role_id, {empty: t("default_of_person")})}</select></label>
      <label>${t("filament")}<select id="cur_filament" ${dis}>${this.opts("filaments", p.current_filament_id, {empty: t("choose")})}</select></label>
      <span class="muted">${t("next_hint")}</span></div>`;
  }
  bindCurrent() {
    const p = this.printer, root = this.shadowRoot;
    root.getElementById("cur_printer")?.addEventListener("change", (e) => { this.printerId = e.target.value; this.render(); });
    for (const k of ["person", "role", "filament"]) {
      const el = root.getElementById("cur_" + k);
      if (el) el.onchange = async () => {
        try { Object.assign(p, await this.api("PUT", `printers/${p.id}`, {["current_" + k + "_id"]: el.value || null})); }
        catch (e) { alert(e.message); }
      };
    }
  }

  async viewPrints(c) {
    const t = this.t, f = this.filters, size = this.prefs.size || 25, multi = this.printers.length > 1;
    const res = await this.api("GET", `prints?${this.qs({limit: size, offset: this.page * size, sort: this.sort, order: this.order})}`);
    const pages = Math.max(1, Math.ceil(res.total / size));
    const th = (k, l, n) => `<th class="${n ? "n" : ""}" data-sort="${k}">${l}${this.sort === k ? (this.order === "asc" ? " ▲" : " ▼") : ""}</th>`;
    const sel = (name, label, inner) => `<label>${label}<select name="${name}"><option value="">${t("all")}</option>${inner}</select></label>`;
    c.innerHTML = `<div class="card bar" id="filters">
      ${sel("person", t("person"), `<option value="none" ${f.person === "none" ? "selected" : ""}>${t("unknown")}</option>${this.opts("people", f.person, {empty: null, archived: true})}`)}
      ${sel("role", t("role"), this.opts("roles", f.role, {empty: null, archived: true}))}
      ${sel("filament", t("filament"), this.opts("filaments", f.filament, {empty: null, archived: true}))}
      ${multi ? sel("printer", t("printer"), this.opts("printers", f.printer, {empty: null, archived: true})) : ""}
      ${sel("status", t("status"), ["complete", "cancelled", "error"].map((k) => `<option value="${k}" ${f.status === k ? "selected" : ""}>${this.stLabel(k)}</option>`).join(""))}
      ${sel("paid", t("paid"), ["yes", "no"].map((k) => `<option value="${k}" ${f.paid === k ? "selected" : ""}>${t(k === "yes" ? "paid" : "unpaid")}</option>`).join(""))}
      <label>${t("from")}<input type="date" name="from" value="${esc(f.from)}"></label><label>${t("to")}<input type="date" name="to" value="${esc(f.to)}"></label>
      <label>${t("min_dur")}<input type="number" name="min_duration" min="0" value="${esc(f.min_duration)}" style="width:90px"></label>
      <label>${t("max_dur")}<input type="number" name="max_duration" min="0" value="${esc(f.max_duration)}" style="width:90px"></label>
      <label>${t("search")}<input type="search" name="q" value="${esc(f.q)}"></label><button class="sec" id="reset">${t("reset")}</button></div>
      <div class="card tot"><div><span class="muted">${t("t_prints")}</span><b>${res.total}</b></div>
        <div><span class="muted">${t("total_cost")}</span><b>${this.money(res.total_cost)}</b></div>
        <div><span class="muted">${t("total_price")}</span><b>${this.money(res.total_price)}</b></div>
        <div><span class="muted">${t("total_profit")}</span><b>${this.money(res.total_profit)}</b></div>
        <div><span class="muted">${t("total_unpaid")}</span><b>${this.money(res.total_unpaid)}</b></div>
        <div><span class="muted">${t("total_filament")}</span><b>${res.total_length_m.toFixed(1)} m</b></div>
        <div><span class="muted">${t("total_energy")}</span><b>${res.total_energy_kwh.toFixed(2)} kWh</b></div>
        <div style="margin-left:auto;display:flex;gap:8px;align-items:center;flex-wrap:wrap"><button class="sec" id="csv">${t("csv")}</button>
          ${this.admin ? `<button class="sec" id="bpaid">${t("mark_paid")}</button><button class="sec" id="bunpaid">${t("mark_unpaid")}</button><button id="add">${t("add_print")}</button>` : ""}</div></div>
      <div class="card" style="overflow:auto"><table><thead><tr>${this.admin ? '<th><input type="checkbox" id="selall"></th>' : ""}${th("ended_at", t("end"))}${th("filename", t("file"))}${th("person", t("person"))}${th("role", t("role"))}
        ${th("filament", t("filament"))}${multi ? th("printer", t("printer")) : ""}${th("duration_s", t("duration"), 1)}${th("length_m", t("meters"), 1)}${th("energy_kwh", t("energy"), 1)}
        ${th("total_cost", t("cost"), 1)}${th("price", t("price"), 1)}${th("profit", t("profit"), 1)}${th("paid_at", t("paid"))}${th("status", t("status"))}<th></th></tr></thead><tbody>
        ${res.items.map((p) => `<tr>${this.admin ? `<td><input type="checkbox" data-sel="${p.id}"></td>` : ""}<td>${this.dt(p.ended_at)}</td><td>${esc(p.filename) || '<span class="muted">-</span>'}</td>
          <td>${esc(p.person) || `<span class="badge">${t("pick")}</span>`}</td><td>${esc(p.role)}</td><td>${esc(p.filament) || `<span class="badge">${t("pick")}</span>`}</td>
          ${multi ? `<td>${esc(p.printer)}</td>` : ""}<td class="n">${dur(p.duration_s)}</td><td class="n">${p.length_m.toFixed(2)}</td>
          <td class="n">${p.energy_kwh == null ? "" : p.energy_kwh.toFixed(2) + " kWh"}</td><td class="n">${this.money(p.total_cost)}</td>
          <td class="n">${this.money(p.price)}${p.sale_price != null ? " ✎" : ""}</td><td class="n">${this.money(p.profit)}</td>
          <td>${p.paid ? `<span class="ok">✓ ${this.dday(p.paid_at)}</span>` : ""}</td>
          <td class="st-${p.status}">${this.stLabel(p.status)}</td>
          <td>${this.admin ? `<button class="tiny sec" data-edit="${p.id}">✎</button> <button class="tiny danger" data-del="${p.id}">✕</button>` : ""}</td></tr>`).join("") ||
          `<tr><td colspan="16" class="muted">${t("no_prints")}</td></tr>`}</tbody></table>
        <div class="pager"><button class="sec tiny" id="prev" ${this.page <= 0 ? "disabled" : ""}>←</button><span>${this.page + 1} / ${pages}</span>
        <button class="sec tiny" id="next" ${this.page + 1 >= pages ? "disabled" : ""}>→</button></div></div>`;
    c.querySelectorAll("#filters select,#filters input").forEach((el) => (el.onchange = () => { this.filters[el.name] = el.value; this.page = 0; this.render(); }));
    c.querySelector("#reset").onclick = () => { this.filters = {}; this.page = 0; this.render(); };
    c.querySelectorAll("th[data-sort]").forEach((el) => (el.onclick = () => { const k = el.dataset.sort; this.order = this.sort === k && this.order === "desc" ? "asc" : "desc"; this.sort = k; this.render(); }));
    c.querySelector("#prev").onclick = () => { this.page--; this.render(); };
    c.querySelector("#next").onclick = () => { this.page++; this.render(); };
    c.querySelector("#csv").onclick = () => this.exportCsv();
    c.querySelector("#add")?.addEventListener("click", () => this.printForm(null));
    c.querySelector("#selall")?.addEventListener("change", (e) => c.querySelectorAll("input[data-sel]").forEach((x) => (x.checked = e.target.checked)));
    const bulk = (paid) => async () => {
      const ids = [...c.querySelectorAll("input[data-sel]:checked")].map((x) => parseInt(x.dataset.sel));
      if (!ids.length) { alert(t("select_none")); return; }
      try { await this.api("POST", "paid", {ids, paid}); this.render(); } catch (e) { alert(e.message); }
    };
    c.querySelector("#bpaid")?.addEventListener("click", bulk(true));
    c.querySelector("#bunpaid")?.addEventListener("click", bulk(false));
    c.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => this.printForm(res.items.find((p) => p.id == b.dataset.edit))));
    c.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
      if (!confirm(t("del_print"))) return;
      try { await this.api("DELETE", "prints/" + b.dataset.del); this.render(); } catch (e) { alert(e.message); }
    }));
  }
  async exportCsv() {
    const r = await this._hass.fetchWithAuth(`/api/print_log/export.csv?${this.qs()}`);
    const url = URL.createObjectURL(await r.blob());
    const a = document.createElement("a"); a.href = url; a.download = "print_log.csv"; a.click(); URL.revokeObjectURL(url);
  }

  modal(html, onSubmit) {
    const t = this.t, m = this.shadowRoot.getElementById("modal");
    m.innerHTML = `<div class="modal"><form>${html}<div class="err" id="err"></div><div class="row"><button type="button" class="sec" id="cancel">${t("cancel")}</button><button type="submit">${t("save")}</button></div></form></div>`;
    m.querySelector("#cancel").onclick = () => (m.innerHTML = "");
    m.querySelector("form").onsubmit = async (e) => {
      e.preventDefault();
      try { await onSubmit(Object.fromEntries(new FormData(e.target).entries())); m.innerHTML = ""; await this.loadLists(); this.render(); }
      catch (err) { m.querySelector("#err").textContent = err.message; }
    };
  }
  printForm(p) {
    const t = this.t, cp = this.printer || {}, locked = !!(p && p.settlement_id);
    const n = p || {status: "complete", length_m: 0, ended_at: new Date().toISOString(), person_id: cp.current_person_id, role_id: cp.current_role_id, filament_id: cp.current_filament_id, printer_id: cp.id};
    this.modal(`<h3>${p ? t("edit_print") : t("new_print")}</h3>
      <label>${t("filename")}<input name="filename" value="${esc(n.filename)}"></label>
      <label>${t("printer")}<select name="printer_id">${this.opts("printers", n.printer_id, {empty: t("unknown")})}</select></label>
      <label>${t("person")}<select name="person_id">${this.opts("people", n.person_id, {empty: t("unknown")})}</select></label>
      <label>${t("role")}<select name="role_id">${this.opts("roles", n.role_id, {empty: t("default_of_person")})}</select></label>
      <label>${t("filament")}<select name="filament_id">${this.opts("filaments", n.filament_id, {empty: t("unknown")})}</select></label>
      <label>${t("length_m")}<input name="length_m" type="number" step="0.001" min="0" value="${n.length_m}" required></label>
      ${p && p.length_auto_m != null && p.length_auto_m !== p.length_m ? `<span class="muted">${t("auto_counted", {n: p.length_auto_m})}</span>` : ""}
      <label>${t("kwh")}<input name="energy_kwh" type="number" step="0.001" min="0" value="${n.energy_kwh ?? ""}"></label>
      <label>${t("sale_price")}<input name="sale_price" type="number" step="0.01" min="0" value="${n.sale_price ?? ""}"></label>
      <label class="chk"><input type="checkbox" name="paid" ${n.paid ? "checked" : ""} ${locked ? "disabled" : ""}> ${t("paid_chk")}</label>
      ${locked ? `<span class="muted">${t("in_settlement")}</span>` : ""}
      <label>${t("status")}<select name="status">${["complete", "cancelled", "error"].map((k) => `<option value="${k}" ${n.status === k ? "selected" : ""}>${this.stLabel(k)}</option>`).join("")}</select></label>
      <label>${t("started")}<input name="started_at" type="datetime-local" value="${localInput(n.started_at)}"></label>
      <label>${t("ended")}<input name="ended_at" type="datetime-local" value="${localInput(n.ended_at)}"></label>
      <label>${t("notes")}<textarea name="notes" rows="2">${esc(n.notes)}</textarea></label>
      ${p ? `<span class="muted">${t("current_cost", {c: this.money(p.total_cost), p: p.price_per_m})}</span>` : ""}`,
      async (d) => {
        const body = {filename: d.filename, printer_id: d.printer_id || null, person_id: d.person_id || null, role_id: d.role_id || null,
          filament_id: d.filament_id || null, length_m: parseFloat(d.length_m), energy_kwh: d.energy_kwh === "" ? null : parseFloat(d.energy_kwh),
          sale_price: d.sale_price ?? "", status: d.status, started_at: fromLocalInput(d.started_at), ended_at: fromLocalInput(d.ended_at), notes: d.notes || null};
        if (!locked) body.paid = d.paid === "on";
        if (p) await this.api("PUT", "prints/" + p.id, body); else await this.api("POST", "prints", body);
      });
  }

  entitySpec(table) {
    const t = this.t, pct = (v) => (v == null ? "" : `${v} %`);
    return {
      people: {title: t("people_t"), fields: [{k: "name", label: t("name"), type: "text", req: true},
        {k: "default_role_id", label: t("default_role"), type: "select", from: "roles", empty: t("none")},
        {k: "modifier_pct", label: t("own_margin"), col: t("margin"), type: "number", step: "0.1", fmt: (r) => pct(r.modifier_pct)}], hint: t("margin_hint")},
      roles: {title: t("roles_t"), fields: [{k: "name", label: t("name"), type: "text", req: true},
        {k: "modifier_pct", label: t("margin"), type: "number", step: "0.1", req: true, fmt: (r) => pct(r.modifier_pct)}], hint: t("margin_hint")},
      filaments: {title: t("filaments_t"), fields: [{k: "name", label: t("name"), type: "text", req: true},
        {k: "material", label: t("kind"), col: t("kind"), type: "text"}, {k: "brand", label: t("brand"), type: "text"},
        {k: "color", label: t("color"), type: "text", fmt: (r) => `${safeHex(r.color_hex) ? `<span class="swatch" style="background:${safeHex(r.color_hex)}"></span>` : ""}${esc(r.color)}`},
        {k: "color_hex", label: t("color_hex"), type: "text", hide: true},
        {k: "price_per_m", label: t("price_m"), type: "number", step: "0.000001", req: true, fmt: (r) => this.moneyP(r.price_per_m)},
        {k: "stock_m", label: t("stock_m"), col: t("remaining"), type: "number", step: "0.1", valueKey: "remaining_m",
          fmt: (r) => (r.remaining_m == null ? "" : `${r.remaining_m} m${r.low_stock ? ` <span class="badge">${t("low_stock")}</span>` : ""}`)}], hint: t("stock_hint")},
    }[table];
  }
  tableCard(title, headers, rowsHtml, addBtn) {
    return `<div class="card" style="overflow:auto"><div class="bar" style="margin-bottom:8px"><b>${title}</b>${addBtn && this.admin ? `<button id="add" style="margin-left:auto">${this.t("new")}</button>` : ""}</div>
      <table><thead><tr>${headers.map((x) => `<th>${x}</th>`).join("")}</tr></thead><tbody>${rowsHtml}</tbody></table></div>`;
  }
  actions(r) { return this.admin ? `<button class="tiny sec" data-edit="${r.id}">✎</button> <button class="tiny danger" data-del="${r.id}">✕</button>` : ""; }
  bindActions(c, table, rows, editFn) {
    c.querySelector("#add")?.addEventListener("click", () => editFn(null));
    c.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => editFn(rows.find((r) => r.id == b.dataset.edit))));
    c.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
      if (!confirm(this.t("del_confirm"))) return;
      try { const r = await this.api("DELETE", `${table}/${b.dataset.del}`); if (r.result === "archived") alert(this.t("archived_msg")); await this.loadLists(); this.render(); }
      catch (e) { alert(e.message); }
    }));
  }
  viewEntity(c, table) {
    const t = this.t, spec = this.entitySpec(table), rows = this.lists[table], shown = spec.fields.filter((f) => !f.hide);
    const cell = (r, f) => f.fmt ? f.fmt(r) : f.type === "select" ? esc(this.lists[f.from].find((x) => x.id == r[f.k])?.name || "") : esc(r[f.k]);
    c.innerHTML = this.tableCard(spec.title, [...shown.map((f) => f.col || f.label), t("prints_n"), ""],
      rows.map((r) => `<tr class="${r.archived ? "muted" : ""}">${shown.map((f) => `<td>${cell(r, f)}${f.k === "name" && r.archived ? " (" + t("archived").toLowerCase() + ")" : ""}</td>`).join("")}<td>${r.print_count}</td><td>${this.actions(r)}</td></tr>`).join(""), true);
    this.bindActions(c, table, rows, (item) => this.entityForm(table, item));
  }
  entityForm(table, item) {
    const t = this.t, spec = this.entitySpec(table), n = item || {};
    const input = (f) => f.type === "select" ? `<select name="${f.k}">${this.opts(f.from, n[f.k], {empty: f.empty})}</select>`
      : `<input name="${f.k}" type="${f.type}" ${f.step ? `step="${f.step}"` : ""} value="${esc(n[f.valueKey || f.k])}" ${f.req ? "required" : ""}>`;
    this.modal(`<h3>${spec.title}</h3>${spec.fields.map((f) => `<label>${f.label}${input(f)}</label>`).join("")}
      ${spec.hint ? `<span class="muted">${spec.hint}</span>` : ""}
      ${item ? `<label class="chk"><input type="checkbox" name="archived" ${n.archived ? "checked" : ""}> ${t("archived")}</label>` : ""}`,
      async (d) => {
        const body = {};
        for (const f of spec.fields) body[f.k] = f.type === "number" ? (d[f.k] === "" ? null : parseFloat(d[f.k])) : f.type === "select" ? (d[f.k] || null) : d[f.k];
        if (item) body.archived = d.archived === "on";
        if (item) await this.api("PUT", `${table}/${item.id}`, body); else await this.api("POST", table, body);
      });
  }

  viewPrinters(c) {
    const t = this.t, rows = this.lists.printers;
    c.innerHTML = this.tableCard(t("printers_t"), [t("name"), t("state_entity"), t("energy"), t("prints_n"), ""],
      rows.map((r) => `<tr class="${r.archived ? "muted" : ""}"><td>${esc(r.name)}${r.archived ? " (" + t("archived").toLowerCase() + ")" : ""}</td><td>${esc(r.state_entity)}</td><td>${esc(r.energy_entity)}</td><td>${r.print_count}</td><td>${this.actions(r)}</td></tr>`).join(""), true);
    this.bindActions(c, "printers", rows, (item) => this.printerForm(item));
  }
  printerForm(item) {
    const t = this.t, n = item || {state_map: {}, length_unit: "mm"};
    const ent = (k) => `<label>${t(k)}<input name="${k}" list="ents" value="${esc(n[k])}" ${k === "state_entity" ? "required" : ""} autocomplete="off"></label>`;
    this.modal(`<h3>${t("printers_t")}</h3><span class="muted">${t("entities_hint")}</span>
      <label>${t("name")}<input name="name" value="${esc(n.name)}" required></label>${ENTITY_KEYS.map(ent).join("")}
      <label>${t("length_unit")}<select name="length_unit">${["mm", "cm", "m"].map((u) => `<option ${n.length_unit === u ? "selected" : ""}>${u}</option>`).join("")}</select></label>
      <b>${t("state_map")}</b><div class="grid">${SM_KEYS.map((k) => `<label>${t("sm_" + k)}<input name="sm_${k}" value="${esc((n.state_map?.[k] || []).join(", "))}"></label>`).join("")}</div>
      ${item ? `<label class="chk"><input type="checkbox" name="archived" ${n.archived ? "checked" : ""}> ${t("archived")}</label>` : ""}`,
      async (d) => {
        const body = {name: d.name, length_unit: d.length_unit, state_map: {}};
        for (const k of ENTITY_KEYS) body[k] = d[k];
        for (const k of SM_KEYS) body.state_map[k] = (d["sm_" + k] || "").split(",").map((x) => x.trim()).filter(Boolean);
        if (item) body.archived = d.archived === "on";
        if (item) await this.api("PUT", `printers/${item.id}`, body); else await this.api("POST", "printers", body);
      });
  }

  viewSettlements(c) { return renderSettlements(this, c); }

  async viewStats(c) {
    const t = this.t, rows = await this.api("GET", `stats?${this.qs({group_by: this.group})}`);
    const groups = ["person", "role", "filament", "printer", "month", "status"];
    c.innerHTML = `<div class="card bar">${groups.map((k) => `<button class="${k === this.group ? "" : "sec"}" data-g="${k}">${t("g_" + k)}</button>`).join("")}<span class="muted">${t("filters_apply")}</span></div>
      <div class="card"><b>${t("chart_cost")}</b>${this.bars(rows, "total_cost", (v) => this.money(v))}</div>
      <div class="card"><b>${t("chart_profit")}</b>${this.bars(rows, "profit", (v) => this.money(v))}</div>
      <div class="card"><b>${t("chart_len")}</b>${this.bars(rows, "length_m", (v) => v.toFixed(1) + " m")}</div>
      <div class="card" style="overflow:auto"><table><thead><tr><th>${t("g_" + this.group)}</th><th class="n">${t("t_prints")}</th><th class="n">${t("meters")}</th><th class="n">${t("duration")}</th><th class="n">${t("energy")}</th><th class="n">${t("cost")}</th><th class="n">${t("profit")}</th><th class="n">${t("unpaid")}</th></tr></thead><tbody>
      ${rows.map((r) => `<tr><td>${esc(r.key)}</td><td class="n">${r.prints}</td><td class="n">${r.length_m.toFixed(1)}</td><td class="n">${dur(r.duration_s)}</td><td class="n">${r.energy_kwh.toFixed(2)} kWh</td><td class="n">${this.money(r.total_cost)}</td><td class="n">${this.money(r.profit)}</td><td class="n">${this.money(r.unpaid)}</td></tr>`).join("")}</tbody></table></div>`;
    c.querySelectorAll("[data-g]").forEach((b) => (b.onclick = () => { this.group = b.dataset.g; this.render(); }));
  }
  bars(rows, key, fmt) {
    if (!rows.length) return `<div class="muted">${this.t("no_data")}</div>`;
    const max = Math.max(...rows.map((r) => Math.abs(r[key])), 1e-9), h = 26, lw = 130, w = 700;
    return `<svg viewBox="0 0 ${w + 140} ${rows.length * h + 6}" width="100%">${rows.map((r, i) => {
      const bw = Math.max(1, (Math.abs(r[key]) / max) * w * 0.8);
      return `<text x="0" y="${i * h + 17}">${esc(String(r.key).slice(0, 20))}</text><rect x="${lw}" y="${i * h + 4}" width="${bw}" height="${h - 8}" rx="3" fill="${r[key] < 0 ? "var(--error-color,#c00)" : "var(--primary-color)"}"/>
        <text x="${lw + bw + 6}" y="${i * h + 17}">${esc(fmt(r[key]))}</text>`; }).join("")}</svg>`;
  }

  notifyServices() { return Object.keys(this._hass.services?.notify || {}).filter((s) => s.startsWith("mobile_app_")).sort(); }
  viewSettings(c) {
    const t = this.t, s = this.settings, n = s.notifications || {}, dis = this.admin ? "" : "disabled";
    const chk = (k, l) => `<label class="chk"><input type="checkbox" name="${k}" ${n[k] ? "checked" : ""} ${dis}> ${t(l)}</label>`;
    const num = (k, l) => `<label>${t(l)}<input type="number" min="0" name="${k}" value="${n[k] ?? 0}" ${dis}></label>`;
    const svcs = this.notifyServices(), targets = (n.targets || []).map((x) => x.replace(/^notify\./, ""));
    const tpl = (k, l) => `<label>${t(l)}<input name="${k}" value="${esc(n[k])}" ${dis}></label>`;
    c.innerHTML = `<div class="card"><h3>${t("my_prefs")}</h3><div class="bar">
        <label>${t("theme")}<select id="p_theme">${["auto", "light", "dark"].map((k) => `<option value="${k}" ${this.prefs.theme === k ? "selected" : ""}>${t("th_" + k)}</option>`).join("")}</select></label>
        <label>${t("language")}<select id="p_lang"><option value="auto" ${this.prefs.lang === "auto" ? "selected" : ""}>${t("lang_auto")}</option>${Object.entries(LANGS).map(([k, v]) => `<option value="${k}" ${this.prefs.lang === k ? "selected" : ""}>${v}</option>`).join("")}</select></label>
        <label>${t("page_size")}<select id="p_size">${[10, 25, 50, 100].map((k) => `<option ${this.prefs.size == k ? "selected" : ""}>${k}</option>`).join("")}</select></label></div></div>
      <form id="sform"><div class="card"><h3>${t("costs")}</h3>${this.admin ? "" : `<div class="muted">${t("admin_only")}</div>`}<div class="grid">
        <label>${t("failed_pct")}<input name="failed_cost_pct" type="number" min="0" max="100" value="${s.failed_cost_pct ?? 100}" ${dis}></label>
        <label>${t("energy_price")}<input name="energy_price" type="number" min="0" step="0.0001" value="${(s.energy_price_micro || 0) / 1e6}" ${dis}></label>
        <label>${t("energy_price_entity")}<input name="energy_price_entity" list="ents" value="${esc(s.energy_price_entity)}" ${dis} autocomplete="off"></label>
        <label>${t("low_stock_m")}<input name="low_stock_m" type="number" min="0" value="${s.low_stock_m ?? 50}" ${dis}></label></div>
        <p class="muted">${t("energy_hint")}</p></div>
      <div class="card"><h3>${t("notif")}</h3><div class="grid">${chk("enabled", "n_enabled")}${chk("progress", "n_progress")}${chk("live_update", "n_live")}
        ${chk("on_complete", "n_complete")}${chk("on_cancelled", "n_cancelled")}${chk("on_error", "n_error")}</div>
        <div class="grid" style="margin-top:8px">${num("min_step_pct", "n_step")}${num("min_interval_s", "n_interval")}${num("clear_after_min", "n_clear")}</div>
        <h4>${t("n_targets")}</h4>${svcs.length ? svcs.map((x) => `<label class="chk"><input type="checkbox" name="target:${x}" ${targets.includes(x) ? "checked" : ""} ${dis}> notify.${x}</label>`).join("") : `<div class="muted">${t("n_no_targets")}</div>`}
        <h4>${t("n_templates")}</h4><div class="grid">${["progress", "complete", "cancelled", "error"].map((k) => tpl(k + "_title", `n_${k}_title`) + tpl(k + "_message", `n_${k}_message`)).join("")}</div>
        <div class="row" style="margin-top:10px"><button type="button" class="sec" id="test">${t("n_test")}</button>${this.admin ? `<button type="submit">${t("save")}</button>` : ""}</div></div></form>`;
    c.querySelector("#p_theme").onchange = (e) => this.savePrefs({theme: e.target.value});
    c.querySelector("#p_lang").onchange = (e) => this.savePrefs({lang: e.target.value});
    c.querySelector("#p_size").onchange = (e) => this.savePrefs({size: parseInt(e.target.value)});
    c.querySelector("#test").onclick = async () => { try { await this._hass.callService("print_log", "test_notification", {}); alert(t("n_test_sent")); } catch (e) { alert(e.message); } };
    c.querySelector("#sform").onsubmit = async (e) => {
      e.preventDefault();
      const f = e.target, v = (k) => f.elements[k];
      const notifications = {targets: svcs.filter((x) => v("target:" + x)?.checked).map((x) => "notify." + x)};
      for (const k of ["enabled", "progress", "live_update", "on_complete", "on_cancelled", "on_error"]) notifications[k] = v(k).checked;
      for (const k of ["min_step_pct", "min_interval_s", "clear_after_min"]) notifications[k] = parseInt(v(k).value || 0);
      for (const k of ["progress", "complete", "cancelled", "error"]) for (const x of ["_title", "_message"]) notifications[k + x] = v(k + x).value;
      try {
        this.settings = await this.api("PUT", "settings", {failed_cost_pct: parseFloat(v("failed_cost_pct").value), energy_price_micro: Math.round(parseFloat(v("energy_price").value || 0) * 1e6),
          energy_price_entity: v("energy_price_entity").value, low_stock_m: parseFloat(v("low_stock_m").value || 0), notifications});
        alert(t("saved"));
      } catch (err) { alert(err.message); }
    };
  }
}
customElements.define("print-log-panel", PrintLogPanel);
