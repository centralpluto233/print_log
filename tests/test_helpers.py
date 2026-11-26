from pl.helpers import fmt_duration, map_state, pretty_name, render, to_kwh, to_meters, to_percent, to_seconds


def test_units():
    assert to_meters("1500", "mm") == 1.5
    assert to_meters("2", "m") == 2
    assert to_meters("1000", None, "mm") == 1.0
    assert to_meters("unknown", "m") is None
    assert to_kwh("1500", "Wh") == 1.5
    assert to_kwh("2.5", "kWh") == 2.5
    assert to_kwh("120", "W") is None
    assert to_percent("0.5", None) == 50
    assert to_percent("42", "%") == 42
    assert to_percent("150", "%") == 100
    assert to_seconds("2", "min") == 120


def test_state_map_defaults_and_custom():
    assert map_state("Printing", None) == "printing"
    assert map_state("standby", {}) == "idle"
    assert map_state("finished", {"complete": ["finished"], "printing": []}) == "complete"
    assert map_state("printing", {"printing": []}) == "printing"
    assert map_state("unavailable", None) is None
    assert map_state("whatever", None) is None


def test_render_is_safe():
    assert render("{printer}: {percent}%", {"printer": "V400", "percent": 42}) == "V400: 42%"
    assert render("{unknown} {__class__}", {}) == "{unknown} {__class__}"


def test_misc():
    assert fmt_duration(3900) == "1h 05m"
    assert fmt_duration(300) == "5 min"
    assert fmt_duration(None) == "?"
    assert pretty_name("winglet_insert - Part 1_PLA_18m55s.gcode") == "winglet insert - Part 1 PLA 18m55s"
