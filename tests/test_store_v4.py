import pytest

from pl.exports import money, settlement_csv, settlement_html
from pl.store_ext import ExtStore


@pytest.fixture
def store(tmp_path):
    s = ExtStore(tmp_path / "pl" / "prints.db")
    s.init()
    return s


def _sql(store, sql, args=()):
    with store._db() as c:
        return c.execute(sql, args).lastrowid


def test_init_adds_thumbnail_entity_and_is_repeatable(store):
    store.init()
    with store._db() as c:
        cols = {r["name"] for r in c.execute("PRAGMA table_info(printers)")}
    assert "thumbnail_entity" in cols
    assert store.get_setting("ext_version") == 1


def test_upgrade_from_existing_v3_database_keeps_data(tmp_path):
    from pl.store import Store
    path = tmp_path / "prints.db"
    base = Store(path)
    base.init()
    _sql(base, "INSERT INTO people(name) VALUES ('Seppe')")
    ext = ExtStore(path)
    ext.init()
    assert [p["name"] for p in ext.list_table("people")] == ["Seppe"]


def test_printer_thumbnail_entity_is_cleaned(store):
    assert store._clean("printers", {"name": "A", "thumbnail_entity": "  camera.x "})["thumbnail_entity"] == "camera.x"
    assert store._clean("printers", {"name": "A", "thumbnail_entity": ""})["thumbnail_entity"] is None
    assert "thumbnail_entity" not in store._clean("printers", {"name": "A"})


def test_save_thumbnail_validates_and_stores(store):
    name = store.save_thumbnail(b"\x89PNGdata", "image/png")
    assert name and name.endswith(".png") and store.thumbnail_path(name).read_bytes() == b"\x89PNGdata"
    assert store.save_thumbnail(b"x", "text/html") is None
    assert store.save_thumbnail(b"", "image/png") is None
    assert store.save_thumbnail(b"x" * 2_000_001, "image/jpeg") is None
    assert store.save_thumbnail(b"jpg", "image/jpeg; charset=x").endswith(".jpg")


@pytest.mark.parametrize("bad", ["../prints.db", "a.png", "0123456789abcdef.exe", "0123456789abcdef.png/..", "", None])
def test_thumbnail_path_rejects_bad_names(store, bad):
    assert store.thumbnail_path(bad) is None


def test_delete_print_removes_thumbnail_file(store):
    name = store.save_thumbnail(b"png", "image/png")
    pid = _sql(store, "INSERT INTO prints(filename, thumbnail, ended_at) VALUES ('a', ?, '2026-10-01T10:00:00Z')", (name,))
    path = store.thumbnail_path(name)
    assert path and store.delete_print(pid) is True
    assert not path.exists()
    assert store.delete_print(pid) is False


def test_low_stock_reported_once_until_restocked(store):
    fid = _sql(store, "INSERT INTO filaments(name, stock_m, stock_at) VALUES ('PLA', 60, '2026-01-01T00:00:00Z')")
    assert store.low_stock_check() == []
    _sql(store, "INSERT INTO prints(filename, filament_id, length_m, ended_at) VALUES ('a', ?, 20, '2026-02-01T00:00:00Z')", (fid,))
    first = store.low_stock_check()
    assert [f["name"] for f in first] == ["PLA"] and first[0]["remaining_m"] == 40
    assert store.low_stock_check() == []
    _sql(store, "UPDATE filaments SET stock_m=500, stock_at='2026-03-01T00:00:00Z' WHERE id=?", (fid,))
    assert store.low_stock_check() == []
    _sql(store, "INSERT INTO prints(filename, filament_id, length_m, ended_at) VALUES ('b', ?, 460, '2026-03-02T00:00:00Z')", (fid,))
    assert [f["name"] for f in store.low_stock_check()] == ["PLA"]


def test_low_stock_ignores_rolls_without_stock(store):
    _sql(store, "INSERT INTO filaments(name) VALUES ('NoStock')")
    assert store.low_stock_check() == []


def _settlement(store):
    pe = _sql(store, "INSERT INTO people(name) VALUES ('Seppe')")
    fil = _sql(store, "INSERT INTO filaments(name) VALUES ('Galaxy <b>')")
    sid = _sql(store, "INSERT INTO settlements(person_id, period, prints_count, calculated_micro, final_micro, diff_micro, note, created_at) "
                      "VALUES (?, '2026-10', 2, 1083333, 1090000, 6667, 'deel 1', '2026-11-01T09:00:00Z')", (pe,))
    for n, (micro, day) in enumerate(((583333, 2), (500000, 5)), 1):
        _sql(store, "INSERT INTO prints(filename, person_id, filament_id, length_m, ended_at, total_cost_micro, settlement_id, paid_at) "
                    "VALUES (?, ?, ?, 5, ?, ?, ?, '2026-11-01T09:00:00Z')", (f"f{n}.gcode", pe, fil, f"2026-10-0{day}T10:00:00Z", micro, sid))
    _sql(store, "INSERT INTO prints(filename, person_id, ended_at, total_cost_micro) VALUES ('other', ?, '2026-10-09T10:00:00Z', 9000000)", (pe,))
    return sid


def test_settlement_detail_lists_only_its_prints(store):
    d = store.settlement_detail(_settlement(store))
    assert d["person"] == "Seppe" and d["final"] == 1.09 and [p["filename"] for p in d["prints"]] == ["f1.gcode", "f2.gcode"]
    assert d["calculated"] == 1.083333
    assert store.settlement_detail(9999) is None


def test_exports(store):
    d = store.settlement_detail(_settlement(store))
    csv_en = settlement_csv(d, "en")
    assert csv_en.splitlines()[0] == "Date,File,Filament,Meters,Price"
    assert "2026-10-02,f1.gcode,Galaxy <b>,5.0,0.583333" in csv_en and "Final amount,1.09" in csv_en and "Note,deel 1" in csv_en
    assert "Afrekening" not in csv_en and settlement_csv(d, "nl").startswith("Datum,Bestand")
    html = settlement_html(d, "nl")
    assert "Galaxy &lt;b&gt;" in html and "<b>Galaxy" not in html and "EUR 1,09" in html and "EUR 0,0067" in html
    assert "<script" not in html and 'lang="nl"' in html


def test_money_format():
    assert money(1.5) == "EUR 1.50" and money(0.0066670, "nl") == "EUR 0,0067" and money(None) == "EUR 0.00" and money(-0.5) == "EUR -0.50"
