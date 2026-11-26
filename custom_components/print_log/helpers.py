"""Small pure helpers (no Home Assistant imports) so they can be unit tested."""
from __future__ import annotations

import re
from typing import Any

from .defaults import DEFAULT_STATE_MAP, ENERGY_UNITS, LENGTH_UNITS, TIME_UNITS

_BAD = (None, "", "unknown", "unavailable")


def to_float(value: Any) -> float | None:
    if value in _BAD:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_meters(value: Any, unit: str | None, fallback_unit: str = "mm") -> float | None:
    v = to_float(value)
    if v is None:
        return None
    factor = LENGTH_UNITS.get((unit or "").lower()) or LENGTH_UNITS.get(fallback_unit, 0.001)
    return v * factor


def to_kwh(value: Any, unit: str | None) -> float | None:
    """Energy counter to kWh. Power units (W, kW) are not energy and return None."""
    v = to_float(value)
    if v is None:
        return None
    key = (unit or "kWh").lower()
    factor = ENERGY_UNITS.get(key)
    return v * factor if factor is not None else None


def to_percent(value: Any, unit: str | None) -> float | None:
    v = to_float(value)
    if v is None:
        return None
    if unit != "%" and 0 <= v <= 1:
        v *= 100
    return max(0.0, min(100.0, v))


def to_seconds(value: Any, unit: str | None) -> float | None:
    v = to_float(value)
    if v is None:
        return None
    return v * TIME_UNITS.get((unit or "s").lower(), 1.0)


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "?"
    s = int(max(0, seconds))
    h, m = divmod(s // 60, 60)
    return f"{h}h {m:02d}m" if h else f"{m} min"


def map_state(state: str | None, state_map: dict | None) -> str | None:
    """Translate a printer-specific state to printing/paused/complete/cancelled/error/idle."""
    if state in _BAD:
        return None
    s = str(state).strip().lower()
    merged = {k: (state_map or {}).get(k) or v for k, v in DEFAULT_STATE_MAP.items()}
    for key, values in merged.items():
        if s in [str(v).strip().lower() for v in values]:
            return key
    return None


def render(template: str, ctx: dict[str, Any]) -> str:
    """Replace {name} placeholders. Unknown placeholders stay untouched; nothing is evaluated."""
    return re.sub(r"\{(\w+)\}", lambda m: str(ctx.get(m.group(1), m.group(0))), template or "")


def pretty_name(filename: str | None) -> str:
    name = (filename or "").strip()
    for ext in (".gcode", ".stl", ".3mf"):
        name = name.replace(ext, "")
    return name.replace("_", " ").strip()
