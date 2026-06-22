# osc-bridge-01 Configuration

Owner: Drop-in Maintainers
Status: active
Last updated: 2026-06-21

Keys live under `[osc]` in `config.toml`. All have safe defaults.

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `enabled` | bool | `true` | Load the drop-in at all |
| `start_enabled` | bool | `false` | Bind the UDP server at boot; else idle until `Ctrl+Shift+Alt+9` |
| `host` | str | `127.0.0.1` | Inbound bind address |
| `port` | int | `9000` | Inbound UDP port (1–65535) |
| `feedback` | bool | `false` | Publish `/uv/state/*` outbound |
| `send_host` | str | `127.0.0.1` | Outbound feedback host |
| `send_port` | int | `9001` | Outbound feedback port (1–65535) |

Bind to `0.0.0.0` only on trusted networks; OSC is unauthenticated. The default
loopback bind keeps the surface local to the machine.

Validation: `config_validator.py` flags non-boolean
`enabled`/`start_enabled`/`feedback`, non-string hosts, and out-of-range ports.

A documented copy lives in `config.full.example.toml`.
