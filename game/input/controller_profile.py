from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomllib


@dataclass(frozen=True)
class ControlDefinition:
    name: str
    index: int
    label: str | None = None

    def display_label(self) -> str:
        if self.label:
            return self.label
        return self.name.replace("_", " ").title()


@dataclass
class ControllerProfile:
    name: str
    deadzone: float
    buttons: dict[str, ControlDefinition]
    axes: dict[str, ControlDefinition]
    hats: dict[str, ControlDefinition]

    @classmethod
    def default(cls) -> ControllerProfile:
        return cls(
            name="Generic Controller",
            deadzone=0.20,
            buttons={},
            axes={},
            hats={},
        )

    @classmethod
    def from_toml(cls, path: str | Path) -> ControllerProfile:
        cfg_path = Path(path)
        with cfg_path.open("rb") as fh:
            data = tomllib.load(fh)

        name = str(data.get("name") or "Controller")
        deadzone = float(data.get("deadzone", 0.20))

        buttons = _parse_controls(data.get("buttons") or [])
        axes = _parse_controls(data.get("axes") or [])
        hats = _parse_controls(data.get("hats") or [])

        return cls(
            name=name,
            deadzone=deadzone,
            buttons=buttons,
            axes=axes,
            hats=hats,
        )

    def button_label(self, control: str | int) -> str:
        return self._control_label(self.buttons, control, prefix="Button")

    def axis_label(self, control: str | int) -> str:
        return self._control_label(self.axes, control, prefix="Axis")

    def hat_label(self, control: str | int) -> str:
        return self._control_label(self.hats, control, prefix="Hat")

    def button_index(self, name: str) -> int | None:
        definition = _lookup_control(self.buttons, name)
        return definition.index if definition is not None else None

    def axis_index(self, name: str) -> int | None:
        definition = _lookup_control(self.axes, name)
        return definition.index if definition is not None else None

    def hat_index(self, name: str) -> int | None:
        definition = _lookup_control(self.hats, name)
        return definition.index if definition is not None else None

    def _control_label(
        self,
        mapping: dict[str, ControlDefinition],
        control: str | int,
        *,
        prefix: str,
    ) -> str:
        definition = _lookup_control(mapping, control)
        if definition is None:
            if isinstance(control, int):
                return f"{prefix} {control}"
            return control.replace("_", " ").title()
        return f"{definition.display_label()} (#{definition.index})"


def _parse_controls(entries: Any) -> dict[str, ControlDefinition]:
    if isinstance(entries, dict):
        raise ValueError("Controls must be defined as an array of tables, not a dict")

    result: dict[str, ControlDefinition] = {}
    if not isinstance(entries, list):
        return result

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip().lower()
        if not name:
            continue
        idx = entry.get("index")
        if not isinstance(idx, int):
            continue
        label = entry.get("label")
        result[name] = ControlDefinition(
            name=name, index=idx, label=str(label) if label else None
        )
    return result


def _lookup_control(
    mapping: dict[str, ControlDefinition], control: str | int
) -> ControlDefinition | None:
    if isinstance(control, str):
        return mapping.get(control.strip().lower())
    if not isinstance(control, int):
        return None
    for definition in mapping.values():
        if definition.index == control:
            return definition
    return None
