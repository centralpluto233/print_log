/* Settlements tab: pick a person, filter their open prints, tick the prints to settle now. */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

export async function renderSettlements(p, c) {
  const t = p.t, S = p.settle, sign = (v) => (v > 0 ? "+" : "") + p.moneyP(v);
  const people = p.lists.people.filter((x) => !x.archived || x.id == S.person);
  let open = [];
  if (S.person) {
    const q = new URLSearchParams({person: S.person, paid: "no", limit: "1000", sort: "ended_at", order: "asc"});
    for (const k of ["from", "to", "filament", "q"]) if (S[k]) q.set(k, S[k]);
    open = (await p.api("GET", `prints?${q}`)).items.filter((x) => !x.settlement_id);
  }
  const ids = new Set(open.map((x) => x.id));
  S.sel = S.sel ? new Set([...S.sel].filter((i) => ids.has(i))) : new Set(ids);
  const hist = await p.api("GET", `settlements${S.person ? `?person=${S.person}` : ""}`);
  const totals = () => {
    let m = 0, pr = 0, n = 0;
    for (const x of open) if (S.sel.has(x.id)) { m += Math.round(x.price * 1e6); pr += Math.round(x.profit * 1e6); n++; }
    return {n, calc: m / 1e6, profit: pr / 1e6, sug: {cent: Math.ceil(m / 1e4) / 100, "50c": Math.ceil(m / 5e5) / 2, euro: Math.ceil(m / 1e6)}};
  };
  const T0 = totals();
  const fil = (v) => `<option value="">${t("all")}</option>${p.opts("filaments", v, {empty: null, archived: true})}`;
  c.innerHTML = `<div class="card bar"><label>${t("person")}<select id="s_person"><option value="">${t("choose")}</option>${people.map((x) => `<option value="${x.id}" ${x.id == S.person ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select></label>
      <label>${t("period")}<input type="month" id="s_month" value="${esc(S.period)}"></label>
      <label>${t("from")}<input type="date" id="s_from" value="${esc(S.from)}"></label><label>${t("to")}<input type="date" id="s_to" value="${esc(S.to)}"></label>
      <label>${t("filament")}<select id="s_fil">${fil(S.filament)}</select></label>
      <label>${t("search")}<input type="search" id="s_q" value="${esc(S.q)}"></label></div>
    ${!S.person ? `<div class="card muted">${t("pick_person")}</div>` : !open.length ? `<div class="card muted">${t("settle_none")}</div>` : `<div class="card">
      <div class="tot"><div><span class="muted">${t("selected")}</span><b><span id="s_n">${T0.n}</span> / ${open.length}</b></div>
        <div><span class="muted">${t("calculated")}</span><b id="s_calc">${p.moneyP(T0.calc)}</b></div><div><span class="muted">${t("profit")}</span><b id="s_profit">${p.moneyP(T0.profit)}</b></div></div>
      ${p.admin ? `<div class="bar" style="margin-top:10px"><button class="sec" data-r="cent">${t("round_cent")}</button><button class="sec" data-r="50c">${t("round_50")}</button><button class="sec" data-r="euro">${t("round_euro")}</button>
        <label>${t("final_amount")}<input type="number" step="0.01" min="0" id="s_final"></label><span>${t("difference")}: <b id="s_diff"></b></span>
        <label>${t("notes")}<input id="s_note"></label><button id="s_go">${t("settle_btn")}</button></div>` : ""}
      <div class="bar" style="margin-top:10px"><button class="sec tiny" id="s_all">${t("sel_all")}</button><button class="sec tiny" id="s_none">${t("sel_none")}</button></div>
      <table style="margin-top:6px"><thead><tr><th><input type="checkbox" id="s_head" ${T0.n === open.length ? "checked" : ""}></th><th>${t("end")}</th><th>${t("file")}</th><th>${t("filament")}</th><th class="n">${t("meters")}</th><th class="n">${t("price")}</th></tr></thead><tbody>
      ${open.map((x) => `<tr><td><input type="checkbox" data-s="${x.id}" ${S.sel.has(x.id) ? "checked" : ""}></td><td>${p.dt(x.ended_at)}</td><td>${esc(x.filename)}</td><td>${esc(x.filament)}</td><td class="n">${x.length_m.toFixed(2)}</td><td class="n">${p.moneyP(x.price)}</td></tr>`).join("")}</tbody></table></div>`}
    <div class="card" style="overflow:auto"><h3>${t("history")}</h3>${hist.length ? `<table><thead><tr><th>${t("date")}</th><th>${t("person")}</th><th>${t("period").split(" (")[0]}</th><th class="n">${t("t_prints")}</th><th class="n">${t("calculated")}</th><th class="n">${t("final_amount")}</th><th class="n">${t("difference")}</th><th>${t("notes")}</th><th></th></tr></thead><tbody>
      ${hist.map((h) => `<tr><td>${p.dt(h.created_at)}</td><td>${esc(h.person)}</td><td>${esc(h.period || t("period_all"))}</td><td class="n">${h.prints_count}</td><td class="n">${p.moneyP(h.calculated)}</td><td class="n">${p.moneyP(h.final)}</td><td class="n">${sign(h.diff)}</td><td>${esc(h.note)}</td><td style="white-space:nowrap"><button class="tiny sec" data-exp="${h.id}" data-fmt="html">${t("export_pdf")}</button> <button class="tiny sec" data-exp="${h.id}" data-fmt="csv">${t("export_csv")}</button> ${p.admin ? `<button class="tiny sec" data-undo="${h.id}">${t("undo")}</button>` : ""}</td></tr>`).join("")}</tbody></table>` : `<span class="muted">${t("no_settlements")}</span>`}</div>`;

  const reset = () => { S.sel = null; S.final = null; p.render(); };
  c.querySelector("#s_person").onchange = (e) => { S.person = e.target.value; reset(); };
  c.querySelector("#s_month").onchange = (e) => {
    const v = e.target.value; S.period = v;
    if (v) { const [y, m] = v.split("-").map(Number); S.from = `${v}-01`; S.to = `${v}-${String(new Date(y, m, 0).getDate()).padStart(2, "0")}`; } else { S.from = ""; S.to = ""; }
    reset();
  };
  for (const [id, k] of [["#s_from", "from"], ["#s_to", "to"]]) c.querySelector(id).onchange = (e) => { S[k] = e.target.value; S.period = ""; reset(); };
  c.querySelector("#s_fil").onchange = (e) => { S.filament = e.target.value; reset(); };
  c.querySelector("#s_q").onchange = (e) => { S.q = e.target.value; reset(); };

  const fin = c.querySelector("#s_final"), diff = c.querySelector("#s_diff");
  const updDiff = () => { if (fin && diff) diff.textContent = sign((parseFloat(fin.value) || 0) - totals().calc); };
  const refresh = () => {
    const T = totals();
    c.querySelector("#s_n").textContent = T.n; c.querySelector("#s_calc").textContent = p.moneyP(T.calc); c.querySelector("#s_profit").textContent = p.moneyP(T.profit);
    if (fin) { fin.value = (S.final ?? T.sug.cent).toFixed(2); updDiff(); }
  };
  const boxes = [...c.querySelectorAll("input[data-s]")];
  const setSel = (set) => { S.sel = set; S.final = null; boxes.forEach((b) => (b.checked = set.has(parseInt(b.dataset.s)))); const h = c.querySelector("#s_head"); if (h) h.checked = set.size === open.length; refresh(); };
  boxes.forEach((b) => (b.onchange = () => { const id = parseInt(b.dataset.s); b.checked ? S.sel.add(id) : S.sel.delete(id); S.final = null; const h = c.querySelector("#s_head"); if (h) h.checked = S.sel.size === open.length; refresh(); }));
  const head = c.querySelector("#s_head");
  if (head) head.onchange = () => setSel(head.checked ? new Set(ids) : new Set());
  const bAll = c.querySelector("#s_all"), bNone = c.querySelector("#s_none");
  if (bAll) { bAll.onclick = () => setSel(new Set(ids)); bNone.onclick = () => setSel(new Set()); }
  if (S.person && open.length) refresh();
  if (fin) {
    fin.oninput = () => { S.final = parseFloat(fin.value); if (isNaN(S.final)) S.final = null; updDiff(); };
    c.querySelectorAll("[data-r]").forEach((b) => (b.onclick = () => { S.final = totals().sug[b.dataset.r]; fin.value = S.final.toFixed(2); updDiff(); }));
    c.querySelector("#s_go").onclick = async () => {
      const final = parseFloat(fin.value);
      if (!S.sel.size) { alert(t("settle_pick")); return; }
      if (isNaN(final) || final < 0) { alert(t("final_amount")); return; }
      try {
        await p.api("POST", "settlements", {person_id: parseInt(S.person), print_ids: [...S.sel], final, note: c.querySelector("#s_note").value, period: S.period || null});
        S.sel = null; S.final = null; alert(t("settle_done")); p.render();
      } catch (e) { alert(e.message); }
    };
  }
  c.querySelectorAll("[data-exp]").forEach((b) => (b.onclick = () => p.exportSettlement(p, b.dataset.exp, b.dataset.fmt)));
  c.querySelectorAll("[data-undo]").forEach((b) => (b.onclick = async () => {
    if (!confirm(t("undo_confirm"))) return;
    try { await p.api("DELETE", "settlements/" + b.dataset.undo); p.render(); } catch (e) { alert(e.message); }
  }));
}
