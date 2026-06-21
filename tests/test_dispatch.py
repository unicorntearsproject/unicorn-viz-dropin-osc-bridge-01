"""Dispatch/queue tests for osc-bridge-01 (no real socket).

These exercise the address→action mapping and the main-thread drain without
binding a UDP port, so they run anywhere.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MOD = Path(__file__).resolve().parents[1] / 'osc_bridge_controller.py'
_spec = importlib.util.spec_from_file_location('osc_bridge_controller_test', _MOD)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)
OscBridgeController = mod.OscBridgeController


class FakeSub:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.calls: list[tuple] = []

    def set_intensity(self, v):
        self.calls.append(('set_intensity', v))

    def next_grade(self):
        self.calls.append(('next_grade',))

    def set_filter(self, name, v):
        self.calls.append(('set_filter', name, v))

    def trigger_sfx(self, name=None):
        self.calls.append(('trigger_sfx', name))

    def toggle(self):
        self.enabled = not self.enabled
        self.calls.append(('toggle',))


class FakeVjApi:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.subs: dict = {}

    def set_reactivity(self, v):
        self.calls.append(('set_reactivity', v))

    def set_effect_parameter(self, name, v):
        self.calls.append(('set_effect_parameter', name, v))

    def goto_random_effect(self):
        self.calls.append(('goto_random_effect',))

    def goto_effect(self, name):
        self.calls.append(('goto_effect', name))

    def select_postfx_slot(self, slot):
        self.calls.append(('select_postfx_slot', slot))

    def get_subsystem(self, name):
        return self.subs.get(name)

    def auto_vj_snapshot(self):
        return {'bpm': 120.0}


class FakeApp:
    def __init__(self) -> None:
        self.vj_api = FakeVjApi()


@pytest.fixture
def bridge():
    app = FakeApp()
    c = OscBridgeController(app, {'enabled': False})  # no server
    return c, app


def _run(bridge, address, *args):
    c, app = bridge
    ok = c.dispatch_message(address, *args)
    c.process_pending_osc()
    return ok, app.vj_api


def test_reactivity(bridge):
    ok, vj = _run(bridge, '/uv/reactivity', 0.7)
    assert ok and ('set_reactivity', 0.7) in vj.calls


def test_speed_and_zoom_route_through_param(bridge):
    _run(bridge, '/uv/speed', 1.5)
    _run(bridge, '/uv/zoom', 2.0)
    vj = bridge[1].vj_api
    assert ('set_effect_parameter', 'speed', 1.5) in vj.calls
    assert ('set_effect_parameter', 'zoom', 2.0) in vj.calls


def test_effect_param_two_forms(bridge):
    _run(bridge, '/uv/effect/param', 'glow', 0.5)
    _run(bridge, '/uv/effect/param/glow', 0.25)
    vj = bridge[1].vj_api
    assert ('set_effect_parameter', 'glow', 0.5) in vj.calls
    assert ('set_effect_parameter', 'glow', 0.25) in vj.calls


def test_effect_random_and_goto(bridge):
    _run(bridge, '/uv/effect/random')
    _run(bridge, '/uv/effect/goto', 'Cube3D')
    vj = bridge[1].vj_api
    assert ('goto_random_effect',) in vj.calls
    assert ('goto_effect', 'Cube3D') in vj.calls


def test_postfx_slot(bridge):
    _run(bridge, '/uv/postfx/slot', 3)
    assert ('select_postfx_slot', 3) in bridge[1].vj_api.calls


def test_postfx_slot_zero_ignored(bridge):
    ok, vj = _run(bridge, '/uv/postfx/slot', 0)
    assert ok is False


def test_colorgrade_and_audioout_subsystems(bridge):
    c, app = bridge
    cg = FakeSub()
    ao = FakeSub()
    app.vj_api.subs = {'color_grade': cg, 'audio_out': ao}
    _run(bridge, '/uv/colorgrade/intensity', 0.4)
    _run(bridge, '/uv/colorgrade/next')
    _run(bridge, '/uv/audioout/filter', 'lpf', 800.0)
    _run(bridge, '/uv/audioout/sfx', 'clap')
    assert ('set_intensity', 0.4) in cg.calls
    assert ('next_grade',) in cg.calls
    assert ('set_filter', 'lpf', 800.0) in ao.calls
    assert ('trigger_sfx', 'clap') in ao.calls


def test_beatflash_enable_toggles_when_state_differs(bridge):
    c, app = bridge
    bf = FakeSub(enabled=False)
    app.vj_api.subs = {'beat_flash': bf}
    _run(bridge, '/uv/beatflash/enable', 1)
    assert bf.enabled is True
    # Already enabled: enabling again must NOT toggle.
    _run(bridge, '/uv/beatflash/enable', 1)
    assert bf.enabled is True


def test_unknown_address_not_queued(bridge):
    c, app = bridge
    assert c.dispatch_message('/nope/whatever', 1.0) is False
    assert c.process_pending_osc() == 0


def test_process_pending_returns_count(bridge):
    c, app = bridge
    c.dispatch_message('/uv/reactivity', 0.1)
    c.dispatch_message('/uv/reactivity', 0.2)
    assert c.process_pending_osc() == 2
    assert c.process_pending_osc() == 0


def test_missing_subsystem_is_safe(bridge):
    # No subsystems registered — actions resolve but do nothing, no error.
    _run(bridge, '/uv/colorgrade/intensity', 0.4)
    assert bridge[1].vj_api.subs == {}


def test_snapshot_shape(bridge):
    snap = bridge[0].snapshot()
    assert {'enabled', 'host', 'port', 'feedback', 'queued'} <= set(snap)
