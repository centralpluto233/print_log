# Print Log

[![hacs](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![release](https://img.shields.io/github/v/release/centralpluto233/print_log)](https://github.com/centralpluto233/print_log/releases)

Home Assistant integration that logs your 3D prints per person, role and filament roll, works out what each print costs, and lets you settle up with the people you print for. It has its own sidebar panel (English and Dutch) and works with Moonraker/Klipper or any printer integration that exposes a print state entity.

> Current version: **v0.3.2**. Keep a backup of `/config/print_log/` before upgrading, because the database schema is migrated on the first start of a new version.

## What it does

- **Automatic logging.** When a print ends (complete, cancelled or failed), it is saved to a local SQLite database at `/config/print_log/prints.db`.
- **Several printers.** Every printer has its own entities. Only the state entity is required. Filename, filament used, progress, time remaining and an energy counter (kWh or Wh, for example a Shelly plug) are optional.
- **Configurable states.** The state values that mean printing, paused, finished, cancelled, error and idle are editable per printer, so other integrations than Moonraker work too.
- **Costs.** Filament and electricity are calculated per print, and a margin can be added per role or per person.
- **Selling and profit.** Enter your own sale price per print, track what is paid, and see profit per print, person, role, filament, printer or month.
- **Settlements.** Pick a person, filter their open prints, tick the prints to settle now, round the amount up and save it. Unticked prints stay open for later.
- **Filament rolls.** Name, type (PLA, PETG, ...), brand, colour name and colour code, price per meter, and an optional remaining length with a low-stock warning.
- **Notifications.** Through the Companion app: one progress notification that updates in place, plus end notifications. Every part can be switched off and the texts are editable.
- **Statistics.** Filters, sorting, paging, CSV export, bar charts and totals.
- **Permissions.** Everybody with a Home Assistant account can read. Changes need an administrator.
- **Import.** Your old pyscript database `/config/prints.db` (tables `rollen` and `prints`) is imported on first start. The old file is never modified.

## Install

1. In HACS open **Custom repositories**, add `https://github.com/centralpluto233/print_log` with category **Integration**, download it and restart Home Assistant.
2. Go to **Settings > Devices & services > Add integration > Print Log** and pick the state entity (and optional entities) of your first printer.
3. Open **Print log** in the sidebar. Add printers, filament rolls and people there.
4. Before a print ends, choose person, role and filament under **Next print** at the top of the panel. The choice is used for the next print that finishes on that printer.

Upgrading from 0.1.x or 0.2.x needs nothing else. Your existing entities become the first printer and your existing data is kept.

## How costs, price and profit work

```
cost   = (length_m x price_per_m + kWh x price_per_kWh) x (1 + margin / 100)
price  = your sale price if you entered one, otherwise the cost above
profit = price - material cost - electricity cost
```

- **Margin.** A person can have their own margin. If the field is empty, the margin of their role is used. The margin that applied is stored on each print, so changing a margin later only affects new prints.
- **Failed or cancelled prints.** Material cost is scaled by the percentage you set in Settings (100% by default).
- **Electricity.** The kWh used is the difference of the energy counter during the print. The price is a fixed value or a price entity, and is stored per print.
- **Snapshots.** Filament price, margin and electricity price are copied onto the print when it is logged. Changing prices later does not rewrite your history.
- **Precision.** Amounts are stored as micro-euros (6 decimals). The price per meter can be entered with 6 decimals.

## Paid prints and settlements

On the **Prints** tab you can tick prints and mark them as paid or unpaid in bulk, filter on paid or unpaid, and enter a sale price per print.

On the **Settlements** tab:

1. Choose a person.
2. Narrow the list with a month, a from and to date, a filament or a search term.
3. Tick the prints you want to settle now. The count, calculated amount and profit follow your selection.
4. Round up to the cent, to 0.50 or to a whole euro, or type your own final amount. The difference with the calculated amount is shown and stored with the settlement.
5. Press **Settle**. The ticked prints are marked as paid and linked to the settlement.

A settlement can be undone from the history list, which makes its prints unpaid again. A print that belongs to a settlement cannot be set to unpaid by hand: undo the settlement instead.

## Filament stock

Fill in **Remaining length** on a roll and every new print on that roll is subtracted from it. A roll shows an "almost empty" label when it falls below the limit in Settings (50 m by default). Leave the field empty if you do not want to track a roll. Editing the remaining length sets a new starting point from that moment.

## Notifications

Open **Settings > Notifications**, choose the mobile app devices, then press **Send test notification**. You should see one notification that updates three times and ends with a final message. Progress notifications need a progress entity on the printer. Without it only the start and end notifications are sent.

## Entities and services

Sensors: **Total prints**, **Total cost**, **Total filament used** and **Last print**. The last print sensor has attributes for person, role, filament, status, length, cost and end time.

| Service | Purpose |
| --- | --- |
| `print_log.add_print` | Add a print by hand: `length_m` (required), `filename`, `printer`, `person`, `filament`, `role`, `status`, `notes`. |
| `print_log.set_current` | Set the person, role and filament for the next print: `printer`, `person`, `filament`, `role`. |
| `print_log.test_notification` | Send the test notification. |

People, roles, filaments and printers in services are given by name.

The panel uses a REST API under `/api/print_log/`. Reading needs a logged-in user and writing needs an administrator.

## Data and backups

Everything is in `/config/print_log/prints.db`. Copy that file to back up. CSV export is available from the Prints tab and respects the active filters.

## Roadmap

Ideas for v0.4.0, not final: print thumbnails, better charts, an export per settlement and a low-stock notification. Open an issue if something matters to you.

## Development

```
pip install pytest
pytest
```

Cost, storage and helper code has no Home Assistant imports, so it is tested without a running Home Assistant.

## License

MIT, see [LICENSE](LICENSE).
