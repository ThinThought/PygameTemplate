from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

import json

import pygame

from game.compositions import CompositionRuntime

from .registry import PaletteRegistry, PaletteKind, PaletteItem

NodeKind = Literal["root", "entity", "environment"]


@dataclass
class Node:
    id: int
    kind: NodeKind
    name: str
    base_name: str
    payload: Any | None
    parent: int | None
    children: list[int] = field(default_factory=list)
    composition_id: str = ""

    def position(self) -> pygame.Vector2 | None:
        if self.payload is None:
            return None
        pos = getattr(self.payload, "pos", None)
        return pygame.Vector2(pos) if pos is not None else None

    def radius(self) -> float:
        if self.payload is None:
            return 0.0
        return float(getattr(self.payload, "radius", 0.0))


class EditorModel:
    """Modelo jerárquico al estilo Godot para entornos/entidades."""

    def __init__(self, registry: PaletteRegistry) -> None:
        self.registry = registry
        self._initialize_state()

    def _initialize_state(self) -> None:
        self.nodes: dict[int, Node] = {}
        self._order: list[int] = []
        self._label_counts: dict[str, int] = {}
        self._composition_id_counts: dict[PaletteKind, int] = {
            "entity": 0,
            "environment": 0,
        }
        self._next_id = 1
        self.root_id = self._create_root()
        self.selected_id: int | None = None

    def _reset_state(self) -> None:
        self._initialize_state()

    # ---------- Creación ----------

    def spawn_from_palette(
        self,
        kind: PaletteKind,
        idx: int,
        position: tuple[int, int],
        parent_hint: int | None = None,
    ) -> Node | None:
        item = self.registry.get_item(kind, idx)
        if item is None:
            return None

        parent_id = self._resolve_parent(kind, parent_hint)
        if parent_id is None:
            return None

        node = self._create_node(item, position, parent_id)
        self._insert_order(node.id)
        self._attach_child(parent_id, node.id)
        self.selected_id = node.id
        return node

    def spawn_from_palette_relative(
        self,
        kind: PaletteKind,
        idx: int,
        position: tuple[int, int],
        reference_id: int,
        *,
        before: bool,
    ) -> Node | None:
        item = self.registry.get_item(kind, idx)
        if item is None:
            return None

        reference = self.nodes.get(reference_id)
        if reference is None or reference.parent is None:
            return None

        parent_id = reference.parent
        if not self._parent_allows(parent_id, kind):
            return None

        node = self._create_node(item, position, parent_id)
        order_index = self._order_index_near(reference_id, before=before)
        child_index = self._child_index_near(parent_id, reference_id, before=before)

        self._insert_order(node.id, index=order_index)
        self._attach_child(parent_id, node.id, index=child_index)
        self.selected_id = node.id
        return node

    def can_add_sibling(self, reference_id: int, child_kind: PaletteKind) -> bool:
        reference = self.nodes.get(reference_id)
        if reference is None or reference.parent is None:
            return False
        return self._parent_allows(reference.parent, child_kind)

    def _resolve_parent(
        self, child_kind: PaletteKind, parent_hint: int | None
    ) -> int | None:
        """Pick the nearest valid parent that satisfies the entity-environment model."""
        candidates: list[int | None] = [parent_hint]

        if self.selected_id not in candidates:
            candidates.append(self.selected_id)
        candidates.append(self.root_id)

        for candidate in candidates:
            if candidate is None:
                continue
            if self._parent_allows(candidate, child_kind):
                return candidate

        return None

    def _parent_allows(self, parent_id: int, child_kind: PaletteKind) -> bool:
        parent = self.nodes.get(parent_id)
        if parent is None:
            return False
        allowed = {
            # Entities must always live inside environments.
            "entity": {"environment"},
            # Environments can hang from the scene root or from entities,
            # but they cannot nest inside other environments.
            "environment": {"root", "entity"},
        }
        return parent.kind in allowed[child_kind]

    def _attach_child(
        self, parent_id: int, child_id: int, index: int | None = None
    ) -> None:
        parent = self.nodes.get(parent_id)
        if parent is None:
            return
        if index is None or index >= len(parent.children):
            parent.children.append(child_id)
        else:
            index = max(0, index)
            parent.children.insert(index, child_id)

    def _insert_order(self, node_id: int, *, index: int | None = None) -> None:
        if index is None or index >= len(self._order):
            self._order.append(node_id)
            return
        self._order.insert(max(0, index), node_id)

    def _make_label(self, base: str) -> str:
        count = self._label_counts.get(base, 0)
        self._label_counts[base] = count + 1
        if count == 0:
            return base
        return f"{base} #{count + 1}"

    def _make_composition_id(self, kind: PaletteKind) -> str:
        prefix = "ent" if kind == "entity" else "env"
        current = self._composition_id_counts.get(kind, 0) + 1
        self._composition_id_counts[kind] = current
        return f"{prefix}-{current:03d}"

    def _create_root(self) -> int:
        root = Node(
            id=0,
            kind="root",
            name="Scene Root",
            base_name="Scene",
            payload=None,
            parent=None,
            composition_id="scene-root",
        )
        self.nodes[root.id] = root
        return root.id

    def _create_node(
        self, item: PaletteItem, position: tuple[int, int], parent_id: int
    ) -> Node:
        payload = item.factory(pygame.Vector2(position))
        label = self._make_label(item.name)
        node = Node(
            id=self._next_id,
            kind=item.kind,
            name=label,
            base_name=item.name,
            payload=payload,
            parent=parent_id,
            composition_id=self._make_composition_id(item.kind),
        )
        self.nodes[node.id] = node
        self._next_id += 1
        return node

    def _order_index_near(self, reference_id: int, *, before: bool) -> int | None:
        try:
            idx = self._order.index(reference_id)
        except ValueError:
            return None
        return idx if before else idx + 1

    def _child_index_near(
        self, parent_id: int, reference_id: int, *, before: bool
    ) -> int | None:
        parent = self.nodes.get(parent_id)
        if parent is None:
            return None
        try:
            idx = parent.children.index(reference_id)
        except ValueError:
            return None
        return idx if before else idx + 1

    # ---------- Consulta ----------

    def iter_drawable_nodes(self) -> Iterable[Node]:
        for node_id in self._order:
            node = self.nodes.get(node_id)
            if node is None or node.payload is None:
                continue
            yield node

    def iter_tree(self) -> Iterable[tuple[int, Node]]:
        """DFS that yields (depth, node) desde la raíz."""

        def _visit(node_id: int, depth: int) -> Iterable[tuple[int, Node]]:
            node = self.nodes.get(node_id)
            if node is None:
                return []

            yield (depth, node)
            for child_id in node.children:
                yield from _visit(child_id, depth + 1)

        yield from _visit(self.root_id, 0)

    def selected_node(self) -> Node | None:
        if self.selected_id is None:
            return None
        return self.nodes.get(self.selected_id)

    def node_by_id(self, node_id: int) -> Node | None:
        return self.nodes.get(node_id)

    def selected_label(self) -> str:
        node = self.selected_node()
        return node.name if node is not None else ""

    def parent_label(self, node_id: int) -> str | None:
        node = self.nodes.get(node_id)
        if node is None or node.parent is None:
            return None
        parent = self.nodes.get(node.parent)
        if parent is None:
            return None
        return parent.name

    def child_labels(self, node_id: int) -> list[str]:
        node = self.nodes.get(node_id)
        if node is None:
            return []
        labels: list[str] = []
        for child_id in node.children:
            child = self.nodes.get(child_id)
            if child is None:
                continue
            labels.append(child.name)
        return labels

    # ---------- Selección / Movimiento ----------

    def select_node(self, node_id: int | None) -> None:
        if node_id is None or node_id not in self.nodes:
            self.selected_id = None
            return
        if node_id == self.root_id:
            self.selected_id = None
            return
        self.selected_id = node_id

    def select_at_position(self, mouse_pos: tuple[int, int]) -> int | None:
        mx, my = mouse_pos
        best_id: int | None = None
        best_d2: float | None = None
        for node in self.iter_drawable_nodes():
            pos = node.position()
            if pos is None:
                continue
            dx = mx - float(pos.x)
            dy = my - float(pos.y)
            d2 = dx * dx + dy * dy
            if best_d2 is None or d2 < best_d2:
                best_d2 = d2
                best_id = node.id

        self.select_node(best_id)
        return best_id

    def move_selected_within(
        self, canvas_rect: pygame.Rect, desired: pygame.Vector2
    ) -> None:
        node = self.selected_node()
        if node is None or node.payload is None:
            return
        pos = getattr(node.payload, "pos", None)
        if pos is None:
            return

        radius = node.radius()
        left = canvas_rect.left + radius
        right = canvas_rect.right - radius
        top = canvas_rect.top + radius
        bottom = canvas_rect.bottom - radius

        pos.x = max(left, min(right, desired.x))
        pos.y = max(top, min(bottom, desired.y))

    # ---------- Eliminación ----------

    def delete_selected(self) -> None:
        node = self.selected_node()
        if node is None:
            return
        parent_id = node.parent
        self._remove_subtree(node.id)
        if (
            parent_id is not None
            and parent_id in self.nodes
            and parent_id != self.root_id
        ):
            self.selected_id = parent_id
        elif self._order:
            self.selected_id = self._order[-1]
        else:
            self.selected_id = None

    def _remove_subtree(self, node_id: int) -> None:
        node = self.nodes.pop(node_id, None)
        if node is None:
            return
        for child_id in list(node.children):
            self._remove_subtree(child_id)
        if node.parent is not None:
            parent = self.nodes.get(node.parent)
            if parent is not None:
                parent.children = [cid for cid in parent.children if cid != node_id]
        self._order = [nid for nid in self._order if nid != node_id]

    # ---------- Export / Persistencia ----------

    def load_from_runtime(self, runtime: CompositionRuntime) -> None:
        """Reconstruye el árbol del editor a partir de una composición ya cargada."""
        self._reset_state()

        comp_to_local: dict[str, int] = {}
        insertion_order: list[int] = []

        for runtime_node in runtime.iter_nodes():
            parent_local = self.root_id
            if runtime_node.parent is not None:
                parent_local = comp_to_local.get(runtime_node.parent, self.root_id)

            base_name = self._base_name_from_type_path(runtime_node.type_path)
            label = self._make_label(base_name)
            node = Node(
                id=self._next_id,
                kind=runtime_node.kind,
                name=label,
                base_name=base_name,
                payload=runtime_node.instance,
                parent=parent_local,
                composition_id=runtime_node.id,
            )

            self.nodes[node.id] = node
            self._attach_child(parent_local, node.id)
            comp_to_local[runtime_node.id] = node.id
            insertion_order.append(node.id)
            self._next_id += 1
            self._sync_composition_counter(runtime_node.kind, runtime_node.id)

        self._order = insertion_order
        self.selected_id = None

    def build_composition(
        self,
        *,
        metadata: dict[str, Any] | None = None,
        scene: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Devuelve un dict listo para serializar como *.eei.json."""

        metadata_block = {
            "name": "editor-composition",
            "description": "",
            "tags": [],
        }
        if metadata:
            metadata_block.update(metadata)
            metadata_block.setdefault("tags", [])

        scene_block = {"canvas": [640, 360], "origin": [0, 0]}
        if scene:
            scene_block.update(scene)

        nodes: list[dict[str, Any]] = []
        for node_id in self._order:
            node = self.nodes.get(node_id)
            if node is None or node.payload is None:
                continue
            nodes.append(self._node_to_entry(node))

        return {
            "version": 1,
            "metadata": metadata_block,
            "scene": scene_block,
            "nodes": nodes,
            "interactions": [],
        }

    def save_composition(
        self,
        path: str | Path,
        *,
        metadata: dict[str, Any] | None = None,
        scene: dict[str, Any] | None = None,
    ) -> Path:
        """Serializa el estado del editor a un archivo EEI."""

        data = self.build_composition(metadata=metadata, scene=scene)
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return file_path

    # ----- Helpers -----

    def _base_name_from_type_path(self, type_path: str) -> str:
        _, _, attr = type_path.rpartition(".")
        return attr or type_path

    def _sync_composition_counter(self, kind: PaletteKind, comp_id: str) -> None:
        current = self._composition_id_counts.get(kind, 0)
        trailing = self._parse_trailing_int(comp_id)
        if trailing is None:
            return
        if trailing > current:
            self._composition_id_counts[kind] = trailing

    def _parse_trailing_int(self, value: str) -> int | None:
        digits = ""
        for ch in reversed(value):
            if ch.isdigit():
                digits = ch + digits
            else:
                break
        if not digits:
            return None
        try:
            return int(digits)
        except ValueError:
            return None

    def _node_to_entry(self, node: Node) -> dict[str, Any]:
        payload = node.payload
        assert payload is not None

        type_path = f"{payload.__class__.__module__}.{payload.__class__.__name__}"
        parent_id = self._parent_composition_id(node)
        transform = self._extract_transform(payload)
        state = self._extract_state(payload)
        children = [
            self.nodes[cid].composition_id for cid in node.children if cid in self.nodes
        ]

        return {
            "id": node.composition_id,
            "kind": node.kind,
            "type": type_path,
            "parent": parent_id,
            "transform": transform,
            "state": state,
            "children": children,
        }

    def _parent_composition_id(self, node: Node) -> str | None:
        if node.parent is None:
            return None
        parent = self.nodes.get(node.parent)
        if parent is None or parent.kind == "root":
            return None
        return parent.composition_id

    def _extract_transform(self, payload: Any) -> dict[str, Any]:
        transform: dict[str, Any] = {}

        pos = getattr(payload, "pos", None)
        transform["position"] = self._vector_to_list(pos) or [0.0, 0.0]

        rotation = getattr(payload, "rotation", None)
        if rotation is not None:
            transform["rotation"] = float(rotation)

        scale = getattr(payload, "scale", None)
        if scale is not None:
            vec = self._vector_to_list(scale)
            if vec is not None:
                transform["scale"] = vec

        return transform

    def _extract_state(self, payload: Any) -> dict[str, Any]:
        if payload is None:
            return {}

        state: dict[str, Any] = {}
        data = getattr(payload, "__dict__", {})
        for key, value in data.items():
            if key.startswith("_"):
                continue
            if key in {"pos", "rotation", "scale"}:
                continue
            state[key] = self._coerce_state_value(value)
        return state

    def _vector_to_list(self, value: Any) -> list[float] | None:
        if isinstance(value, pygame.Vector2):
            return [float(value.x), float(value.y)]
        if isinstance(value, (tuple, list)) and len(value) == 2:
            try:
                return [float(value[0]), float(value[1])]
            except (TypeError, ValueError):
                return None
        return None

    def _coerce_state_value(self, value: Any) -> Any:
        if isinstance(value, pygame.Vector2):
            return [float(value.x), float(value.y)]
        if isinstance(value, (int, float, str, bool)) or value is None:
            return value
        if isinstance(value, list):
            return [self._coerce_state_value(v) for v in value]
        if isinstance(value, tuple):
            return [self._coerce_state_value(v) for v in value]
        if isinstance(value, dict):
            return {str(k): self._coerce_state_value(v) for k, v in value.items()}
        return repr(value)
