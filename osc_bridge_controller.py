"""OSC control-surface bridge for unicorn-viz (osc-bridge-01).

Exposes runtime tweakables over OSC so TouchOSC / Ableton / Max can drive the
show.  An inbound OSC UDP server runs on a daemon thread and **only enqueues**
actions; they are executed on the main render thread via
:meth:`process_pending_osc` (drained once per frame).  This mirrors the MIDI
callback discipline — no GL/SDL/app mutation from the network thread.

Address scheme (inbound)::

    /uv/reactivity            f      master audio reactivity
    /uv/speed                 f      current effect speed
    /uv/zoom                  f      current effect zoom
    /uv/effect/param  <name>  f      named param on the current effect
    /uv/effect/param/<name>   f      (name embedded in the address)
    /uv/effect/random                jump to a random effect
    /uv/effect/goto   <name>         jump to a named effect
    /uv/postfx/slot           i      trigger a post-FX quick-hit slot (1..10)
    /uv/colorgrade/intensity  f      colour-grade intensity
    /uv/colorgrade/next              next colour-grade look
    /uv/colorgrade/enable     i      enable/disable colour grade
    /uv/audioout/filter <name> f     audio-out filter (lpf/hpf/reverb_wet/…)
    /uv/audioout/sfx [name]          trigger a folley SFX (random if omitted)
    /uv/beatflash/enable      i      enable/disable the strobe
    /uv/beatflash/intensity   f      strobe brightness ceiling (governor-capped)

Optional outbound feedback publishes ``/uv/state/bpm`` and ``/uv/state/beat``
for controller displays.

The bridge degrades gracefully: if ``python-osc`` is missing or the port is in
use, it stays alive disabled and the app is unaffected.
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Any, Callable

log = logging.getLogger(__name__)


DROPIN_CAPABILITIES = {
    'name': 'osc',
    'class_symbol': 'OscBridgeController',
    'subsystem_name': 'osc',
    'key_handler_attr': 'handle_key',
}

HELP_ENTRIES = [
    ('OSC', 'Ctrl+Alt+9', 'Toggle OSC control bridge on/off'),
]


def _to_float(args: tuple, default: float = 0.0) -> float:
    try:
        return float(args[0])
    except (IndexError, ValueError, TypeError):
        return default


def _to_int(args: tuple, default: int = 0) -> int:
    try:
        return int(float(args[0]))
    except (IndexError, ValueError, TypeError):
        return default


def _to_str(args: tuple, default: str = '') -> str:
    try:
        return str(args[0])
    except (IndexError, TypeError):
        return default


class OscBridgeController:
    """Bidirectional OSC bridge exposing runtime tweakables.

    Thread-safety: the OSC server thread only appends to a ``deque``; all app
    interaction happens on the main thread in :meth:`process_pending_osc`.
    """

    def __init__(self, app: Any, cfg: dict[str, Any] | None = None) -> None:
        self._app = app
        self._cfg = dict(cfg or {})
        self.enabled = bool(self._cfg.get('enabled', False))

        self._host = str(self._cfg.get('host', '127.0.0.1') or '127.0.0.1')
        self._port = int(self._cfg.get('port', 9000) or 9000)
        self._send_host = str(self._cfg.get('send_host', '127.0.0.1') or '127.0.0.1')
        self._send_port = int(self._cfg.get('send_port', 9001) or 9001)
        self._feedback = bool(self._cfg.get('feedback', False))

        self._queue: deque[Callable[[], None]] = deque()
        self._server: Any = None
        self._server_thread: threading.Thread | None = None
        self._client: Any = None
        self._available = False
        self._status = 'osc off'
        self._last_address = ''

        if self.enabled:
            self._start()

    # ---------------------------------------------------------------- server
    def _start(self) -> None:
        try:
            from pythonosc.dispatcher import Dispatcher  # noqa: PLC0415
            from pythonosc.osc_server import ThreadingOSCUDPServer  # noqa: PLC0415
            from pythonosc.udp_client import SimpleUDPClient  # noqa: PLC0415
        except Exception as exc:
            log.warning('osc-bridge: python-osc unavailable, disabling: %s', exc)
            self.enabled = False
            return

        dispatcher = Dispatcher()
        dispatcher.set_default_handler(self._on_osc)
        try:
            self._server = ThreadingOSCUDPServer((self._host, self._port), dispatcher)
        except Exception as exc:
            log.warning('osc-bridge: cannot bind %s:%d, disabling: %s', self._host, self._port, exc)
            self._server = None
            self.enabled = False
            return

        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            name='osc-bridge',
            daemon=True,
        )
        self._server_thread.start()
        if self._feedback:
            try:
                self._client = SimpleUDPClient(self._send_host, self._send_port)
            except Exception as exc:
                log.warning('osc-bridge: feedback client init failed: %s', exc)
                self._client = None
        self._available = True
        self._status = f'osc on {self._host}:{self._port}'
        log.info('osc-bridge: listening on %s:%d', self._host, self._port)

    def _on_osc(self, address: str, *args: Any) -> None:
        """OSC server-thread callback — resolve + enqueue, never act here."""
        action = self._resolve(address, args)
        if action is not None:
            self._queue.append(action)

    # ------------------------------------------------------------- dispatch
    def dispatch_message(self, address: str, *args: Any) -> bool:
        """Resolve and enqueue an OSC message (used by the server and by tests).

        Returns True when the address mapped to an action.
        """
        action = self._resolve(address, args)
        if action is None:
            return False
        self._queue.append(action)
        return True

    def _resolve(self, address: str, args: tuple) -> Callable[[], None] | None:
        """Map an OSC address+args to a deferred main-thread action."""
        addr = address.strip().lower().rstrip('/')
        self._last_address = address
        vj = self._app.vj_api

        if addr == '/uv/reactivity':
            v = _to_float(args)
            return lambda: vj.set_reactivity(v)
        if addr == '/uv/speed':
            v = _to_float(args)
            return lambda: vj.set_effect_parameter('speed', v)
        if addr == '/uv/zoom':
            v = _to_float(args)
            return lambda: vj.set_effect_parameter('zoom', v)
        if addr == '/uv/effect/random':
            return lambda: vj.goto_random_effect()
        if addr == '/uv/effect/goto':
            name = _to_str(args)
            return (lambda: vj.goto_effect(name)) if name else None
        if addr == '/uv/effect/param':
            # /uv/effect/param  <name> <value>
            if len(args) >= 2:
                name = _to_str((args[0],))
                v = _to_float((args[1],))
                return lambda: vj.set_effect_parameter(name, v)
            return None
        if addr.startswith('/uv/effect/param/'):
            name = addr.rsplit('/', 1)[-1]
            v = _to_float(args)
            return lambda: vj.set_effect_parameter(name, v)
        if addr == '/uv/postfx/slot':
            slot = _to_int(args)
            return (lambda: vj.select_postfx_slot(slot)) if slot else None
        if addr == '/uv/colorgrade/intensity':
            v = _to_float(args)
            return lambda: self._subsystem_call('color_grade', 'set_intensity', v)
        if addr == '/uv/colorgrade/next':
            return lambda: self._subsystem_call('color_grade', 'next_grade')
        if addr == '/uv/colorgrade/enable':
            on = _to_int(args) != 0
            return lambda: self._set_enabled('color_grade', on)
        if addr == '/uv/audioout/filter':
            if len(args) >= 2:
                name = _to_str((args[0],))
                v = _to_float((args[1],))
                return lambda: self._subsystem_call('audio_out', 'set_filter', name, v)
            return None
        if addr == '/uv/audioout/sfx':
            name = _to_str(args) or None
            return lambda: self._subsystem_call('audio_out', 'trigger_sfx', name)
        if addr == '/uv/beatflash/enable':
            on = _to_int(args) != 0
            return lambda: self._set_enabled('beat_flash', on)
        if addr == '/uv/beatflash/intensity':
            v = _to_float(args)
            return lambda: self._beatflash_set_brightness(v)
        return None

    def _subsystem_call(self, name: str, method: str, *args: Any) -> Any:
        sub = self._app.vj_api.get_subsystem(name)
        if sub is None:
            return None
        fn = getattr(sub, method, None)
        if callable(fn):
            return fn(*args)
        return None

    def _set_enabled(self, name: str, on: bool) -> None:
        sub = self._app.vj_api.get_subsystem(name)
        if sub is None:
            return
        if bool(getattr(sub, 'enabled', not on)) != on and hasattr(sub, 'toggle'):
            sub.toggle()

    def _beatflash_set_brightness(self, value: float) -> None:
        sub = self._app.vj_api.get_subsystem('beat_flash')
        gov = getattr(sub, '_governor', None) if sub is not None else None
        if gov is not None and hasattr(gov, 'set_max_brightness'):
            gov.set_max_brightness(value)

    # ------------------------------------------------------------- app hooks
    def process_pending_osc(self) -> int:
        """Execute queued OSC actions on the main thread. Returns count run."""
        count = 0
        while self._queue:
            action = self._queue.popleft()
            try:
                action()
                count += 1
            except Exception as exc:
                log.warning('osc-bridge: action failed: %s', exc)
        return count

    def update(self, dt: float, audio: Any) -> None:  # noqa: ARG002
        """Per-frame tick: drain inbound queue and publish optional feedback."""
        self.process_pending_osc()
        if self._available and self._feedback and self._client is not None:
            try:
                snap = self._app.vj_api.auto_vj_snapshot()
                bpm = float(snap.get('bpm', 0.0)) if isinstance(snap, dict) else 0.0
                self._client.send_message('/uv/state/bpm', bpm)
                self._client.send_message('/uv/state/beat', float(getattr(audio, 'beat', 0.0) or 0.0))
            except Exception as exc:
                log.debug('osc-bridge: feedback send failed: %s', exc)

    @property
    def status_text(self) -> str:
        return self._status

    def snapshot(self) -> dict[str, Any]:
        return {
            'enabled': bool(self.enabled and self._available),
            'host': self._host,
            'port': self._port,
            'feedback': self._feedback,
            'queued': len(self._queue),
            'last_address': self._last_address,
        }

    def toggle_enabled(self) -> bool:
        if self.enabled:
            self.shutdown()
            self.enabled = False
            self._status = 'osc off'
        else:
            self.enabled = True
            self._start()
        return self.enabled and self._available

    def handle_key(self, sym: int, mod: int) -> 'str | None | bool':
        """Ctrl+Alt+9 toggles the OSC bridge."""
        import sdl2  # noqa: PLC0415
        if (mod & sdl2.KMOD_CTRL) and (mod & sdl2.KMOD_ALT) and sym == sdl2.SDLK_9:
            on = self.toggle_enabled()
            return f'OSC bridge {"on" if on else "off"}'
        return False

    def shutdown(self) -> None:
        """Stop the OSC server and release resources (idempotent)."""
        server = self._server
        self._server = None
        self._available = False
        if server is not None:
            try:
                server.shutdown()
                server.server_close()
            except Exception as exc:
                log.warning('osc-bridge: shutdown error: %s', exc)
        self._server_thread = None
        self._client = None
        self._queue.clear()
