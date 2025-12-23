from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class InputBinding:
    device: str
    control: str
    label: str | None = None
    modifiers: tuple[str, ...] = ()

    @classmethod
    def from_raw(cls, raw: InputBinding | dict[str, Any]) -> InputBinding:
        if isinstance(raw, cls):
            return raw
        if not isinstance(raw, dict):
            raise TypeError(
                f"InputBinding expects dict or InputBinding, got {type(raw)!r}"
            )

        device = str(raw.get("device") or "").strip()
        control = str(raw.get("control") or "").strip()
        if not device or not control:
            raise ValueError("InputBinding requires 'device' and 'control'")

        label = raw.get("label")
        if label is not None:
            label = str(label)

        modifiers_raw = raw.get("modifiers") or ()
        modifiers: tuple[str, ...]
        if isinstance(modifiers_raw, (list, tuple)):
            modifiers = tuple(str(m) for m in modifiers_raw)
        else:
            modifiers = (str(modifiers_raw),) if modifiers_raw else ()

        return cls(device=device, control=control, label=label, modifiers=modifiers)


@dataclass(frozen=True)
class ActionBinding:
    action: str
    bindings: tuple[InputBinding, ...]
    description: str = ""
    context: str = ""
    target: str = ""

    def with_defaults(
        self, *, context: str, default_target: str | None
    ) -> ActionBinding:
        ctx = self.context or context
        tgt = self.target or (default_target or "")
        return ActionBinding(
            action=self.action,
            description=self.description,
            bindings=self.bindings,
            context=ctx,
            target=tgt,
        )

    @classmethod
    def from_raw(
        cls,
        raw: ActionBinding | dict[str, Any],
        *,
        context: str,
        default_target: str | None,
    ) -> ActionBinding:
        if isinstance(raw, cls):
            return raw.with_defaults(context=context, default_target=default_target)
        if not isinstance(raw, dict):
            raise TypeError(
                f"ActionBinding expects dict or ActionBinding, got {type(raw)!r}"
            )

        action = str(raw.get("action") or "").strip()
        if not action:
            raise ValueError("ActionBinding requires 'action'")

        description = str(raw.get("description") or "").strip()
        target = str(raw.get("target") or "").strip()
        if not target:
            target = (default_target or "").strip()

        bindings_raw = raw.get("bindings") or ()
        if isinstance(bindings_raw, (list, tuple)):
            bindings_seq: Sequence[Any] = bindings_raw
        else:
            bindings_seq = (bindings_raw,)

        bindings = tuple(InputBinding.from_raw(b) for b in bindings_seq if b)
        if not bindings:
            raise ValueError(f"ActionBinding '{action}' requires at least one binding")

        return cls(
            action=action,
            description=description,
            bindings=bindings,
            context=context,
            target=target or "Unknown",
        )


def gather_input_actions(
    source: Any,
    *,
    context: str,
    default_target: str | None = None,
) -> list[ActionBinding]:
    raw_items = getattr(source, "INPUT_ACTIONS", None)
    if not raw_items:
        return []

    if default_target is None:
        cls = getattr(source, "__class__", None)
        if cls is not None and hasattr(cls, "__name__"):
            default_target = str(cls.__name__)

    actions: list[ActionBinding] = []
    for item in raw_items:
        action = ActionBinding.from_raw(
            item, context=context, default_target=default_target
        )
        actions.append(action)
    return actions
