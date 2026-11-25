"""Constants for Print Log."""
DOMAIN = "print_log"
VERSION = "0.1.0"
PANEL_URL = "print-log"
STATIC_URL = "/print_log_static"
SIGNAL_UPDATED = "print_log_updated"
EVENT_PRINT_FINISHED = "print_log_print_finished"

CONF_STATE_ENTITY = "state_entity"
CONF_FILENAME_ENTITY = "filename_entity"
CONF_FILAMENT_ENTITY = "filament_entity"
CONF_LENGTH_UNIT = "length_unit"

END_STATES = {"complete": "complete", "cancelled": "cancelled", "error": "error"}
UNIT_FACTORS = {"mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0}
