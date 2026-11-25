
import sqlite3
import pytest
from pl.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "p.db", "Europe/Brussels")
    s.init()
    return s


def test_default_roles(store):
    assert {r["name"] for r in store.list_table("roles")} == {"familie", "vrienden", "extern"}


def test_add_print_costs_and_snapshot(store):
    f = store.add_item("filaments", {"name": "blue", "material": "PLA", "price_per_m": 0.04})
    p = store.add_item("people", {"name": "Seppe"})
    pr = store.add_print({"filename": "a.gcode", "person_id": p["id"], "filament_id": f["id"], "length_m": 10})
    assert pr["total_cost"] == 0.4
    store.update_item("filaments", f["id"], {"price_per_m": 0.10})
    assert store.get_print(pr["id"])["total_cost"] == 0.4
    pr2 = store.update_print(pr["id"], {"length_m": 20})
    assert pr2["total_cost"] == 0.8


def test_change_filament_recalculates(store):
    a = store.add_item("filaments", {"name": "a", "price_per_m": 0.04})
    b = store.add_item("filaments", {"name": "b", "price_per_m": 0.10})
    pr = store.add_print({"filament_id": a["id"], "length_m": 10})
    assert store.update_print(pr["id"], {"filament_id": b["id"]})["total_cost"] == 1.0


def test_role_modifier_follows_person_default(store):
    roles = {r["name"]: r["id"] for r in store.list_table("roles")}
    store.update_item("roles", roles["vrienden"], {"modifier_pct": -50})
    f = store.add_item("filaments", {"name": "a", "price_per_m": 0.10})
    p = store.add_item("people", {"name": "Jan", "default_role_id": roles["vrienden"]})
    pr = store.add_print({"person_id": p["id"], "filament_id": f["id"], "length_m": 10})
    assert pr["role"] == "vrienden" and pr["total_cost"] == 0.5


def test_delete_archives_when_in_use(store):
    f = store.add_item("filaments", {"name": "a", "price_per_m": 0.1})
    store.add_print({"filament_id": f["id"], "length_m": 1})
    assert store.delete_item("filaments", f["id"]) == "archived"
    g = store.add_item("filaments", {"name": "b", "price_per_m": 0.1})
    assert store.delete_item("filaments", g["id"]) == "deleted"


def test_filters_stats_export(store):
    f = store.add_item("filaments", {"name": "a", "price_per_m": 0.1})
    a = store.add_item("people", {"name": "A"})
    b = store.add_item("people", {"name": "B"})
    store.add_print({"person_id": a["id"], "filament_id": f["id"], "length_m": 10, "ended_at": "2026-10-01T10:00:00Z"})
    store.add_print({"person_id": b["id"], "filament_id": f["id"], "length_m": 5, "ended_at": "2026-11-01T10:00:00Z"})
    assert store.list_prints({"person": a["id"]})["total"] == 1
    assert store.list_prints({"from": "2026-10-15"})["total"] == 1
    st = {r["key"]: r for r in store.stats("person", {})}
    assert st["A"]["total_cost"] == 1.0 and st["B"]["prints"] == 1
    assert [r["key"] for r in store.stats("month", {})] == ["2026-10", "2026-11"]
    assert "filename" in store.export_csv({}).splitlines()[0]


def test_legacy_import(store, tmp_path):
    old = tmp_path / "old.db"
    c = sqlite3.connect(old)
    c.execute("CREATE TABLE rollen (naam TEXT PRIMARY KEY, materiaal TEXT, prijs_per_m REAL)")
    c.execute("CREATE TABLE prints (ts TEXT, persoon TEXT, rol TEXT, lengte_m REAL, prijs REAL, filename TEXT)")
    c.execute("INSERT INTO rollen VALUES ('blue','PLA',0.04)")
    c.execute("INSERT INTO prints VALUES ('2026-11-09T11:09:59','vincent','blue',10.0,0.4,'knive')")
    c.commit(); c.close()
    assert store.import_legacy(old) == 1
    assert store.import_legacy(old) == 0
    p = store.list_prints({})["items"][0]
    assert p["person"] == "vincent" and p["filament"] == "blue" and p["total_cost"] == 0.4
    assert p["ended_at"] == "2026-11-09T10:09:59Z" and p["source"] == "import"
