/* Loads the stored print thumbnails with the user's token (the images need a login). */
const cache = new Map();

export async function loadThumbs(p, c) {
  const imgs = [...c.querySelectorAll("img[data-thumb]")];
  await Promise.all(imgs.map(async (img) => {
    const name = img.dataset.thumb;
    if (!cache.has(name)) {
      cache.set(name, p._hass.fetchWithAuth(`/api/print_log/thumbs/${encodeURIComponent(name)}`)
        .then((r) => (r.ok ? r.blob() : null)).then((b) => (b ? URL.createObjectURL(b) : null)).catch(() => null));
    }
    const url = await cache.get(name);
    if (url) img.src = url; else img.remove();
  }));
}

/** Download or open an export of one settlement. */
export async function exportSettlement(p, id, fmt) {
  const w = fmt === "html" ? window.open("about:blank", "_blank") : null;
  try {
    const r = await p._hass.fetchWithAuth(`/api/print_log/settlements/${id}/export?format=${fmt}&lang=${p.lang}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const url = URL.createObjectURL(await r.blob());
    if (w) { w.location.href = url; return; }
    const a = document.createElement("a"); a.href = url; a.download = `settlement_${id}.csv`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  } catch (e) { if (w) w.close(); alert(e.message); }
}
