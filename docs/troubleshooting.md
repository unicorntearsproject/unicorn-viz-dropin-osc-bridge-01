# osc-bridge-01 Troubleshooting

Owner: Drop-in Maintainers
Status: active
Last updated: 2026-06-21

## Bridge not receiving messages

- Confirm `[osc] enabled = true` (or press `Ctrl+Alt+9`).
- Confirm the sender targets the right `host:port` (default `127.0.0.1:9000`).
- If the controller is on another device, bind `host = "0.0.0.0"` (trusted
  networks only — OSC is unauthenticated) and check the firewall.

## "cannot bind" in the logs

The port is already in use (another OSC app, or a stale instance). Change
`port`, or free the port. The bridge disables itself rather than crashing.

## python-osc missing

`pip install python-osc` (it is in `requirements.txt`). Without it the bridge
logs a warning and stays disabled; the app is otherwise unaffected.

## Address has no effect

- Check the address against the README table (case-insensitive; trailing
  slashes are ignored).
- Subsystem-targeted addresses (`/uv/colorgrade/*`, `/uv/audioout/*`,
  `/uv/beatflash/*`) only act when that drop-in is loaded and registered.
- `/uv/postfx/slot 0` is ignored (slots are 1–10).

## Feedback (outbound) not arriving

Set `feedback = true` and confirm the receiver listens on
`send_host:send_port` (default `127.0.0.1:9001`).

## Tests

`tests/test_dispatch.py` verifies the full address→action mapping and queue
drain against a fake `vj_api` with no real socket.
