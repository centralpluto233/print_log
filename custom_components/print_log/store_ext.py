"""Store extensions for v0.4.0 (pure Python): thumbnails, low-stock tracking, settlement details and allocation."""
from __future__ import annotations

import json
import re
import secrets

from pathlib import Path

from .store import Store

EXT_VERSION = 1
THUMB_RE = re.compile(r"^[0-9a-f]{16}\.(png|jpg)$")
THUMB_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg"}
THUMB_MAX_BYTES = 2_000_000


def split_final(final: int, prices: list[int]) -> list[int] | None:
    """Spread a final settlement amount (micro-euro) over prints, in proportion to their price.

    The shares add up to exactly `final`. Returns None when the prices already add up to it (nothing to change)."""
    n = len(prices)
    total = sum(prices)
    if not n or total == final:
        return None
    if total <= 0:
        base, extra = divmod(final, n)
        return [base + (1 if i < extra else 0) for i in range(n)]
    shares = [final * p // total for p in prices]
    order = sorted(range(n), key=lambda i: (-prices[i], i))
    for k in range(final - sum(shares)):
        shares[order[k % n]] += 1
    return shares


class ExtStore(Store):
    """Store with the v0.4.0 additions. Its own migration markers keep the base schema untouched."""

    def init(self) -> None:
        super().init()
        with self._db() as c:
            if (self._get(c, "ext_version", 0) or 0) < 1:
                cols = {r["name"] for r in c.execute("PRAGMA table_info(printers)")}
                if "thumbnail_entity" not in cols:
                    c.execute("ALTER TABLE printers ADD COLUMN thumbnail_entity TEXT")
                self._set(c, "ext_version", 1)
            if not self._get(c, "ext_alloc_done", False):
                cols = {r["name"] for r in c.execute("PRAGMA table_info(settlements)")}
                if "allocation" not in cols:
                    c.execute("ALTER TABLE settlements ADD COLUMN allocation TEXT")
                for r in c.execute("SELECT id FROM settlements WHERE allocation IS NULL").fetchall():
                    self._allocate(c, r["id"])
                self._set(c, "ext_alloc_done", True)

    def _clean(self, table, data, partial=False):
        out = super()._clean(table, data, partial)
        if table == "printers" and "thumbnail_entity" in data:
            out["thumbnail_entity"] = str(data["thumbnail_entity"] or "").strip() or None
        return out

    # ---------- thumbnails ----------
    @property
    def thumbs_dir(self) -> Path:
        return Path(self.path).parent / "thumbs"

    def save_thumbnail(self, content: bytes, content_type: str | None) -> str | None:
        """Store a thumbnail image and return its file name, or None when it is not a usable image."""
        ext = THUMB_TYPES.get((content_type or "").split(";")[0].strip().lower())
        if not ext or not content or len(content) > THUMB_MAX_BYTES:
            return None
        self.thumbs_dir.mkdir(parents=True, exist_ok=True)
        name = f"{secrets.token_hex(8)}.{ext}"
        (self.thumbs_dir / name).write_bytes(content)
        return name

    def thumbnail_path(self, name: str | None) -> Path | None:
        if not name or not THUMB_RE.match(name):
            return None
        path = self.thumbs_dir / name
        return path if path.is_file() else None

    def delete_print(self, print_id: int) -> bool:
        row = self.get_print(print_id)
        deleted = super().delete_print(print_id)
        if deleted and row:
            path = self.thumbnail_path(row.get("thumbnail"))
            if path:
                path.unlink(missing_ok=True)
        return deleted

    # ---------- low stock ----------
    def low_stock_check(self) -> list[dict]:
        """Rolls that dropped below the limit since the last check (each roll is reported once).

        A roll is reported again only after its stock went back above the limit."""
        rolls = self.list_table("filaments", False)
        low_now = {f["id"] for f in rolls if f.get("low_stock")}
        with self._db() as c:
            known = set(self._get(c, "low_stock_notified", []) or [])
            new = [f for f in rolls if f["id"] in low_now and f["id"] not in known]
            self._set(c, "low_stock_notified", sorted((known & low_now) | {f["id"] for f in new}))
        return new

    # ---------- settlements ----------
    def settlement_detail(self, settlement_id: int) -> dict | None:
        """One settlement with its prints (for the export)."""
        with self._db() as c:
            s = c.execute("SELECT s.*, pe.name AS person FROM settlements s JOIN people pe ON pe.id = s.person_id "
                          "WHERE s.id=?", (int(settlement_id),)).fetchone()
            if not s:
                return None
            rows = c.execute(self.SELECT + " WHERE p.settlement_id=? ORDER BY p.ended_at, p.id", (int(settlement_id),)).fetchall()
        out = {k: v for k, v in self._settlement_out(s).items() if k != "allocation"}
        return {**out, "prints": [self._out(r) for r in rows]}

    def _allocate(self, c, settlement_id: int) -> None:
        """Spread the final amount of a settlement over its prints as sale prices (so statistics show what was received).

        The sale prices the prints had before are saved in the settlement, so undoing it restores them."""
        s = c.execute("SELECT final_micro FROM settlements WHERE id=?", (settlement_id,)).fetchone()
        rows = c.execute("SELECT id, sale_price_micro, total_cost_micro FROM prints WHERE settlement_id=? ORDER BY id",
                         (settlement_id,)).fetchall()
        original = {str(r["id"]): r["sale_price_micro"] for r in rows}
        prices = [r["total_cost_micro"] if r["sale_price_micro"] is None else r["sale_price_micro"] for r in rows]
        shares = split_final(int(s["final_micro"]), prices) if s else None
        if shares is not None:
            for r, share in zip(rows, shares):
                c.execute("UPDATE prints SET sale_price_micro=? WHERE id=?", (share, r["id"]))
        c.execute("UPDATE settlements SET allocation=? WHERE id=?", (json.dumps(original), settlement_id))

    def settle(self, *args, **kwargs):
        result = super().settle(*args, **kwargs)
        if isinstance(result, dict) and result.get("id") is not None:
            with self._db() as c:
                self._allocate(c, int(result["id"]))
        return result

    def unsettle(self, settlement_id: int) -> bool:
        with self._db() as c:
            row = c.execute("SELECT allocation FROM settlements WHERE id=?", (int(settlement_id),)).fetchone()
            if row and row["allocation"]:
                for pid, sale in json.loads(row["allocation"]).items():
                    c.execute("UPDATE prints SET sale_price_micro=? WHERE id=? AND settlement_id=?",
                              (sale, int(pid), int(settlement_id)))
        return super().unsettle(settlement_id)
