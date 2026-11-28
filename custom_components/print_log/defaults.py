"""Default values (pure Python)."""

DEFAULT_STATE_MAP = {
    "printing": ["printing"],
    "paused": ["paused"],
    "complete": ["complete"],
    "cancelled": ["cancelled"],
    "error": ["error"],
    "idle": ["standby"],
}

DEFAULT_NOTIFICATIONS = {
    "enabled": True,
    "targets": [],
    "progress": True,
    "live_update": True,
    "min_step_pct": 1,
    "min_interval_s": 30,
    "on_complete": True,
    "on_cancelled": True,
    "on_error": True,
    "on_low_stock": True,
    "clear_after_min": 0,
    "progress_title": "", "progress_message": "",
    "complete_title": "", "complete_message": "",
    "cancelled_title": "", "cancelled_message": "",
    "error_title": "", "error_message": "",
    "low_stock_title": "", "low_stock_message": "",
}

TEXTS = {
    "nl": {
        "progress_title": "{printer}: {percent}%",
        "progress_message": "{filename} - nog {remaining}",
        "complete_title": "{printer}: print klaar",
        "complete_message": "{filename} ({length} m, {cost}). Persoon: {person}",
        "cancelled_title": "{printer}: print geannuleerd",
        "cancelled_message": "{filename} ({percent}% klaar, {length} m, {cost})",
        "error_title": "{printer}: fout tijdens print",
        "error_message": "{filename} ({percent}% klaar, {length} m, {cost})",
        "low_stock_title": "Filament bijna op: {filament}",
        "low_stock_message": "Nog {remaining} m over (grens: {limit} m)",
        "unknown": "onbekend",
    },
    "en": {
        "progress_title": "{printer}: {percent}%",
        "progress_message": "{filename} - {remaining} left",
        "complete_title": "{printer}: print finished",
        "complete_message": "{filename} ({length} m, {cost}). Person: {person}",
        "cancelled_title": "{printer}: print cancelled",
        "cancelled_message": "{filename} ({percent}% done, {length} m, {cost})",
        "error_title": "{printer}: print failed",
        "error_message": "{filename} ({percent}% done, {length} m, {cost})",
        "low_stock_title": "Filament almost empty: {filament}",
        "low_stock_message": "{remaining} m left (limit: {limit} m)",
        "unknown": "unknown",
    },
}

LENGTH_UNITS = {"mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0}
ENERGY_UNITS = {"wh": 0.001, "kwh": 1.0, "mwh": 1000.0}
TIME_UNITS = {"s": 1.0, "sec": 1.0, "min": 60.0, "h": 3600.0, "d": 86400.0}
