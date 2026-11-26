# Print Log

Home Assistant custom integration that logs 3D prints per person, per persoonsrol and per filament roll, with cost calculation (filament and electricity), notifications and its own sidebar panel. Works with Moonraker/Klipper and with any other printer integration that exposes a state entity.

> Status: v0.2.0. Test on a copy first and keep a backup of `/config/print_log/`.

## Features
- One or more printers, each with its own entities. Only the state entity is required; filename, filament used, progress, time remaining and an energy counter (kWh or Wh, e.g. Shelly) are optional.
- Configurable state values per printer, so other integrations than Moonraker work too.
- Automatic logging at the end of a print (complete, cancelled, error) into a local SQLite database in `/config/print_log/prints.db`.
- Cost per print = (length x price per meter + electricity) x (1 + modifier). Prices are stored per print as a snapshot.
- Electricity cost from the energy counter difference during the print, with a fixed price or a price entity.
- Notifications through the Companion app: one progress notification that is updated in place (same tag, live update on Android 16+/iOS 17.2+), plus end notifications. Every part can be switched off, texts are editable, targets are chosen in the panel.
- Sidebar panel in English and Dutch, with a light/dark/auto theme per user (saved in your Home Assistant account).
- Filters, sorting, paging, add/edit/delete, CSV export, bar charts and totals per person, role, filament, printer, month or status.
- Writes need a Home Assistant admin; everybody with an account can read.
- Import of the old pyscript `/config/prints.db` (tables `rollen` and `prints`) on first start. The old file is never modified.
- Services: `print_log.add_print`, `print_log.set_current`, `print_log.test_notification`.

## Install
1. HACS > Custom repositories > add this repo (category: Integration), download, restart Home Assistant.
2. Settings > Devices & services > Add integration > Print Log. Pick the state entity (and optional entities) of your first printer.
3. Open "Print log" in the sidebar. Add more printers, filaments and people there. Choose person, role and filament under "Next print" before a print ends.

Upgrading from 0.1.x: your existing entities become the first printer automatically (name "Printer"). Nothing else is required.

## Notifications
Settings tab > Notifications. Pick the mobile app devices to notify, then press "Send test notification": you should see one notification that updates 3 times and ends with a final message. Progress notifications need a progress entity on the printer; without it only the start and end notifications are sent.

## Cost
`total = (length_m x price_per_m + kWh x price_per_kWh) x (1 + modifier_pct / 100)`. The modifier column exists but is not exposed in the UI yet. Planned: v0.3.0 filament stock, margin, selling price, profit, paid flag and settlements; v0.4.0 thumbnails and better charts.

## Development
`pip install pytest` then `pytest`. Cost, storage and helper code has no Home Assistant imports.
