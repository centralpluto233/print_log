"""Settlement exports (pure Python): CSV and a printable HTML page."""
from __future__ import annotations

import csv
import io
from html import escape

LABELS = {
    "en": {"title": "Settlement", "person": "Person", "period": "Period", "date": "Date", "created": "Settled on",
           "file": "File", "filament": "Filament", "meters": "Meters", "price": "Price", "prints": "Prints",
           "calculated": "Calculated", "final": "Final amount", "difference": "Difference", "note": "Note", "all": "all"},
    "nl": {"title": "Afrekening", "person": "Persoon", "period": "Periode", "date": "Datum", "created": "Afgerekend op",
           "file": "Bestand", "filament": "Filament", "meters": "Meter", "price": "Prijs", "prints": "Prints",
           "calculated": "Berekend", "final": "Eindbedrag", "difference": "Verschil", "note": "Notitie", "all": "alles"},
}


def _lang(lang: str | None) -> str:
    return lang if lang in LABELS else "en"


def money(value: float, lang: str = "en") -> str:
    """EUR with at least 2 and at most 4 decimals."""
    whole, dec = f"{float(value or 0):.4f}".split(".")
    dec = dec.rstrip("0").ljust(2, "0")
    return f"EUR {whole}{',' if lang == 'nl' else '.'}{dec}"


def _day(iso: str | None) -> str:
    return (iso or "")[:10]


def settlement_csv(detail: dict, lang: str | None = "en") -> str:
    lang = _lang(lang)
    t = LABELS[lang]
    buf = io.StringIO()
    wr = csv.writer(buf)
    wr.writerow([t["date"], t["file"], t["filament"], t["meters"], t["price"]])
    for p in detail["prints"]:
        wr.writerow([_day(p.get("ended_at")), p.get("filename") or "", p.get("filament") or "", p.get("length_m", 0), p.get("price", 0)])
    wr.writerow([])
    wr.writerow([t["person"], detail["person"]])
    wr.writerow([t["period"], detail.get("period") or t["all"]])
    wr.writerow([t["created"], _day(detail.get("created_at"))])
    wr.writerow([t["calculated"], detail["calculated"]])
    wr.writerow([t["final"], detail["final"]])
    wr.writerow([t["difference"], detail["diff"]])
    if detail.get("note"):
        wr.writerow([t["note"], detail["note"]])
    return buf.getvalue()


def settlement_html(detail: dict, lang: str | None = "en") -> str:
    """A self-contained printable page (no scripts). Open it and use the browser's print / save as PDF."""
    lang = _lang(lang)
    t = LABELS[lang]
    e = lambda v: escape(str(v if v is not None else ""))  # noqa: E731
    rows = "".join(
        f"<tr><td>{e(_day(p.get('ended_at')))}</td><td>{e(p.get('filename'))}</td><td>{e(p.get('filament'))}</td>"
        f"<td class=n>{float(p.get('length_m') or 0):.2f}</td><td class=n>{e(money(p.get('price'), lang))}</td></tr>"
        for p in detail["prints"])
    note = f"<p><b>{e(t['note'])}:</b> {e(detail['note'])}</p>" if detail.get("note") else ""
    return f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><title>{e(t['title'])} {e(detail['person'])}</title>
<style>
body{{font-family:system-ui,Arial,sans-serif;max-width:800px;margin:24px auto;padding:0 16px;color:#111}}
h1{{font-size:22px;margin:0 0 4px}}table{{width:100%;border-collapse:collapse;margin:16px 0}}
th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid #ccc;font-size:14px}}.n{{text-align:right}}
.sum td{{border:0;padding:3px 8px}}.sum tr:last-child td{{font-weight:700;border-top:2px solid #111}}
@media print{{body{{margin:0}}}}
</style></head><body>
<h1>{e(t['title'])} #{e(detail['id'])}</h1>
<p>{e(t['person'])}: <b>{e(detail['person'])}</b><br>{e(t['period'])}: {e(detail.get('period') or t['all'])}<br>{e(t['created'])}: {e(_day(detail.get('created_at')))}</p>
<table><thead><tr><th>{e(t['date'])}</th><th>{e(t['file'])}</th><th>{e(t['filament'])}</th><th class=n>{e(t['meters'])}</th><th class=n>{e(t['price'])}</th></tr></thead><tbody>{rows}</tbody></table>
<table class="sum"><tbody>
<tr><td>{e(t['calculated'])} ({len(detail['prints'])} {e(t['prints'].lower())})</td><td class=n>{e(money(detail['calculated'], lang))}</td></tr>
<tr><td>{e(t['difference'])}</td><td class=n>{e(money(detail['diff'], lang))}</td></tr>
<tr><td>{e(t['final'])}</td><td class=n>{e(money(detail['final'], lang))}</td></tr>
</tbody></table>{note}
</body></html>
"""
