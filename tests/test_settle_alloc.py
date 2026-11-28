import pytest

from pl.store import Store
from pl.store_ext import ExtStore, split_final


@pytest.mark.parametrize("final,prices", [
    (8_000_000, [583_333, 500_000, 326_567]), (1, [5, 5, 5]), (0, [10, 20]), (7, [0, 0, 0]),
    (1_000_003, [1, 1_000_000, 2]), (500, [999_999]), (10, [3, 0, 7]),
])
def test_split_final_adds_up_exactly_and_is_proportional(final, prices):
    shares = split_final(final, prices)
    if sum(prices) == final:
        assert shares is None
        return
    assert sum(shares) == final and all(s >= 0 for s in shares) and len(shares) == len(prices)
    if sum(prices) > 0:
        for s, p in zip(shares, prices):
            assert abs(s - final * p / sum(prices)) < 1


def test_split_final_nothing_to_do():
    assert split_final(10, []) is None and split_final(15, [5, 10]) is None


def _person_with_prints(store, lengths):
    pid = store.add_item("people", {"name": "Seppe"})["id"]
    fid = store.add_item("filaments", {"name": "PLA", "price_per_m": 0.03})["id"]
    ids = [store.add_print({"person_id": pid, "filament_id": fid, "length_m": n, "filename": f"f{n}.gcode"})["id"] for n in lengths]
    return pid, ids


def _prices(store, ids):
    return [store.get_print(i) for i in ids]


@pytest.fixture
def store(tmp_path):
    s = ExtStore(tmp_path / "pl" / "prints.db")
    s.init()
    return s


def test_settling_with_a_higher_final_amount_books_the_difference_as_profit(store):
    pid, ids = _person_with_prints(store, [10, 20, 33])
    cost = sum(p["total_cost_micro"] for p in _prices(store, ids)) / 1e6
    store.settle(pid, ids, 8.0, "x", None)
    rows = _prices(store, ids)
    assert sum(p["price"] for p in rows) == pytest.approx(8.0, abs=1e-6)
    assert sum(p["profit"] for p in rows) == pytest.approx(8.0 - cost, abs=1e-6)
    assert all(p["sale_price"] is not None for p in rows)


def test_settling_the_calculated_amount_changes_nothing(store):
    pid, ids = _person_with_prints(store, [10, 20])
    store.settle(pid, ids, 0.9, None, None)
    assert all(p["sale_price"] is None for p in _prices(store, ids))


def test_a_lower_final_amount_gives_a_loss(store):
    pid, ids = _person_with_prints(store, [10, 20])
    store.settle(pid, ids, 0.5, None, None)
    assert sum(p["profit"] for p in _prices(store, ids)) < 0


def test_undo_restores_the_earlier_sale_prices(store):
    pid, ids = _person_with_prints(store, [10, 20, 33])
    store.update_print(ids[0], {"sale_price": 1.0}) if hasattr(store, "update_print") else None
    before = [p["sale_price"] for p in _prices(store, ids)]
    sid = store.settle(pid, ids, 8.0, None, None)["id"]
    assert store.unsettle(sid) is True
    assert [p["sale_price"] for p in _prices(store, ids)] == before
    assert store.unsettle(sid) is False


def test_existing_settlements_are_allocated_when_the_extension_starts(tmp_path):
    path = tmp_path / "prints.db"
    base = Store(path)
    base.init()
    pid, ids = _person_with_prints(base, [10, 20, 33])
    sid = base.settle(pid, ids, 8.0, None, None)["id"]
    assert all(p["sale_price"] is None for p in _prices(base, ids))
    ext = ExtStore(path)
    ext.init()
    assert sum(p["price"] for p in _prices(ext, ids)) == pytest.approx(8.0, abs=1e-6)
    ext.init()
    assert sum(p["price"] for p in _prices(ext, ids)) == pytest.approx(8.0, abs=1e-6)
    assert ext.unsettle(sid) is True
    assert all(p["sale_price"] is None for p in _prices(ext, ids))


def test_settlement_detail_hides_the_allocation_column(store):
    pid, ids = _person_with_prints(store, [10, 20])
    sid = store.settle(pid, ids, 3.0, None, None)["id"]
    d = store.settlement_detail(sid)
    assert "allocation" not in d and len(d["prints"]) == 2
