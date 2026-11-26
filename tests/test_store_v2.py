import json
import sqlite3
import pytest
from pl.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "p.db", "Europe/Brussels")
    s.init()
    return s


def test_printer_crud_and_state_map_defaults(store):
    p = store.add_item("printers", {"name": "V400", "state_entity": "sensor.state", "state_map": {"complete": ["finished"]}})
    row = [r for r in store.list_table("printers") if r["id"] == p["id"]][0]
    assert row["state_map"]["complete"] == ["finished"]
    assert row["state_map"]["printing"] == ["printing"]
    assert store.update_item("printers", p["id"], {"energy_entity": " sensor.shelly "})["energy_entity"] == "sensor.shelly"
    assert store.update_item("printers", p["id"], {"energy_entity": ""})["energy_entity"] is None


def test_energy_cost_snapshot(store):
    store.update_settings({"energy_price_micro": 300_000})
    f = store.add_item("filaments", {"name": "a", "price_per_m": 0.1})
    pr = store.add_print({"filament_id": f["id"], "length_m": 10, "energy_kwh": 0.5})
    assert pr["energy_cost"] == 0.15 and pr["total_cost"] == 1.15
    store.update_settings({"energy_price_micro": 1_000_000})
    assert store.get_print(pr["id"])["energy_cost"] == 0.15
    assert store.update_print(pr["id"], {"energy_kwh": 1.0})["energy_cost"] == 0.3


def test_no_energy_means_no_energy_cost(store):
    store.update_settings({"energy_price_micro": 300_000})
    pr = store.add_print({"length_m": 1})
    assert pr["energy_cost"] == 0 and pr["energy_kwh"] is None


def test_notification_settings_validated(store):
    s = store.update_settings({"notifications": {"targets": ["notify.mobile_app_x"], "min_step_pct": "5",
                                                 "enabled": False, "bogus": 1, "progress_title": "{printer}"}})
    n = s["notifications"]
    assert n["targets"] == ["notify.mobile_app_x"] and n["min_step_pct"] == 5 and n["enabled"] is False
    assert "bogus" not in n and n["progress_title"] == "{printer}"
    assert n["on_complete"] is True


def test_default_printer_from_entry_and_assign_old_prints(store):
    store.add_print({"length_m": 1})
    f = store.add_item("filaments", {"name": "a", "price_per_m": 0.1})
    store.set_setting("current_filament_id", f["id"])
    assert store.ensure_default_printer({"state_entity": "sensor.s", "filename_entity": "sensor.f", "length_unit": "m"})
    assert not store.ensure_default_printer({"state_entity": "sensor.other"})
    pr = store.list_table("printers")[0]
    assert pr["name"] == "Printer" and pr["current_filament_id"] == f["id"] and pr["length_unit"] == "m"
    assert store.list_prints({})["items"][0]["printer"] == "Printer"
    assert store.list_prints({"printer": pr["id"]})["total"] == 1


def test_migration_from_v1(tmp_path):
    path = tmp_path / "v1.db"
    c = sqlite3.connect(path)
    c.executescript("""
    CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE roles (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, modifier_pct REAL NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE people (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, default_role_id INTEGER, modifier_pct REAL, archived INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE filaments (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, material TEXT, price_per_m_micro INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE prints (id INTEGER PRIMARY KEY, filename TEXT NOT NULL DEFAULT '', person_id INTEGER, role_id INTEGER, filament_id INTEGER,
      status TEXT NOT NULL DEFAULT 'complete', started_at TEXT, ended_at TEXT, duration_s INTEGER, length_m REAL NOT NULL DEFAULT 0,
      length_auto_m REAL, energy_kwh REAL, thumbnail TEXT, source TEXT NOT NULL DEFAULT 'auto', price_per_m_micro INTEGER NOT NULL DEFAULT 0,
      modifier_pct REAL NOT NULL DEFAULT 0, material_cost_micro INTEGER NOT NULL DEFAULT 0, energy_cost_micro INTEGER NOT NULL DEFAULT 0,
      total_cost_micro INTEGER NOT NULL DEFAULT 0, notes TEXT);
    INSERT INTO settings VALUES ('schema_version', '1');
    INSERT INTO prints(filename, length_m, total_cost_micro, ended_at) VALUES ('old.gcode', 3, 120000, '2026-11-01T10:00:00Z');
    """)
    c.commit(); c.close()
    s = Store(path)
    s.init()
    assert s.get_setting("schema_version") == 2
    assert s.list_prints({})["items"][0]["filename"] == "old.gcode"
    s.init()
