"""osc-bridge-01's Control Room operator panel (P1 of
docs/planning/control-room-drop-in-integration-plan-2026-09-05.md).
Hermetic: real OscBridgeController with start_enabled=False (no socket),
a fake app/vj_api carrying an in-memory registry."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from unicornviz.operator_panels import OperatorPanel, PanelContent

_MOD = Path(__file__).resolve().parents[1] / 'osc_bridge_controller.py'
_spec = importlib.util.spec_from_file_location('osc_bridge_controller_panel_test', _MOD)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)
OscBridgeController = mod.OscBridgeController


class _FakeVJApi:
    def __init__(self) -> None:
        self.panels: dict[str, OperatorPanel] = {}

    def register_midi_actions(self, section, actions) -> None:
        pass

    def register_midi_action_handler(self, action, fn) -> None:
        pass

    def register_operator_panel(self, panel: OperatorPanel) -> None:
        self.panels[panel.name] = panel


class _FakeApp:
    def __init__(self) -> None:
        self.vj_api = _FakeVJApi()


def _controller() -> tuple[OscBridgeController, _FakeApp]:
    app = _FakeApp()
    return OscBridgeController(app, {'start_enabled': False, 'host': '10.0.0.5', 'port': 9123}), app


def test_init_registers_the_panel_on_the_output_page() -> None:
    c, app = _controller()
    panel = app.vj_api.panels['osc']
    assert panel.title == 'OSC Bridge' and panel.page == 'output' and panel.size == 'small'
    assert panel.content == c._operator_panel_content and 'toggle' in panel.tooltips


def test_content_mirrors_snapshot() -> None:
    c, _ = _controller()
    c._last_address = '/unicorn/fx/next'
    content = c._operator_panel_content()
    assert isinstance(content, PanelContent)
    assert content.status == 'OFF'
    by_label = {r.label: r.value for r in content.rows}
    assert by_label['Listen'] == '10.0.0.5:9123'
    assert by_label['Last'] == '/unicorn/fx/next' and by_label['Queued'] == '0'
    assert content.buttons[0].active is False


def test_toggle_action_uses_toggle_enabled_and_flashes_like_the_hotkey(monkeypatch) -> None:
    c, _ = _controller()
    monkeypatch.setattr(c, 'toggle_enabled', lambda: True)
    assert c._operator_panel_action('toggle', None) == 'OSC bridge on'
    monkeypatch.setattr(c, 'toggle_enabled', lambda: False)
    assert c._operator_panel_action('toggle', None) == 'OSC bridge off'
    assert c._operator_panel_action('nope', None) is None
