from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

import pygame

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
        self.nodes: dict[int, Node] = {}
        self._order: list[int] = []
        self._label_counts: dict[str, int] = {}
        self._next_id = 1
        self.root_id = self._create_root()
        self.selected_id: int | None = None

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
        payload = item.factory(pygame.Vector2(position))
        label = self._make_label(item.name)
        node = Node(
            id=self._next_id,
            kind=kind,
            name=label,
            base_name=item.name,
            payload=payload,
            parent=parent_id,
        )

        self.nodes[node.id] = node
        self._order.append(node.id)
        self._attach_child(parent_id, node.id)
        self._next_id += 1
        self.selected_id = node.id
        return node

    def _resolve_parent(self, child_kind: PaletteKind, parent_hint: int | None) -> int | None:
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

    def _attach_child(self, parent_id: int, child_id: int) -> None:
        parent = self.nodes.get(parent_id)
        if parent is None:
            return
        parent.children.append(child_id)

    def _make_label(self, base: str) -> str:
        count = self._label_counts.get(base, 0)
        self._label_counts[base] = count + 1
        if count == 0:
            return base
        return f"{base} #{count + 1}"

    def _create_root(self) -> int:
        root = Node(
            id=0,
            kind="root",
            name="Scene Root",
            base_name="Scene",
            payload=None,
            parent=None,
        )
        self.nodes[root.id] = root
        return root.id

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

    def move_selected_within(self, canvas_rect: pygame.Rect, desired: pygame.Vector2) -> None:
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
        if parent_id is not None and parent_id in self.nodes and parent_id != self.root_id:
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
