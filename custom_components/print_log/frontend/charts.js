/* Charts for the statistics tab: plain SVG, no dependencies. */
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
export const PALETTE = ["#4c78a8", "#54a24b", "#e45756", "#f58518", "#72b7b2", "#b279a2", "#9d755d", "#bab0ac"];

export function niceMax(v) {
  if (!(v > 0)) return 1;
  const e = Math.pow(10, Math.floor(Math.log10(v))), f = v / e;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * e;
}

/** Clustered columns per key (cost, profit, unpaid). Shows the last 24 keys. */
export function columnChart(p, rows) {
  if (!rows.length) return `<div class="muted">${esc(p.t("no_data"))}</div>`;
  const t = p.t, data = rows.slice(-24);
  const series = [["total_cost", t("cost"), PALETTE[0]], ["profit", t("profit"), PALETTE[1]], ["unpaid", t("unpaid"), PALETTE[3]]];
  const vals = data.flatMap((r) => series.map(([k]) => Number(r[k]) || 0));
  const max = niceMax(Math.max(0, ...vals)), min = Math.min(0, ...vals) < 0 ? -niceMax(-Math.min(...vals)) : 0;
  const L = 64, R = 12, T = 12, B = 52, W = 720, H = 280, pw = W - L - R, ph = H - T - B;
  const y = (v) => T + ((max - v) / (max - min)) * ph;
  const ticks = 4, grid = [];
  for (let i = 0; i <= ticks; i++) {
    const v = min + ((max - min) * i) / ticks;
    grid.push(`<line x1="${L}" x2="${W - R}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}" stroke="var(--divider-color)" stroke-width="${v === 0 ? 1.5 : 0.5}"/>` +
      `<text x="${L - 6}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end">${esc(p.axis ? p.axis(v) : v.toFixed(2))}</text>`);
  }
  const gw = pw / data.length, bw = Math.min(26, (gw * 0.8) / series.length);
  const cols = data.map((r, i) => {
    const x0 = L + i * gw + (gw - bw * series.length) / 2;
    const bars = series.map(([k, label, color], j) => {
      const v = Number(r[k]) || 0, top = y(Math.max(v, 0)), h = Math.max(1, Math.abs(y(v) - y(0)));
      return `<rect x="${(x0 + j * bw).toFixed(1)}" y="${(v >= 0 ? top : y(0)).toFixed(1)}" width="${(bw - 1).toFixed(1)}" height="${h.toFixed(1)}" fill="${color}" rx="2"><title>${esc(r.key)} - ${esc(label)}: ${esc(p.money(v))}</title></rect>`;
    }).join("");
    const label = esc(String(r.key).slice(0, 12));
    const lx = (L + i * gw + gw / 2).toFixed(1);
    return bars + `<text x="${lx}" y="${H - B + 16}" text-anchor="${data.length > 8 ? "end" : "middle"}" ${data.length > 8 ? `transform="rotate(-35 ${lx} ${H - B + 16})"` : ""}>${label}</text>`;
  }).join("");
  const legend = series.map(([, label, color]) => `<span class="lg"><i style="background:${color}"></i>${esc(label)}</span>`).join("");
  return `<div class="legend">${legend}</div><svg viewBox="0 0 ${W} ${H}" width="100%" role="img">${grid.join("")}${cols}</svg>`;
}

/** Donut with the share of a value per key (top 6 plus "other"). */
export function donutChart(p, rows, key = "total_cost") {
  const items = rows.map((r) => ({name: String(r.key), v: Math.max(0, Number(r[key]) || 0)})).filter((x) => x.v > 0).sort((a, b) => b.v - a.v);
  const total = items.reduce((s, x) => s + x.v, 0);
  if (!total) return `<div class="muted">${esc(p.t("no_data"))}</div>`;
  const top = items.slice(0, 6), rest = items.slice(6).reduce((s, x) => s + x.v, 0);
  if (rest > 0) top.push({name: p.t("other"), v: rest});
  const r = 60, C = 2 * Math.PI * r;
  let offset = 0;
  const seg = top.map((x, i) => {
    const len = (x.v / total) * C, el = `<circle r="${r}" cx="80" cy="80" fill="none" stroke="${PALETTE[i % PALETTE.length]}" stroke-width="28" stroke-dasharray="${len.toFixed(2)} ${(C - len).toFixed(2)}" stroke-dashoffset="${(-offset).toFixed(2)}" transform="rotate(-90 80 80)"><title>${esc(x.name)}: ${esc(p.money(x.v))} (${((x.v / total) * 100).toFixed(1)}%)</title></circle>`;
    offset += len;
    return el;
  }).join("");
  const legend = top.map((x, i) => `<div class="lg"><i style="background:${PALETTE[i % PALETTE.length]}"></i>${esc(x.name.slice(0, 22))} <span class="muted">${((x.v / total) * 100).toFixed(0)}%</span></div>`).join("");
  return `<div class="donut"><svg viewBox="0 0 160 160" width="160" height="160" role="img">${seg}<text x="80" y="84" text-anchor="middle" style="font-size:12px">${esc(p.money(total))}</text></svg><div>${legend}</div></div>`;
}
