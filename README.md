# Print Log

Home Assistant custom integration that logs your 3D prints (Moonraker/Klipper) per person, per persoonsrol and per filamentrol, with cost calculation and its own sidebar dashboard.

> Status: v0.1.0, first working version. Not yet tested on a live Home Assistant. Test on a copy first and keep a backup.

## Features
- Automatic logging when a print ends (`complete`, `cancelled`, `error`) based on three Moonraker entities.
- Local SQLite database in `/config/print_log/prints.db`.
- Filamentrollen with price per meter. Cost per print = length x price per meter (price is stored as a snapshot per print).
- People, persoonsrollen (default: familie, vrienden, extern) and filamentrollen, all editable in the panel.
- Sidebar panel: filters (person, role, filament, status, date, duration, text), sort, pagination, add/edit/delete, CSV export, bar charts and totals per person/role/filament/month.
- Writes (add/edit/delete) need a Home Assistant admin. Everybody with an account can read.
- Import of the old pyscript `/config/prints.db` (tables `rollen` and `prints`) on first start. The old file is never modified.
- Services: `print_log.add_print`, `print_log.set_current`. Sensors: total prints, total cost, total filament, last print.

## Install
1. HACS > Custom repositories > add this repo (category: Integration). HACS only works with public repositories.
   Or copy `custom_components/print_log` to `/config/custom_components/`.
2. Restart Home Assistant.
3. Settings > Devices & services > Add integration > Print Log. Pick the Moonraker print state, filename and "filament used" entities.
4. Open "Print log" in the sidebar. Choose person, role and filament under "Volgende print" before a print ends.

## How logging works
- State `printing` starts a session. The highest "filament used" value seen is kept (the sensor resets to 0 after a print).
- At `complete`, `cancelled`, `error` (or `standby` during a session) one row is written with the current "Volgende print" selection. Missing person/filament show a "kies" badge; edit the print afterwards.
- Cost for non-complete prints = filament cost x `failed_cost_pct` (setting, default 100).

## Cost
`total = (length_m x price_per_m + energy) x (1 + modifier_pct / 100)`. Modifier and energy columns exist but are not exposed in the UI yet (v0.1.0 starts with names only).

## Development
`pip install pytest` then `pytest` (cost and storage code has no Home Assistant imports).
