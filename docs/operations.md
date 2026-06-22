# osc-bridge-01 Operations

Owner: Drop-in Maintainers
Status: active
Last updated: 2026-06-21

## Purpose

Expose runtime tweakables over OSC for external control surfaces (TouchOSC,
Ableton, Max).

## Lifecycle

- Loaded by `app.py` when `[osc] enabled = true`.
- Registered as the `osc` subsystem + key handler.
- Ticked each frame via `update(dt, audio)`, which drains the inbound queue
  (`process_pending_osc`) and publishes optional feedback.
- Torn down by the generic subsystem shutdown loop (`shutdown()` is idempotent).

## Live operation

- `Ctrl+Shift+Alt+9` toggles the bridge at runtime.
- Send OSC to `host:port` (default `127.0.0.1:9000`). See the README for the
  address scheme.

## Threading

The OSC server runs on a daemon thread and only appends resolved actions to a
`deque`. All app/GL interaction happens on the main thread during
`process_pending_osc`.

## Quick test

```bash
python -c "from pythonosc.udp_client import SimpleUDPClient; \
SimpleUDPClient('127.0.0.1', 9000).send_message('/uv/reactivity', 0.7)"
```
