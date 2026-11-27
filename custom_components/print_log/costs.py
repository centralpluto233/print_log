"""Cost calculation. Pure Python (no Home Assistant imports) so it is easy to test."""
from __future__ import annotations

MICRO = 1_000_000
CENT_MICRO = 10_000


def euro_to_micro(value: float) -> int:
    return int(round(float(value) * MICRO))


def micro_to_euro(value: int | None) -> float:
    return round((value or 0) / MICRO, 6)


def round_up_micro(value: int, step_micro: int = CENT_MICRO) -> int:
    """Round a micro-euro amount up to a multiple of step_micro (default: a whole cent)."""
    step = max(1, int(step_micro))
    return -(-int(value) // step) * step


def compute_costs(
    length_m: float,
    price_per_m_micro: int,
    *,
    energy_micro: int = 0,
    modifier_pct: float = 0.0,
    status: str = "complete",
    failed_cost_pct: float = 100.0,
) -> dict[str, int]:
    """Return material/energy/total cost in micro-euro.

    total = (material + energy) * (1 + modifier/100)
    For non-complete prints the material cost is scaled by failed_cost_pct.
    """
    material = float(length_m or 0) * int(price_per_m_micro or 0)
    if status != "complete":
        material *= float(failed_cost_pct) / 100.0
    material_i = int(round(material))
    energy_i = int(energy_micro or 0)
    total = (material_i + energy_i) * (1 + float(modifier_pct or 0) / 100.0)
    return {
        "material_cost_micro": material_i,
        "energy_cost_micro": energy_i,
        "total_cost_micro": int(round(total)),
    }
