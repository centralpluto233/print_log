"""SQLite storage for Print Log. Pure Python (no Home Assistant imports)."""
from __future__ import annotations

import csv
import io
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .costs import MICRO, compute_costs, euro_to_micro, micro_to_euro

SCHEMA_VERSION = 1
DEFAULT_ROLES = ("familie", "vrienden", "extern")

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS roles (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
  modifier_pct REAL NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS people (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
  default_role_id INTEGER REFERENCES roles(id), modifier_pct REAL,
  archived INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS filaments (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, material TEXT,
  price_per_m_micro INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS prints (
  id INTEGER PRIMARY KEY,
  filename TEXT NOT NULL DEFAULT '',
  person_id INTEGER REFERENCES people(id),
  role_id INTEGER REFERENCES roles(id),
  filament_id INTEGER REFERENCES filaments(id),
  status TEXT NOT NULL DEFAULT 'complete',
  started_at TEXT, ended_at TEXT, duration_s INTEGER,
  length_m REAL NOT NULL DEFAULT 0, length_auto_m REAL,
  energy_kwh REAL, thumbnail TEXT,
  source TEXT NOT NULL DEFAULT 'auto',
  price_per_m_micro INTEGER NOT NULL DEFAULT 0,
  modifier_pct REAL NOT NULL DEFAULT 0,
  material_cost_micro INTEGER NOT NULL DEFAULT 0,
  energy_cost_micro INTEGER NOT NULL DEFAULT 0,
  total_cost_micro INTEGER NOT NULL DEFAULT 0,
  notes TEXT);
CREATE INDEX IF NOT EXISTS idx_prints_person ON prints(person_id);
CREATE INDEX IF NOT EXISTS idx_prints_ended ON prints(ended_at);
"""

TABLE_FIELDS = {
    "roles": ("name", "modifier_pct", "archived"),
    "people": ("name", "default_role_id", "modifier_pct", "archived"),
    "filaments": ("name", "material", "price_per_m_micro", "archived"),
}
PRINT_FIELDS = (
    "filename", "person_id", "role_id", "filament_id", "status", "started_at",
    "ended_at", "duration_s", "length_m", "length_auto_m", "energy_kwh",
    "thumbnail", "source", "price_per_m_micro", "modifier_pct",
    "energy_cost_micro", "notes",
)
SORTS = {
    "ended_at": "p.ended_at", "filename": "p.filename COLLATE NOCASE",
    "length_m": "p.length_m", "total_cost": "p.total_cost_micro",
    "duration_s": "p.duration_s", "person": "pe.name COLLATE NOCASE",
    "filament": "f.name COLLATE NOCASE", "status": "p.status", "role": "r.name COLLATE NOCASE",
}
GROUPS = {
    "person": "COALESCE(pe.name, '(onbekend)')",
    "role": "COALESCE(r.name, '(geen rol)')",
    "filament": "COALESCE(f.name, '(onbekend)')",
    "month": "COALESCE(substr(p.ended_at, 1, 7), '(onbekend)')",
    "status": "p.status",
}
BASE_FROM = (
    "FROM prints p LEFT JOIN people pe ON pe.id = p.person_id "
    "LEFT JOIN roles r ON r.id = p.role_id LEFT JOIN filaments f ON f.id = p.filament_id"
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(v, default=None):
    if v in (None, ""):
        return default
    return float(v)


def _int(v, default=None):
    if v in (None, ""):
        return default
    return int(v)


class Store:
    def __init__(self, path: str | Path, tz: str = "UTC") -> None:
        self.path = str(path)
        self.tz = ZoneInfo(tz)
        self._lock = threading.RLock()

    @contextmanager
    def _db(self):
        with self._lock:
            conn = sqlite3.connect(self.path, timeout=15)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    # ---------- setup ----------
    def init(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._db() as c:
            c.executescript(SCHEMA)
            if self._get(c, "schema_version") is None:
                self._set(c, "schema_version", SCHEMA_VERSION)
                for name in DEFAULT_ROLES:
                    c.execute("INSERT OR IGNORE INTO roles(name) VALUES (?)", (name,))
            for k, v in (("failed_cost_pct", 100), ("energy_price_micro", 0)):
                if self._get(c, k) is None:
                    self._set(c, k, v)

    @staticmethod
    def _get(c, key, default=None):
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    @staticmethod
    def _set(c, key, value):
        c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", (key, json.dumps(value)))

    def get_setting(self, key, default=None):
        with self._db() as c:
            return self._get(c, key, default)

    def set_setting(self, key, value):
        with self._db() as c:
            self._set(c, key, value)

    def get_settings(self) -> dict[str, Any]:
        with self._db() as c:
            return {r["key"]: json.loads(r["value"]) for r in c.execute("SELECT * FROM settings")
                    if r["key"] not in ("session", "schema_version", "legacy_imported")}

    def update_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        allowed = {"failed_cost_pct": float, "energy_price_micro": int,
                   "current_person_id": lambda v: _int(v), "current_role_id": lambda v: _int(v),
                   "current_filament_id": lambda v: _int(v)}
        with self._db() as c:
            for k, v in data.items():
                if k in allowed:
                    self._set(c, k, allowed[k](v) if v is not None else None)
        return self.get_settings()

    # ---------- people / roles / filaments ----------
    def list_table(self, table: str, include_archived: bool = True) -> list[dict]:
        if table not in TABLE_FIELDS:
            raise ValueError("unknown table")
        with self._db() as c:
            where = "" if include_archived else "WHERE archived = 0"
            rows = [dict(r) for r in c.execute(f"SELECT * FROM {table} {where} ORDER BY name COLLATE NOCASE")]
            counts = {r["k"]: r["n"] for r in c.execute(
                f"SELECT {self._fk(table)} AS k, COUNT(*) AS n FROM prints GROUP BY k")}
        for r in rows:
            r["print_count"] = counts.get(r["id"], 0)
            if table == "filaments":
                r["price_per_m"] = micro_to_euro(r["price_per_m_micro"])
        return rows

    @staticmethod
    def _fk(table):
        return {"people": "person_id", "roles": "role_id", "filaments": "filament_id"}[table]

    def _clean(self, table, data, partial=False):
        out = {}
        for k in TABLE_FIELDS[table]:
            if k in data:
                out[k] = data[k]
        if table == "filaments" and "price_per_m" in data:
            out["price_per_m_micro"] = euro_to_micro(data["price_per_m"])
        if "name" in out:
            out["name"] = str(out["name"]).strip()
            if not out["name"]:
                raise ValueError("name is required")
        elif not partial:
            raise ValueError("name is required")
        for k in ("modifier_pct",):
            if k in out:
                out[k] = _num(out[k], None if table == "people" else 0.0)
        for k in ("default_role_id", "price_per_m_micro"):
            if k in out:
                out[k] = _int(out[k], None if k == "default_role_id" else 0)
        if "archived" in out:
            out["archived"] = 1 if out["archived"] else 0
        return out

    def add_item(self, table: str, data: dict) -> dict:
        d = self._clean(table, data)
        with self._db() as c:
            cur = c.execute(f"INSERT INTO {table}({','.join(d)}) VALUES ({','.join('?' * len(d))})", list(d.values()))
            row = dict(c.execute(f"SELECT * FROM {table} WHERE id=?", (cur.lastrowid,)).fetchone())
        return row

    def update_item(self, table: str, item_id: int, data: dict) -> dict | None:
        d = self._clean(table, data, partial=True)
        with self._db() as c:
            if d:
                sets = ",".join(f"{k}=?" for k in d)
                c.execute(f"UPDATE {table} SET {sets} WHERE id=?", [*d.values(), item_id])
            row = c.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
        return dict(row) if row else None

    def delete_item(self, table: str, item_id: int) -> str:
        """Delete, or archive when prints still reference it. Returns 'deleted' or 'archived'."""
        with self._db() as c:
            n = c.execute(f"SELECT COUNT(*) FROM prints WHERE {self._fk(table)}=?", (item_id,)).fetchone()[0]
            if table == "roles":
                n += c.execute("SELECT COUNT(*) FROM people WHERE default_role_id=?", (item_id,)).fetchone()[0]
            if n:
                c.execute(f"UPDATE {table} SET archived=1 WHERE id=?", (item_id,))
                return "archived"
            c.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
            return "deleted"

    def get_or_create(self, table: str, name: str, **extra) -> int:
        name = name.strip()
        with self._db() as c:
            row = c.execute(f"SELECT id FROM {table} WHERE name=? COLLATE NOCASE", (name,)).fetchone()
            if row:
                return row["id"]
        return self.add_item(table, {"name": name, **extra})["id"]

    # ---------- prints ----------
    def _prepare(self, c, d: dict, existing: dict | None) -> dict:
        row = dict(existing or {})
        changed_person = existing is not None and "person_id" in d and d["person_id"] != existing["person_id"]
        changed_role = existing is not None and "role_id" in d and d["role_id"] != existing["role_id"]
        changed_fil = existing is not None and "filament_id" in d and d["filament_id"] != existing["filament_id"]
        if changed_person and "role_id" not in d:
            d = {**d, "role_id": None}
            changed_role = True
        for k in PRINT_FIELDS:
            if k in d:
                row[k] = d[k]
        row.setdefault("status", "complete")
        for k in ("person_id", "role_id", "filament_id"):
            row[k] = _int(row.get(k))
        row["length_m"] = _num(row.get("length_m"), 0.0)
        row["energy_kwh"] = _num(row.get("energy_kwh"))
        row["duration_s"] = _int(row.get("duration_s"))
        person = c.execute("SELECT * FROM people WHERE id=?", (row["person_id"],)).fetchone() if row["person_id"] else None
        if row["role_id"] is None and person and person["default_role_id"]:
            row["role_id"] = person["default_role_id"]
            changed_role = True
        if row.get("duration_s") is None and row.get("started_at") and row.get("ended_at"):
            try:
                a = datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
                b = datetime.fromisoformat(row["ended_at"].replace("Z", "+00:00"))
                row["duration_s"] = max(0, int((b - a).total_seconds()))
            except ValueError:
                pass
        if "price_per_m_micro" in d:
            row["price_per_m_micro"] = _int(d["price_per_m_micro"], 0)
        elif existing is None or changed_fil:
            fil = c.execute("SELECT price_per_m_micro FROM filaments WHERE id=?", (row["filament_id"],)).fetchone() if row["filament_id"] else None
            row["price_per_m_micro"] = fil["price_per_m_micro"] if fil else 0
        if "modifier_pct" in d:
            row["modifier_pct"] = _num(d["modifier_pct"], 0.0)
        elif existing is None or changed_person or changed_role:
            mod = None
            if person and person["modifier_pct"] is not None:
                mod = person["modifier_pct"]
            elif row["role_id"]:
                r = c.execute("SELECT modifier_pct FROM roles WHERE id=?", (row["role_id"],)).fetchone()
                mod = r["modifier_pct"] if r else None
            row["modifier_pct"] = mod or 0.0
        energy_price = self._get(c, "energy_price_micro", 0) or 0
        if row.get("energy_kwh") is not None and energy_price and "energy_cost_micro" not in d:
            row["energy_cost_micro"] = int(round(row["energy_kwh"] * energy_price))
        row["energy_cost_micro"] = _int(row.get("energy_cost_micro"), 0)
        row.update(compute_costs(
            row["length_m"], row["price_per_m_micro"], energy_micro=row["energy_cost_micro"],
            modifier_pct=row["modifier_pct"], status=row["status"],
            failed_cost_pct=self._get(c, "failed_cost_pct", 100)))
        row["filename"] = (row.get("filename") or "").strip()
        return row

    COLS = PRINT_FIELDS + ("material_cost_micro", "total_cost_micro")

    def add_print(self, data: dict) -> dict:
        with self._db() as c:
            row = self._prepare(c, data, None)
            row.setdefault("ended_at", utc_now_iso())
            if not row.get("ended_at"):
                row["ended_at"] = utc_now_iso()
            row.setdefault("source", "manual")
            cols = [k for k in self.COLS if k in row]
            cur = c.execute(f"INSERT INTO prints({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", [row[k] for k in cols])
            pid = cur.lastrowid
        return self.get_print(pid)

    def update_print(self, print_id: int, data: dict) -> dict | None:
        with self._db() as c:
            existing = c.execute("SELECT * FROM prints WHERE id=?", (print_id,)).fetchone()
            if not existing:
                return None
            row = self._prepare(c, data, dict(existing))
            cols = [k for k in self.COLS if k in row]
            c.execute(f"UPDATE prints SET {','.join(k + '=?' for k in cols)} WHERE id=?", [*[row[k] for k in cols], print_id])
        return self.get_print(print_id)

    def delete_print(self, print_id: int) -> bool:
        with self._db() as c:
            return c.execute("DELETE FROM prints WHERE id=?", (print_id,)).rowcount > 0

    SELECT = (
        "SELECT p.*, pe.name AS person, r.name AS role, f.name AS filament, f.material AS material "
        + BASE_FROM
    )

    @staticmethod
    def _out(r: sqlite3.Row) -> dict:
        d = dict(r)
        d["material_cost"] = micro_to_euro(d["material_cost_micro"])
        d["energy_cost"] = micro_to_euro(d["energy_cost_micro"])
        d["total_cost"] = micro_to_euro(d["total_cost_micro"])
        d["price_per_m"] = micro_to_euro(d["price_per_m_micro"])
        d["incomplete"] = d["person_id"] is None or d["filament_id"] is None
        return d

    def get_print(self, print_id: int) -> dict | None:
        with self._db() as c:
            r = c.execute(self.SELECT + " WHERE p.id=?", (print_id,)).fetchone()
        return self._out(r) if r else None

    @staticmethod
    def _where(f: dict) -> tuple[str, list]:
        cl, args = [], []
        for key, col in (("person", "p.person_id"), ("role", "p.role_id"), ("filament", "p.filament_id"), ("status", "p.status")):
            v = f.get(key)
            if v in (None, "", "all"):
                continue
            if v == "none" and key != "status":
                cl.append(f"{col} IS NULL")
            else:
                cl.append(f"{col} = ?")
                args.append(v)
        if f.get("from"):
            cl.append("p.ended_at >= ?"); args.append(f["from"])
        if f.get("to"):
            cl.append("p.ended_at <= ?"); args.append(f["to"] + "T23:59:59Z")
        if f.get("min_duration"):
            cl.append("p.duration_s >= ?"); args.append(float(f["min_duration"]) * 60)
        if f.get("max_duration"):
            cl.append("p.duration_s <= ?"); args.append(float(f["max_duration"]) * 60)
        if f.get("q"):
            cl.append("(p.filename LIKE ? OR p.notes LIKE ?)"); args += [f"%{f['q']}%"] * 2
        return (" WHERE " + " AND ".join(cl)) if cl else "", args

    def list_prints(self, f: dict, limit: int = 50, offset: int = 0, sort: str = "ended_at", desc: bool = True) -> dict:
        where, args = self._where(f)
        order = SORTS.get(sort, SORTS["ended_at"]) + (" DESC" if desc else " ASC")
        with self._db() as c:
            total = c.execute(f"SELECT COUNT(*) {BASE_FROM}{where}", args).fetchone()[0]
            sums = c.execute(f"SELECT COALESCE(SUM(p.total_cost_micro),0) t, COALESCE(SUM(p.length_m),0) l {BASE_FROM}{where}", args).fetchone()
            rows = c.execute(f"{self.SELECT}{where} ORDER BY {order}, p.id DESC LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()
        return {"total": total, "total_cost": micro_to_euro(sums["t"]), "total_length_m": round(sums["l"], 3),
                "items": [self._out(r) for r in rows]}

    def stats(self, group_by: str, f: dict) -> list[dict]:
        key = GROUPS.get(group_by)
        if not key:
            raise ValueError("invalid group_by")
        where, args = self._where(f)
        order = "k" if group_by == "month" else "cost DESC"
        with self._db() as c:
            rows = c.execute(
                f"SELECT {key} AS k, COUNT(*) AS prints, SUM(p.length_m) AS length_m, "
                f"COALESCE(SUM(p.duration_s),0) AS duration_s, SUM(p.total_cost_micro) AS cost "
                f"{BASE_FROM}{where} GROUP BY k ORDER BY {order}", args).fetchall()
        return [{"key": r["k"], "prints": r["prints"], "length_m": round(r["length_m"] or 0, 3),
                 "duration_s": r["duration_s"], "total_cost": micro_to_euro(r["cost"])} for r in rows]

    def export_csv(self, f: dict) -> str:
        data = self.list_prints(f, limit=1_000_000)["items"]
        buf = io.StringIO()
        cols = ["id", "ended_at", "started_at", "duration_s", "filename", "person", "role", "filament",
                "status", "length_m", "price_per_m", "material_cost", "energy_cost", "modifier_pct", "total_cost", "notes"]
        wr = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(data)
        return buf.getvalue()

    def summary(self) -> dict:
        with self._db() as c:
            r = c.execute("SELECT COUNT(*) n, COALESCE(SUM(total_cost_micro),0) t, COALESCE(SUM(length_m),0) l FROM prints").fetchone()
            last = c.execute(self.SELECT + " ORDER BY p.ended_at DESC, p.id DESC LIMIT 1").fetchone()
        return {"prints": r["n"], "total_cost": micro_to_euro(r["t"]), "length_m": round(r["l"], 3),
                "last": self._out(last) if last else None}

    # ---------- legacy import ----------
    def import_legacy(self, legacy_path: str | Path) -> int:
        """Import the old pyscript database (tables rollen + prints). Returns imported print count."""
        with self._db() as c:
            if self._get(c, "legacy_imported"):
                return 0
        src = sqlite3.connect(str(legacy_path))
        src.row_factory = sqlite3.Row
        try:
            rollen = [dict(r) for r in src.execute("SELECT naam, materiaal, prijs_per_m FROM rollen")]
            old = [dict(r) for r in src.execute("SELECT ts, persoon, rol, lengte_m, prijs, filename FROM prints ORDER BY ts")]
        finally:
            src.close()
        return self._import_rows(rollen, old)

    def _import_rows(self, rollen: list[dict], old: list[dict]) -> int:
        with self._db() as c:
            fil_ids, fil_price = {}, {}
            def fil(name, material=None, price=0.0):
                key = name.strip().lower()
                if key not in fil_ids:
                    row = c.execute("SELECT id, price_per_m_micro FROM filaments WHERE name=? COLLATE NOCASE", (name.strip(),)).fetchone()
                    if row:
                        fil_ids[key], fil_price[key] = row["id"], row["price_per_m_micro"]
                    else:
                        cur = c.execute("INSERT INTO filaments(name, material, price_per_m_micro) VALUES (?,?,?)",
                                        (name.strip(), material, euro_to_micro(price)))
                        fil_ids[key], fil_price[key] = cur.lastrowid, euro_to_micro(price)
                return fil_ids[key], fil_price[key]
            for r in rollen:
                fil(r["naam"], r.get("materiaal"), r.get("prijs_per_m") or 0)
            people = {}
            n = 0
            for r in old:
                name = (r["persoon"] or "").strip() or None
                pid = None
                if name:
                    if name.lower() not in people:
                        row = c.execute("SELECT id FROM people WHERE name=? COLLATE NOCASE", (name,)).fetchone()
                        people[name.lower()] = row["id"] if row else c.execute("INSERT INTO people(name) VALUES (?)", (name,)).lastrowid
                    pid = people[name.lower()]
                fid, fprice = (fil(r["rol"]) if r["rol"] else (None, 0))
                length = float(r["lengte_m"] or 0)
                total = euro_to_micro(r["prijs"] or 0)
                ppm = int(round(total / length)) if length > 0 else fprice
                try:
                    ts = datetime.fromisoformat(r["ts"]).replace(tzinfo=self.tz).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                except (TypeError, ValueError):
                    ts = utc_now_iso()
                c.execute(
                    "INSERT INTO prints(filename, person_id, filament_id, status, ended_at, length_m, length_auto_m, source,"
                    " price_per_m_micro, modifier_pct, material_cost_micro, energy_cost_micro, total_cost_micro)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (r["filename"] or "", pid, fid, "complete", ts, length, length, "import", ppm, 0.0, total, 0, total))
                n += 1
            self._set(c, "legacy_imported", True)
        return n
