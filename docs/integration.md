# osc-bridge-01 Integration

Owner: Drop-in Maintainers
Status: active
Last updated: 2026-06-21

## Load path

`app.py` loads the controller via `_load_osc_bridge_controller_class()` →
`load_dropin_symbol('osc-bridge-01/osc_bridge_controller.py',
'OscBridgeController')` inside a `try/except` that sets `self._osc_bridge = None`
on failure. The app starts cleanly when the drop-in or `python-osc` is absent.

## Public-surface usage

The bridge maps OSC addresses onto the **public** runtime surface only:

- Core controls: `vj_api.set_reactivity`, `set_effect_parameter` /
  `get_effect_parameters` (added with this drop-in), `goto_random_effect`,
  `goto_effect`, `select_postfx_slot`.
- Other drop-ins: via `vj_api.get_subsystem('color_grade' | 'audio_out' |
  'beat_flash')` and their public methods.

It never touches `app._private` state, satisfying the public-runtime-surface
rules. `set_effect_parameter` / `get_effect_parameters` were promoted to
`VJApi` precisely so OSC (and later the control room) could enumerate and set
live effect parameters without reaching into the current effect.

## Thread model

Inbound OSC handlers run on the server daemon thread and only append a deferred
action (a closure) to a `deque`. `App` ticks `update(dt, audio)` each frame,
which calls `process_pending_osc()` to execute those closures on the main
thread. This is the same discipline as `hotkeys.process_pending_midi()`.

## Resolution is unit-tested

`dispatch_message(address, *args)` resolves + enqueues and is covered by
`tests/test_dispatch.py` against a fake `vj_api` — no socket required, so the
address scheme is verified deterministically.
