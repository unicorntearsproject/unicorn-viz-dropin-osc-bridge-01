"""Optional config validation for the osc-bridge-01 drop-in."""
from __future__ import annotations

from typing import Any


def validate_config(config_data: dict[str, Any]) -> list[str]:
    """Validate the ``[osc]`` section, returning any error strings."""
    errors: list[str] = []
    section = config_data.get('osc')
    if section is None:
        return errors
    if not isinstance(section, dict):
        return ['[osc] must be a table']

    for key in ('enabled', 'start_enabled', 'feedback'):
        if key in section and not isinstance(section[key], bool):
            errors.append(f'[osc] {key} must be a boolean')

    for key in ('host', 'send_host'):
        if key in section and not isinstance(section[key], str):
            errors.append(f'[osc] {key} must be a string')

    for key in ('port', 'send_port'):
        val = section.get(key)
        if val is not None:
            if not isinstance(val, int):
                errors.append(f'[osc] {key} must be an integer')
            elif not (1 <= val <= 65535):
                errors.append(f'[osc] {key} must be in 1..65535')

    return errors
