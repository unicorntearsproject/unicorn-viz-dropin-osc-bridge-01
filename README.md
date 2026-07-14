# osc-bridge-01 — OSC Control Surface (TouchOSC / Ableton / Max)

**Version 0.2.0**


Exposes unicorn-viz runtime tweakables over OSC so an external surface can drive
the show live. An inbound UDP server runs on a daemon thread and **only
enqueues** actions; they execute on the main render thread once per frame —
mirroring the MIDI callback discipline (no GL/app mutation off-thread).

## Controls

| Key | Action |
| --- | --- |
| `Ctrl+Shift+Alt+9` | Toggle the OSC bridge on/off |

## Configuration

```toml
[osc]
enabled = true         # load the drop-in (default true)
start_enabled = false  # UDP server unbound until Ctrl+Shift+Alt+9 / set true
host = "127.0.0.1"     # inbound bind address
port = 9000            # inbound port
feedback = false       # publish state out (bpm/beat)
send_host = "127.0.0.1"
send_port = 9001       # outbound feedback port
```

## Address scheme (inbound)

| Address | Args | Effect |
| --- | --- | --- |
| `/uv/reactivity` | `f` | Master audio reactivity |
| `/uv/speed` | `f` | Current effect speed |
| `/uv/zoom` | `f` | Current effect zoom |
| `/uv/effect/param` | `s f` | Named param on the current effect |
| `/uv/effect/param/<name>` | `f` | Same, name in the address |
| `/uv/effect/random` | — | Jump to a random effect |
| `/uv/effect/goto` | `s` | Jump to a named effect |
| `/uv/postfx/slot` | `i` | Trigger post-FX quick-hit slot (1–10) |
| `/uv/colorgrade/intensity` | `f` | Colour-grade intensity |
| `/uv/colorgrade/next` | — | Next colour-grade look |
| `/uv/colorgrade/enable` | `i` | Enable/disable colour grade |
| `/uv/audioout/filter` | `s f` | Audio-out filter (lpf/hpf/reverb_wet/…) |
| `/uv/audioout/sfx` | `[s]` | Trigger a folley SFX (random if omitted) |
| `/uv/beatflash/enable` | `i` | Enable/disable the strobe |
| `/uv/beatflash/intensity` | `f` | Strobe brightness (governor-capped) |

Outbound (when `feedback = true`): `/uv/state/bpm f`, `/uv/state/beat f`.

## Dependencies

`python-osc` (added to `requirements.txt`). The bridge degrades gracefully when
it is missing or the port is busy — it stays disabled and the app is unaffected.

## Notes

Other drop-ins are reached via the public `vj_api.get_subsystem(...)` surface
and the new `vj_api.set_effect_parameter()` / `get_effect_parameters()` methods,
so OSC never touches private app state.

See `docs/` for operations, configuration, integration, and troubleshooting.

## Changelog

- **0.2.0** — initial versioned release.
