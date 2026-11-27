import sqlite3
import pytest
import pl.store as sm
from pl.costs import round_up_micro
from pl.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "p.db", "Europe/Brussels")
    s.init()
    return s


def test_round_up_micro():
    assert round_up_micro(666_660) == 670_000
    assert round_up_micro(670_000) == 670_000
    assert round_up_micro(670_001) == 680_000
    assert round_up_micro(1_000_001, 1_000_000) == 2_000_000
    assert round_up_micro(0) == 0


def test_migration_v2_to_v3_keeps_data(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, "SCHEMA_VERSION", 2)
    s = Store(tmp_path / "p.db")
    s.init()
    c = sqlite3.connect(tmp_path / "p.db")
    c.execute("INSERT INTO filaments(name, material, price_per_m_micro) VALUES ('old','PLA',50000)")
    c.execute("INSERT INTO prints(filename, length_m, total_cost_micro, ended_at) VALUES ('x', 2, 100000, '2026-11-01T10:00:00Z')")
    c.commit(); c.close()
    monkeypatch.setattr(sm, "SCHEMA_VERSION", 3)
    s2 = Store(tmp_path / "p.db")
    s2.init()
    s2.init()
    assert s2.get_setting("schema_version") == 3
    fil = s2.list_table("filaments")[0]
    assert fil["name"] == "old" and fil["brand"] is None and fil["remaining_m"] is None and fil["low_stock"] is False
    p = s2.list_prints({})["items"][0]
    assert p["filename"] == "x" and p["paid"] is False and p["price"] == 0.1 and p["profit"] == 0.1 - p["material_cost"]


def test_filament_details(store):
    f = store.add_item("filaments", {"name": "Galaxy", "material": "PETG", "brand": " Prusament ",
                                     "color": "Galaxy Black", "color_hex": "#1b1b1f", "price_per_m": 0.0333333})
    row = [r for r in store.list_table("filaments") if r["id"] == f["id"]][0]
    assert row["brand"] == "Prusament" and row["color"] == "Galaxy Black" and row["color_hex"] == "#1b1b1f"
    assert row["material"] == "PETG" and row["price_per_m_micro"] == 33333
    store.update_item("filaments", f["id"], {"brand": ""})
    assert store.list_table("filaments")[0]["brand"] is None


def test_stock_remaining_and_baseline(store):
    f = store.add_item("filaments", {"name": "a", "price_per_m": 0.1})
    store.add_print({"filament_id": f["id"], "length_m": 10, "ended_at": "2026-01-01T00:00:00Z"})
    store.update_item("filaments", f["id"], {"stock_m": 100})
    row = lambda: store.list_table("filaments")[0]
    assert row()["remaining_m"] == 100
    store.add_print({"filament_id": f["id"], "length_m": 12.5, "ended_at": "2999-01-01T00:00:00Z", "status": "cancelled"})
    assert row()["remaining_m"] == 87.5
    store.update_item("filaments", f["id"], {"name": "renamed", "stock_m": 100})
    assert row()["name"] == "renamed" and row()["remaining_m"] == 87.5


def test_changing_stock_sets_new_baseline(store):
    g = store.add_item("filaments", {"name": "g", "price_per_m": 0.1, "stock_m": 100})
    store.add_print({"filament_id": g["id"], "length_m": 30, "ended_at": "2026-01-01T00:00:00Z"})
    assert store.list_table("filaments")[0]["remaining_m"] == 100
    store.update_item("filaments", g["id"], {"stock_m": 55})
    assert store.list_table("filaments")[0]["remaining_m"] == 55


def test_low_stock_flag(store):
    f = store.add_item("filaments", {"name": "a", "price_per_m": 0.1, "stock_m": 60})
    assert store.list_table("filaments")[0]["low_stock"] is False
    store.add_print({"filament_id": f["id"], "length_m": 20, "ended_at": "2999-01-01T00:00:00Z"})
    assert store.list_table("filaments")[0]["low_stock"] is True
    store.update_settings({"low_stock_m": 10})
    assert store.list_table("filaments")[0]["low_stock"] is False


def test_sale_price_and_profit(store):
    f = store.add_item("filaments", {"name": "a", "price_per_m": 0.1})
    p = store.add_print({"filament_id": f["id"], "length_m": 10, "modifier_pct": 50})
    assert p["total_cost"] == 1.5 and p["price"] == 1.5 and p["profit"] == 0.5 and p["sale_price"] is None
    p = store.update_print(p["id"], {"sale_price": 1.2})
    assert p["price"] == 1.2 and p["profit"] == 0.2 and p["total_cost"] == 1.5
    p = store.update_print(p["id"], {"length_m": 20})
    assert p["sale_price"] == 1.2 and p["total_cost"] == 3.0
    p = store.update_print(p["id"], {"sale_price": ""})
    assert p["sale_price"] is None and p["price"] == 3.0 and p["profit"] == 1.0
    res = store.list_prints({})
    assert res["total_profit"] == 1.0 and res["total_price"] == 3.0
    assert store.stats("month", {})[0]["profit"] == 1.0


def test_paid_flag_filter_and_bulk(store):
    a = store.add_print({"length_m": 1, "ended_at": "2026-11-01T00:00:00Z"})
    b = store.add_print({"length_m": 1, "ended_at": "2026-11-02T00:00:00Z"})
    c = store.add_print({"length_m": 1, "ended_at": "2026-11-03T00:00:00Z"})
    assert store.mark_paid([a["id"], b["id"]]) == 2
    assert store.mark_paid([a["id"]]) == 0
    assert store.list_prints({"paid": "yes"})["total"] == 2
    assert store.list_prints({"paid": "no"})["total"] == 1
    assert store.get_print(a["id"])["paid"] is True
    assert store.mark_paid([a["id"]], paid=False) == 1
    assert store.update_print(c["id"], {"paid": True})["paid"] is True
    assert store.update_print(c["id"], {"paid": False})["paid_at"] is None


def _setup_person(store):
    f = store.add_item("filaments", {"name": "a", "price_per_m": 0.0333333})
    p = store.add_item("people", {"name": "Seppe"})
    ids = [store.add_print({"person_id": p["id"], "filament_id": f["id"], "length_m": 10,
                            "ended_at": f"2026-1{m}-05T10:00:00Z"})["id"] for m in (0, 0, 1)]
    return p, ids


def test_settlement_preview_and_rounding(store):
    p, ids = _setup_person(store)
    pv = store.settlement_preview(p["id"], "2026-10")
    assert pv["prints"] == 2 and pv["print_ids"] == ids[:2]
    assert pv["calculated"] == 0.66666
    assert pv["suggestions"] == {"cent": 0.67, "50c": 1.0, "euro": 1.0}
    assert store.settlement_preview(p["id"])["prints"] == 3


def test_settle_default_rounds_up_to_cent_and_stores_difference(store):
    p, ids = _setup_person(store)
    s = store.settle(p["id"], ids[:2], period="2026-10")
    assert s["calculated_micro"] == 666_660 and s["final_micro"] == 670_000 and s["diff_micro"] == 3_340
    assert s["final"] == 0.67 and s["diff"] == 0.00334 and s["person"] == "Seppe"
    assert all(store.get_print(i)["paid"] for i in ids[:2])
    assert store.settlement_preview(p["id"])["print_ids"] == ids[2:]


def test_settle_manual_amount_and_errors(store):
    p, ids = _setup_person(store)
    s = store.settle(p["id"], ids[:2], final=0.80, note="afgerond")
    assert s["final"] == 0.8 and s["diff_micro"] == 800_000 - 666_660 and s["note"] == "afgerond"
    with pytest.raises(ValueError):
        store.settle(p["id"], ids[:2])
    with pytest.raises(ValueError):
        store.settle(p["id"], [])
    with pytest.raises(ValueError):
        store.settle(p["id"], ids[2:], final=-1)
    with pytest.raises(ValueError):
        store.mark_paid(ids[:1], paid=False)
    other = store.add_item("people", {"name": "Other"})
    with pytest.raises(ValueError):
        store.settle(other["id"], ids[2:])


def test_unsettle_restores_prints(store):
    p, ids = _setup_person(store)
    s = store.settle(p["id"], ids)
    assert store.list_settlements(p["id"])[0]["id"] == s["id"]
    assert store.unsettle(s["id"]) is True and store.unsettle(s["id"]) is False
    assert store.list_settlements() == []
    assert store.settlement_preview(p["id"])["prints"] == 3


def test_person_with_settlement_is_archived_not_deleted(store):
    p, ids = _setup_person(store)
    store.settle(p["id"], ids)
    for i in ids:
        store.delete_print(i)
    assert store.delete_item("people", p["id"]) == "archived"


def test_csv_has_new_columns(store):
    store.add_print({"length_m": 1})
    head = store.export_csv({}).splitlines()[0]
    assert "profit" in head and "paid_at" in head and "sale_price" in head
