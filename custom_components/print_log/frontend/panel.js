/* Print Log panel - vanilla web component, no external dependencies. */
const CSS = `
:host{display:block;height:100%;overflow:auto;background:var(--primary-background-color);color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,Roboto,sans-serif)}
*{box-sizing:border-box}
.wrap{max-width:1200px;margin:0 auto;padding:16px}
h1{font-size:22px;margin:0 0 12px;font-weight:500}
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:end;margin-bottom:12px}
.card{background:var(--card-background-color,#fff);border-radius:12px;padding:12px 16px;box-shadow:var(--ha-card-box-shadow,0 1px 3px rgba(0,0,0,.2));margin-bottom:12px}
label{display:flex;flex-direction:column;font-size:12px;color:var(--secondary-text-color);gap:2px}
input,select,textarea{font:inherit;padding:6px 8px;border-radius:6px;border:1px solid var(--divider-color,#ccc);background:var(--primary-background-color);color:inherit;min-width:110px}
button{font:inherit;padding:7px 14px;border-radius:8px;border:0;cursor:pointer;background:var(--primary-color);color:var(--text-primary-color,#fff)}
button.sec{background:transparent;color:var(--primary-color);border:1px solid var(--primary-color)}
button.danger{background:var(--error-color,#c00)}
button.tiny{padding:3px 8px;font-size:12px}
.tabs{display:flex;gap:4px;margin-bottom:12px;border-bottom:1px solid var(--divider-color)}
.tab{padding:8px 14px;cursor:pointer;border-bottom:3px solid transparent;color:var(--secondary-text-color)}
.tab.on{border-color:var(--primary-color);color:var(--primary-text-color);font-weight:500}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--divider-color)}
th{cursor:pointer;font-weight:500;color:var(--secondary-text-color);white-space:nowrap}
td.n,th.n{text-align:right}
.tot{display:flex;gap:24px;flex-wrap:wrap}.tot b{font-size:20px;display:block}
.badge{font-size:11px;padding:1px 6px;border-radius:8px;background:var(--warning-color,#fa0);color:#000}
.st-cancelled,.st-error{color:var(--error-color,#c00)}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:10}
.modal form{background:var(--card-background-color,#fff);padding:20px;border-radius:12px;min-width:320px;max-width:95vw;display:grid;gap:10px}
.modal .row{display:flex;gap:8px;justify-content:flex-end}
.err{color:var(--error-color,#c00);font-size:13px}
.muted{color:var(--secondary-text-color)}
svg text{fill:var(--primary-text-color);font-size:11px}
.pager{display:flex;gap:8px;align-items:center;justify-content:flex-end;margin-top:8px}
`;

const ENTITY_SPECS = {
  people: {title: "Mensen", fields: [
    {k: "name", label: "Naam", type: "text", req: true},
    {k: "default_role_id", label: "Standaardrol", type: "select", from: "roles", empty: "(geen)"}]},
  roles: {title: "Rollen (personen)", fields: [{k: "name", label: "Naam", type: "text", req: true}]},
  filaments: {title: "Filamentrollen", fields: [
    {k: "name", label: "Naam", type: "text", req: true},
    {k: "material", label: "Materiaal", type: "text"},
    {k: "price_per_m", label: "Prijs per meter (EUR)", type: "number", step: "0.0001", req: true}]},
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const eur = (v) => new Intl.NumberFormat("nl-BE", {style: "currency", currency: "EUR", minimumFractionDigits: 2, maximumFractionDigits: 3}).format(v || 0);
const dur = (s) => (s == null ? "" : `${Math.floor(s / 3600)}u ${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}m`);
const dt = (iso) => (iso ? new Date(iso).toLocaleString("nl-BE", {dateStyle: "short", timeStyle: "short"}) : "");
const localInput = (iso) => { if (!iso) return ""; const d = new Date(iso); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); };
const fromLocalInput = (v) => (v ? new Date(v).toISOString().replace(/\.\d+Z$/, "Z") : null);
const STATUS = {complete: "gelukt", cancelled: "geannuleerd", error: "fout"};

class PrintLogPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({mode: "open"});
    this.tab = "prints"; this.filters = {}; this.sort = "ended_at"; this.order = "desc"; this.page = 0; this.size = 25;
    this.lists = {people: [], roles: [], filaments: []}; this.settings = {}; this.group = "person";
  }
  set hass(h) { const first = !this._hass; this._hass = h; if (first) this.init(); }
  set narrow(_) {} set panel(_) {} set route(_) {}
  get admin() { return !!this._hass?.user?.is_admin; }

  async api(method, path, body) {
    try { return await this._hass.callApi(method, "print_log/" + path, body); }
    catch (e) { throw new Error(e?.body?.error || e?.error || e?.message || "Fout"); }
  }
  qs(extra = {}) {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries({...this.filters, ...extra})) if (v !== "" && v != null) p.set(k, v);
    return p.toString();
  }
  async init() {
    this.shadowRoot.innerHTML = `<style>${CSS}</style><div class="wrap" id="root"></div><div id="modal"></div>`;
    await this.loadLists();
    await this.render();
  }
  async loadLists() {
    const [people, roles, filaments, settings] = await Promise.all([
      this.api("GET", "people"), this.api("GET", "roles"), this.api("GET", "filaments"), this.api("GET", "settings")]);
    this.lists = {people, roles, filaments}; this.settings = settings;
  }
  opts(list, sel, {empty = "", archived = false} = {}) {
    const items = this.lists[list].filter((x) => archived || !x.archived || x.id == sel);
    return (empty !== null ? `<option value="">${esc(empty)}</option>` : "") +
      items.map((x) => `<option value="${x.id}" ${x.id == sel ? "selected" : ""}>${esc(x.name)}${x.archived ? " (archief)" : ""}</option>`).join("");
  }
  async render() {
    const root = this.shadowRoot.getElementById("root");
    const tabs = [["prints", "Prints"], ["stats", "Statistieken"], ["people", "Mensen"], ["filaments", "Filamenten"], ["roles", "Rollen"], ["settings", "Instellingen"]];
    root.innerHTML = `<h1>Print log</h1>${this.currentBar()}
      <div class="tabs">${tabs.map(([k, l]) => `<div class="tab ${k === this.tab ? "on" : ""}" data-tab="${k}">${l}</div>`).join("")}</div>
      <div id="content"></div>`;
    root.querySelectorAll(".tab").forEach((t) => (t.onclick = () => { this.tab = t.dataset.tab; this.page = 0; this.render(); }));
    this.bindCurrent();
    const c = root.querySelector("#content");
    try {
      if (this.tab === "prints") await this.viewPrints(c);
      else if (this.tab === "stats") await this.viewStats(c);
      else if (this.tab === "settings") this.viewSettings(c);
      else await this.viewEntity(c, this.tab);
    } catch (e) { c.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
  }

  currentBar() {
    const s = this.settings, dis = this.admin ? "" : "disabled";
    return `<div class="card bar"><b>Volgende print:</b>
      <label>Persoon<select id="cur_person" ${dis}>${this.opts("people", s.current_person_id, {empty: "(kies)"})}</select></label>
      <label>Rol<select id="cur_role" ${dis}>${this.opts("roles", s.current_role_id, {empty: "(standaard van persoon)"})}</select></label>
      <label>Filament<select id="cur_filament" ${dis}>${this.opts("filaments", s.current_filament_id, {empty: "(kies)"})}</select></label>
      <span class="muted">Wordt gebruikt voor de eerstvolgende gelogde prints.</span></div>`;
  }
  bindCurrent() {
    for (const k of ["person", "role", "filament"]) {
      const el = this.shadowRoot.getElementById("cur_" + k);
      el.onchange = async () => {
        try { this.settings = await this.api("PUT", "settings", {["current_" + k + "_id"]: el.value || null}); }
        catch (e) { alert(e.message); }
      };
    }
  }

  async viewPrints(c) {
    const f = this.filters;
    const res = await this.api("GET", `prints?${this.qs({limit: this.size, offset: this.page * this.size, sort: this.sort, order: this.order})}`);
    const pages = Math.max(1, Math.ceil(res.total / this.size));
    const th = (k, l, n) => `<th class="${n ? "n" : ""}" data-sort="${k}">${l}${this.sort === k ? (this.order === "asc" ? " ▲" : " ▼") : ""}</th>`;
    c.innerHTML = `<div class="card bar" id="filters">
      <label>Persoon<select name="person"><option value="">Alle</option><option value="none" ${f.person === "none" ? "selected" : ""}>(onbekend)</option>${this.opts("people", f.person, {empty: null, archived: true})}</select></label>
      <label>Rol<select name="role"><option value="">Alle</option>${this.opts("roles", f.role, {empty: null, archived: true})}</select></label>
      <label>Filament<select name="filament"><option value="">Alle</option>${this.opts("filaments", f.filament, {empty: null, archived: true})}</select></label>
      <label>Status<select name="status"><option value="">Alle</option>${Object.entries(STATUS).map(([k, v]) => `<option value="${k}" ${f.status === k ? "selected" : ""}>${v}</option>`).join("")}</select></label>
      <label>Van<input type="date" name="from" value="${esc(f.from)}"></label>
      <label>Tot<input type="date" name="to" value="${esc(f.to)}"></label>
      <label>Min. duur (min)<input type="number" name="min_duration" min="0" value="${esc(f.min_duration)}" style="width:90px"></label>
      <label>Max. duur (min)<input type="number" name="max_duration" min="0" value="${esc(f.max_duration)}" style="width:90px"></label>
      <label>Zoek<input type="search" name="q" value="${esc(f.q)}"></label>
      <button class="sec" id="reset">Reset</button></div>
      <div class="card tot"><div><span class="muted">Prints</span><b>${res.total}</b></div>
        <div><span class="muted">Totale kost</span><b>${eur(res.total_cost)}</b></div>
        <div><span class="muted">Filament</span><b>${res.total_length_m.toFixed(1)} m</b></div>
        <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
          <button class="sec" id="csv">CSV export</button>${this.admin ? '<button id="add">+ Print toevoegen</button>' : ""}</div></div>
      <div class="card" style="overflow:auto"><table><thead><tr>
        ${th("ended_at", "Einde")}${th("filename", "Bestand")}${th("person", "Persoon")}${th("role", "Rol")}${th("filament", "Filament")}
        ${th("duration_s", "Duur", 1)}${th("length_m", "Meter", 1)}${th("total_cost", "Kost", 1)}${th("status", "Status")}<th></th></tr></thead><tbody>
        ${res.items.map((p) => `<tr><td>${dt(p.ended_at)}</td><td>${esc(p.filename) || '<span class="muted">-</span>'}</td>
          <td>${esc(p.person) || '<span class="badge">kies</span>'}</td><td>${esc(p.role)}</td>
          <td>${esc(p.filament) || '<span class="badge">kies</span>'}</td><td class="n">${dur(p.duration_s)}</td>
          <td class="n">${p.length_m.toFixed(2)}</td><td class="n">${eur(p.total_cost)}</td>
          <td class="st-${p.status}">${STATUS[p.status] || p.status}</td>
          <td>${this.admin ? `<button class="tiny sec" data-edit="${p.id}">✎</button> <button class="tiny danger" data-del="${p.id}">✕</button>` : ""}</td></tr>`).join("") ||
          '<tr><td colspan="10" class="muted">Geen prints gevonden.</td></tr>'}
        </tbody></table>
        <div class="pager"><button class="sec tiny" id="prev" ${this.page <= 0 ? "disabled" : ""}>←</button>
          <span>${this.page + 1} / ${pages}</span><button class="sec tiny" id="next" ${this.page + 1 >= pages ? "disabled" : ""}>→</button></div></div>`;
    c.querySelectorAll("#filters select,#filters input").forEach((el) => (el.onchange = () => { this.filters[el.name] = el.value; this.page = 0; this.render(); }));
    c.querySelector("#reset").onclick = () => { this.filters = {}; this.page = 0; this.render(); };
    c.querySelectorAll("th[data-sort]").forEach((el) => (el.onclick = () => {
      const k = el.dataset.sort; this.order = this.sort === k && this.order === "desc" ? "asc" : "desc"; this.sort = k; this.render(); }));
    c.querySelector("#prev").onclick = () => { this.page--; this.render(); };
    c.querySelector("#next").onclick = () => { this.page++; this.render(); };
    c.querySelector("#csv").onclick = () => this.exportCsv();
    c.querySelector("#add")?.addEventListener("click", () => this.printForm(null));
    c.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => this.printForm(res.items.find((p) => p.id == b.dataset.edit))));
    c.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
      if (!confirm("Deze print verwijderen?")) return;
      try { await this.api("DELETE", "prints/" + b.dataset.del); this.render(); } catch (e) { alert(e.message); }
    }));
  }
  async exportCsv() {
    const r = await this._hass.fetchWithAuth(`/api/print_log/export.csv?${this.qs()}`);
    const url = URL.createObjectURL(await r.blob());
    const a = document.createElement("a"); a.href = url; a.download = "print_log.csv"; a.click(); URL.revokeObjectURL(url);
  }

  modal(html, onSubmit) {
    const m = this.shadowRoot.getElementById("modal");
    m.innerHTML = `<div class="modal"><form>${html}<div class="err" id="err"></div>
      <div class="row"><button type="button" class="sec" id="cancel">Annuleer</button><button type="submit">Opslaan</button></div></form></div>`;
    m.querySelector("#cancel").onclick = () => (m.innerHTML = "");
    m.querySelector("form").onsubmit = async (e) => {
      e.preventDefault();
      try { await onSubmit(Object.fromEntries(new FormData(e.target).entries())); m.innerHTML = ""; await this.loadLists(); this.render(); }
      catch (err) { m.querySelector("#err").textContent = err.message; }
    };
  }
  printForm(p) {
    const n = p || {status: "complete", length_m: 0, ended_at: new Date().toISOString(), person_id: this.settings.current_person_id,
      role_id: this.settings.current_role_id, filament_id: this.settings.current_filament_id};
    this.modal(`<h3>${p ? "Print bewerken" : "Print toevoegen"}</h3>
      <label>Bestandsnaam<input name="filename" value="${esc(n.filename)}"></label>
      <label>Persoon<select name="person_id">${this.opts("people", n.person_id, {empty: "(onbekend)"})}</select></label>
      <label>Rol<select name="role_id">${this.opts("roles", n.role_id, {empty: "(standaard van persoon)"})}</select></label>
      <label>Filament<select name="filament_id">${this.opts("filaments", n.filament_id, {empty: "(onbekend)"})}</select></label>
      <label>Lengte (m)<input name="length_m" type="number" step="0.001" min="0" value="${n.length_m}" required></label>
      ${p && p.length_auto_m != null && p.length_auto_m !== p.length_m ? `<span class="muted">Automatisch geteld: ${p.length_auto_m} m</span>` : ""}
      <label>Status<select name="status">${Object.entries(STATUS).map(([k, v]) => `<option value="${k}" ${n.status === k ? "selected" : ""}>${v}</option>`).join("")}</select></label>
      <label>Start<input name="started_at" type="datetime-local" value="${localInput(n.started_at)}"></label>
      <label>Einde<input name="ended_at" type="datetime-local" value="${localInput(n.ended_at)}"></label>
      <label>Notities<textarea name="notes" rows="2">${esc(n.notes)}</textarea></label>
      ${p ? `<span class="muted">Huidige kost: ${eur(p.total_cost)} (${p.price_per_m} EUR/m). Bij wijzigen van filament, persoon of lengte wordt herberekend.</span>` : ""}`,
      async (d) => {
        const body = {filename: d.filename, person_id: d.person_id || null, role_id: d.role_id || null, filament_id: d.filament_id || null,
          length_m: parseFloat(d.length_m), status: d.status, started_at: fromLocalInput(d.started_at), ended_at: fromLocalInput(d.ended_at), notes: d.notes || null};
        if (p) await this.api("PUT", "prints/" + p.id, body); else await this.api("POST", "prints", body);
      });
  }

  async viewEntity(c, table) {
    const spec = ENTITY_SPECS[table], rows = this.lists[table];
    const cols = spec.fields.map((f) => f.label).concat(["Prints", ""]);
    const cell = (r, f) => f.type === "select" ? esc(this.lists[f.from].find((x) => x.id == r[f.k])?.name || "") : esc(r[f.k]);
    c.innerHTML = `<div class="card"><div class="bar"><b>${spec.title}</b>${this.admin ? '<button id="add" style="margin-left:auto">+ Nieuw</button>' : ""}</div>
      <table><thead><tr>${cols.map((x) => `<th>${x}</th>`).join("")}</tr></thead><tbody>
      ${rows.map((r) => `<tr class="${r.archived ? "muted" : ""}">${spec.fields.map((f) => `<td>${cell(r, f)}${f.k === "name" && r.archived ? " (archief)" : ""}</td>`).join("")}
        <td>${r.print_count}</td><td>${this.admin ? `<button class="tiny sec" data-edit="${r.id}">✎</button> <button class="tiny danger" data-del="${r.id}">✕</button>` : ""}</td></tr>`).join("")}
      </tbody></table></div>`;
    c.querySelector("#add")?.addEventListener("click", () => this.entityForm(table, null));
    c.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => this.entityForm(table, rows.find((r) => r.id == b.dataset.edit))));
    c.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
      if (!confirm("Verwijderen? Als er prints aan hangen wordt het gearchiveerd.")) return;
      try { const r = await this.api("DELETE", `${table}/${b.dataset.del}`); if (r.result === "archived") alert("Gearchiveerd (er hangen nog prints aan)."); await this.loadLists(); this.render(); }
      catch (e) { alert(e.message); }
    }));
  }
  entityForm(table, item) {
    const spec = ENTITY_SPECS[table], n = item || {};
    const input = (f) => f.type === "select"
      ? `<select name="${f.k}">${this.opts(f.from, n[f.k], {empty: f.empty})}</select>`
      : `<input name="${f.k}" type="${f.type}" ${f.step ? `step="${f.step}"` : ""} value="${esc(n[f.k])}" ${f.req ? "required" : ""}>`;
    this.modal(`<h3>${item ? "Bewerken" : "Nieuw"}: ${spec.title}</h3>${spec.fields.map((f) => `<label>${f.label}${input(f)}</label>`).join("")}
      ${item ? `<label style="flex-direction:row;gap:6px;align-items:center"><input type="checkbox" name="archived" ${n.archived ? "checked" : ""} style="min-width:0"> Gearchiveerd</label>` : ""}`,
      async (d) => {
        const body = {};
        for (const f of spec.fields) body[f.k] = f.type === "number" ? parseFloat(d[f.k]) : f.type === "select" ? (d[f.k] || null) : d[f.k];
        if (item) body.archived = d.archived === "on";
        if (item) await this.api("PUT", `${table}/${item.id}`, body); else await this.api("POST", table, body);
      });
  }

  async viewStats(c) {
    const rows = await this.api("GET", `stats?${this.qs({group_by: this.group})}`);
    const groups = {person: "Per persoon", role: "Per rol", filament: "Per filament", month: "Per maand", status: "Per status"};
    c.innerHTML = `<div class="card bar">${Object.entries(groups).map(([k, l]) => `<button class="${k === this.group ? "" : "sec"}" data-g="${k}">${l}</button>`).join("")}
      <span class="muted">De filters van het tabblad Prints gelden hier ook.</span></div>
      <div class="card"><b>Kost (EUR)</b>${this.bars(rows, "total_cost", (v) => eur(v))}</div>
      <div class="card"><b>Filament (m)</b>${this.bars(rows, "length_m", (v) => v.toFixed(1) + " m")}</div>
      <div class="card" style="overflow:auto"><table><thead><tr><th>${groups[this.group]}</th><th class="n">Prints</th><th class="n">Meter</th><th class="n">Duur</th><th class="n">Kost</th></tr></thead><tbody>
      ${rows.map((r) => `<tr><td>${esc(r.key)}</td><td class="n">${r.prints}</td><td class="n">${r.length_m.toFixed(1)}</td><td class="n">${dur(r.duration_s)}</td><td class="n">${eur(r.total_cost)}</td></tr>`).join("")}
      </tbody></table></div>`;
    c.querySelectorAll("[data-g]").forEach((b) => (b.onclick = () => { this.group = b.dataset.g; this.render(); }));
  }
  bars(rows, key, fmt) {
    if (!rows.length) return '<div class="muted">Geen data.</div>';
    const max = Math.max(...rows.map((r) => r[key]), 1e-9), h = 26, lw = 130, w = 700;
    return `<svg viewBox="0 0 ${w + 120} ${rows.length * h + 6}" width="100%">${rows.map((r, i) => {
      const bw = Math.max(1, (r[key] / max) * w * 0.8);
      return `<text x="0" y="${i * h + 17}">${esc(String(r.key).slice(0, 20))}</text>
        <rect x="${lw}" y="${i * h + 4}" width="${bw}" height="${h - 8}" rx="3" fill="var(--primary-color)"/>
        <text x="${lw + bw + 6}" y="${i * h + 17}">${esc(fmt(r[key]))}</text>`;
    }).join("")}</svg>`;
  }

  viewSettings(c) {
    const s = this.settings;
    c.innerHTML = `<div class="card"><h3>Instellingen</h3>
      <label>Kost bij mislukte of geannuleerde print (% van het filament)<input id="failed" type="number" min="0" max="100" value="${s.failed_cost_pct ?? 100}" ${this.admin ? "" : "disabled"}></label>
      <p class="muted">Stroomprijs en percentages per rol komen in een volgende versie. De kolommen bestaan al in de database.</p>
      ${this.admin ? '<button id="save">Opslaan</button>' : ""}</div>`;
    c.querySelector("#save")?.addEventListener("click", async () => {
      try { this.settings = await this.api("PUT", "settings", {failed_cost_pct: parseFloat(c.querySelector("#failed").value)}); alert("Opgeslagen. Geldt voor nieuwe en bewerkte prints."); }
      catch (e) { alert(e.message); }
    });
  }
}
customElements.define("print-log-panel", PrintLogPanel);
