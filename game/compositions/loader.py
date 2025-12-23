from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
from typing import Any, Iterator, Literal

import pygame

NodeKind = Literal["entity", "environment"]


@dataclass
class CompositionNode:
    id: str
    kind: NodeKind
    type_path: str
    parent: str | None
    children: list[str]
    instance: Any


@dataclass
class CompositionRuntime:
    nodes: dict[str, CompositionNode]
    ordered_ids: list[str]
    interactions: list[dict[str, Any]]
    canvas_size: tuple[int, int]
    origin: pygame.Vector2

    def iter_nodes(self, kind: NodeKind | None = None) -> Iterator[CompositionNode]:
        for node_id in self._iter_tree_ids():
            node = self.nodes[node_id]
            if kind is not None and node.kind != kind:
                continue
            yield node

    def iter_instances(self, kind: NodeKind | None = None) -> Iterator[Any]:
        for node in self.iter_nodes(kind):
            yield node.instance

    def _iter_tree_ids(self) -> Iterator[str]:
        roots = [
            node_id
            for node_id in self.ordered_ids
            if self.nodes[node_id].parent is None
        ]

        def _visit(node_id: str):
            yield node_id
            for child_id in self.nodes[node_id].children:
                yield from _visit(child_id)

        for root_id in roots:
            yield from _visit(root_id)


def load_composition(path: str | Path) -> CompositionRuntime:
    file_path = Path(path)
    data = json.loads(file_path.read_text(encoding="utf-8"))

    canvas_size, origin = _parse_scene_block(data.get("scene"))

    version = int(data.get("version", 0))
    if version != 1:
        raise ValueError(f"Unsupported composition version: {version}")

    nodes_data = data.get("nodes", [])
    if not isinstance(nodes_data, list):
        raise ValueError("nodes must be a list")

    ordered_ids: list[str] = []
    nodes: dict[str, CompositionNode] = {}
    for entry in nodes_data:
        node_id = str(entry.get("id", "")).strip()
        if not node_id:
            raise ValueError("Each node requires a non-empty id")
        if node_id in nodes:
            raise ValueError(f"Duplicated node id: {node_id}")

        kind = entry.get("kind")
        if kind not in ("entity", "environment"):
            raise ValueError(f"Invalid node kind for {node_id}: {kind}")

        type_path = entry.get("type")
        if not type_path:
            raise ValueError(f"Node {node_id} is missing 'type'")

        parent = entry.get("parent")
        transform = entry.get("transform", {})
        state = entry.get("state", {})

        instance = _instantiate_type(type_path, transform, state)
        nodes[node_id] = CompositionNode(
            id=node_id,
            kind=kind,
            type_path=type_path,
            parent=parent,
            children=[],
            instance=instance,
        )
        ordered_ids.append(node_id)

    _build_children(nodes, ordered_ids)
    _validate_parentage(nodes)

    interactions = data.get("interactions") or []
    if not isinstance(interactions, list):
        raise ValueError("interactions must be a list")

    return CompositionRuntime(
        nodes=nodes,
        ordered_ids=ordered_ids,
        interactions=interactions,
        canvas_size=canvas_size,
        origin=origin,
    )


def _instantiate_type(
    type_path: str, transform: dict[str, Any], state: dict[str, Any]
) -> Any:
    cls = _resolve_type(type_path)
    pos = _vector_from(transform.get("position")) or pygame.Vector2(0, 0)

    try:
        instance = cls(pygame.Vector2(pos))
    except TypeError:
        instance = cls()

    _apply_transform(instance, transform, default_pos=pos)
    _apply_state(instance, state)
    return instance


def _resolve_type(type_path: str) -> type:
    module_name, _, attr = type_path.rpartition(".")
    if not module_name:
        raise ValueError(f"Invalid type path: {type_path}")
    module = importlib.import_module(module_name)
    try:
        return getattr(module, attr)
    except AttributeError as exc:
        raise ValueError(f"Type {type_path} not found") from exc


def _build_children(nodes: dict[str, CompositionNode], ordered_ids: list[str]) -> None:
    order_index = {node_id: idx for idx, node_id in enumerate(ordered_ids)}
    for node in nodes.values():
        node.children.clear()

    for node_id, node in nodes.items():
        parent_id = node.parent
        if parent_id is None:
            continue
        if parent_id not in nodes:
            raise ValueError(f"Parent '{parent_id}' of node '{node_id}' is not defined")
        nodes[parent_id].children.append(node_id)

    for node in nodes.values():
        node.children.sort(key=lambda cid: order_index[cid])


def _validate_parentage(nodes: dict[str, CompositionNode]) -> None:
    for node in nodes.values():
        parent_id = node.parent
        if node.kind == "entity":
            if parent_id is None:
                raise ValueError(
                    f"Entity '{node.id}' must be parented to an environment"
                )
            parent = nodes[parent_id]
            if parent.kind != "environment":
                raise ValueError(
                    f"Entity '{node.id}' must live inside an environment (parent: {parent_id})"
                )
            continue

        if node.kind == "environment":
            if parent_id is None:
                continue
            parent = nodes[parent_id]
            if parent.kind != "entity":
                raise ValueError(
                    f"Environment '{node.id}' can only hang from the root or an entity"
                )


def _apply_transform(
    instance: Any, transform: dict[str, Any], default_pos: pygame.Vector2
) -> None:
    position = transform.get("position")
    if position is not None:
        vec = _vector_from(position) or default_pos
    else:
        vec = default_pos

    if hasattr(instance, "pos"):
        setattr(instance, "pos", pygame.Vector2(vec))

    rotation = transform.get("rotation")
    if rotation is not None and hasattr(instance, "rotation"):
        setattr(instance, "rotation", float(rotation))

    scale = transform.get("scale")
    if scale is not None and hasattr(instance, "scale"):
        scale_vec = _vector_from(scale)
        if scale_vec is not None:
            setattr(instance, "scale", scale_vec)


def _apply_state(instance: Any, state: dict[str, Any]) -> None:
    for key, value in state.items():
        current = getattr(instance, key, None)
        coerced = _coerce_state_value(value, current)
        setattr(instance, key, coerced)


def _coerce_state_value(value: Any, current: Any) -> Any:
    if isinstance(current, pygame.Vector2):
        vec = _vector_from(value)
        if vec is not None:
            return vec
    if isinstance(current, str):
        return value if isinstance(value, str) else current
    if (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(n, (int, float)) for n in value)
    ):
        vec = _vector_from(value)
        if vec is not None and current is None:
            return vec
    return value


def _parse_scene_block(raw_scene: Any) -> tuple[tuple[int, int], pygame.Vector2]:
    scene = raw_scene if isinstance(raw_scene, dict) else {}
    canvas = _parse_canvas_size(scene.get("canvas"))
    origin_vec = _vector_from(scene.get("origin"))
    if origin_vec is None:
        origin_vec = pygame.Vector2(0, 0)
    return canvas, origin_vec


def _parse_canvas_size(raw: Any) -> tuple[int, int]:
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        w, h = raw
        if isinstance(w, (int, float)) and isinstance(h, (int, float)):
            width = max(1, int(round(w)))
            height = max(1, int(round(h)))
            return width, height
    return 1028, 720


def _vector_from(raw: Any) -> pygame.Vector2 | None:
    if isinstance(raw, pygame.Vector2):
        return pygame.Vector2(raw)
    if isinstance(raw, (tuple, list)) and len(raw) == 2:
        x, y = raw
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            return pygame.Vector2(float(x), float(y))
    return None
