from pl.costs import compute_costs, euro_to_micro, micro_to_euro


def test_basic_cost():
    r = compute_costs(10, euro_to_micro(0.04))
    assert r["total_cost_micro"] == 400_000
    assert micro_to_euro(r["total_cost_micro"]) == 0.4


def test_modifier_discount():
    r = compute_costs(10, euro_to_micro(0.04), modifier_pct=-20)
    assert r["total_cost_micro"] == 320_000


def test_failed_print_scaled():
    r = compute_costs(10, euro_to_micro(0.04), status="cancelled", failed_cost_pct=50)
    assert r["material_cost_micro"] == 200_000


def test_energy_included_in_modifier():
    r = compute_costs(10, euro_to_micro(0.04), energy_micro=100_000, modifier_pct=10)
    assert r["total_cost_micro"] == 550_000
