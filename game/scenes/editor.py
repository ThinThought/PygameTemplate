from __future__ import annotations

import pygame
from game.scenes.base import Scene, AppLike
import game.entities as entities
import game.environments as environments
from game.editor import EditorModel, PaletteRegistry, PaletteItem


class EditorScene(Scene):
    def __init__(self) -> None:
        self.registry = PaletteRegistry.from_modules(entities, environments)
        self.model = EditorModel(self.registry)

        self.dragging = False
        self.drag_mode: str | None = None
        self.drag_offset = pygame.Vector2(0, 0)

        self.font = pygame.font.Font(None, 20)
        self.font_mono = pygame.font.Font(None, 18)

        self.margin = 20
        self.gap = 12
        self.palette_item_h = 28
        self.entity_items_rects: list[pygame.Rect] = []
        self.environment_items_rects: list[pygame.Rect] = []
        self.tree_rect = pygame.Rect(0, 0, 0, 0)
        self.attrs_rect = pygame.Rect(0, 0, 0, 0)
        self._tree_hitboxes: list[tuple[pygame.Rect, int]] = []

        self._last_size: tuple[int, int] | None = None

    # ---------------- Layout ----------------

    def _ensure_layout(self, screen: pygame.Surface) -> None:
        size = screen.get_size()
        if size != self._last_size:
            self._recompute_layout(size)
            self._last_size = size

    def _recompute_layout(self, size: tuple[int, int]) -> None:
        w, h = size
        self.scene_width, self.scene_height = w, h

        m = self.margin
        gap = self.gap

        left_w = int(w * 0.55)
        self.canvas_rect = pygame.Rect(m, m, left_w - m, h - 2 * m)

        right_x = self.canvas_rect.right + gap
        right_w = w - right_x - m
        self.inspector_rect = pygame.Rect(right_x, m, right_w, h - 2 * m)

        palette_h = min(180, self.inspector_rect.height // 3)
        palette_width = self.inspector_rect.width
        column_gap = min(gap, palette_width)
        entity_w = max(0, (palette_width - column_gap) // 2)
        env_w = max(0, palette_width - entity_w - column_gap)

        palette_y = self.inspector_rect.y
        palette_x = self.inspector_rect.x
        self.entities_palette_rect = pygame.Rect(palette_x, palette_y, entity_w, palette_h)
        env_x = self.entities_palette_rect.right + column_gap
        self.environments_palette_rect = pygame.Rect(env_x, palette_y, env_w, palette_h)

        palettes_bottom = max(self.entities_palette_rect.bottom, self.environments_palette_rect.bottom)
        insp_y = palettes_bottom + gap
        insp_h = self.inspector_rect.bottom - insp_y
        self.inspector_rect = pygame.Rect(self.inspector_rect.x, insp_y, self.inspector_rect.width, insp_h)

        tree_h = min(max(120, int(self.inspector_rect.height * 0.45)), self.inspector_rect.height)
        attr_y = self.inspector_rect.y + tree_h + gap
        attr_y = min(attr_y, self.inspector_rect.bottom)
        attr_h = max(0, self.inspector_rect.bottom - attr_y)

        self.tree_rect = pygame.Rect(self.inspector_rect.x, self.inspector_rect.y, self.inspector_rect.width, tree_h)
        self.attrs_rect = pygame.Rect(self.inspector_rect.x, attr_y, self.inspector_rect.width, attr_h)
        self._tree_hitboxes = []

        self._rebuild_palette_item_rects()

    def _rebuild_palette_item_rects(self) -> None:
        self.entity_items_rects = self._build_palette_rects(self.entities_palette_rect, len(self.registry.entities))
        self.environment_items_rects = self._build_palette_rects(
            self.environments_palette_rect,
            len(self.registry.environments),
        )

    def _build_palette_rects(self, rect: pygame.Rect, count: int) -> list[pygame.Rect]:
        rects: list[pygame.Rect] = []
        if rect.width <= 0 or count <= 0:
            return rects

        x = rect.x + 10
        y = rect.y + 36
        w = rect.width - 20
        h = self.palette_item_h

        for _ in range(count):
            rects.append(pygame.Rect(x, y, w, h))
            y += h + 6
        return rects

    # ---------------- Update / Events ----------------

    def update(self, app: AppLike, dt: float) -> None:
        for node in self.model.iter_drawable_nodes():
            updater = getattr(node.payload, "update", None)
            if callable(updater):
                updater(app, dt)

    # (tu handle_event lo puedes mantener, pero recuerda: VIDEORESIZE en escenas no hace falta si el core gestiona)
    # y recuerda convertir mouse a local si usas viewport/hud.

    # ---------------- Render (orquestador) ----------------

    def render(self, app, screen: pygame.Surface) -> None:
        self._ensure_layout(screen)

        screen.fill("black")

        self._render_canvas(app, screen)
        self._render_palettes(app, screen)
        self._render_inspector(app, screen)

    # ---------------- Render helpers ----------------

    def _render_canvas(self, app: AppLike, screen: pygame.Surface) -> None:
        pygame.draw.rect(screen, "white", self.canvas_rect, border_radius=6)

        prev_clip = screen.get_clip()
        screen.set_clip(self.canvas_rect.inflate(-4, -4))

        for node in self.model.iter_drawable_nodes():
            renderer = getattr(node.payload, "render", None)
            if callable(renderer):
                renderer(app, screen)
            if node.id == self.model.selected_id:
                self._render_selection_ring(screen, node)

        screen.set_clip(prev_clip)

    def _render_selection_ring(self, screen: pygame.Surface, node) -> None:
        p = getattr(node.payload, "pos", None)
        if p is None:
            return
        r = int(getattr(node.payload, "radius", 26)) + 6
        pygame.draw.circle(screen, (255, 200, 0), (int(p.x), int(p.y)), r, 2)

    def _render_palettes(self, app: AppLike, screen: pygame.Surface) -> None:
        mouse = self._mouse_local(app)
        self._render_palette_column(
            screen,
            self.entities_palette_rect,
            "Entities",
            self.registry.entities,
            self.entity_items_rects,
            mouse,
        )
        self._render_palette_column(
            screen,
            self.environments_palette_rect,
            "Environments",
            self.registry.environments,
            self.environment_items_rects,
            mouse,
        )

    def _render_palette_column(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        title: str,
        items: list[PaletteItem],
        item_rects: list[pygame.Rect],
        mouse_pos: tuple[int, int],
    ) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        pygame.draw.rect(screen, (30, 30, 30), rect, border_radius=6)
        self._draw_section_header(screen, rect, title)

        for i, item in enumerate(items):
            if i >= len(item_rects):
                break
            r = item_rects[i]
            hovered = r.collidepoint(mouse_pos)
            col = (55, 55, 55) if hovered else (45, 45, 45)
            pygame.draw.rect(screen, col, r, border_radius=6)
            t = self.font_mono.render(item.name, True, (220, 220, 220))
            screen.blit(t, (r.x + 8, r.y + 6))

    def _render_inspector(self, app: AppLike, screen: pygame.Surface) -> None:
        self._render_tree_panel(screen)
        self._render_attrs_panel(screen)

    def _render_tree_panel(self, screen: pygame.Surface) -> None:
        rect = self.tree_rect
        if rect.width <= 0 or rect.height <= 0:
            self._tree_hitboxes = []
            return

        pygame.draw.rect(screen, (30, 30, 30), rect, border_radius=6)
        self._draw_section_header(screen, rect, "Tree")

        y = rect.y + 36
        line_h = 20
        max_y = rect.bottom - 8
        self._tree_hitboxes = []

        for depth, node in self.model.iter_tree():
            if y > max_y:
                break

            line_rect = pygame.Rect(rect.x + 6, y - 2, rect.width - 12, line_h)
            is_selected = node.id == self.model.selected_id
            if is_selected:
                pygame.draw.rect(screen, (80, 70, 30), line_rect, border_radius=4)

            indent = depth * 14
            text_x = rect.x + 12 + indent
            text = node.name
            if node.kind in ("entity", "environment"):
                tag = " [Ent]" if node.kind == "entity" else " [Env]"
                text = f"{node.name}{tag}"
            color = (255, 220, 160) if is_selected else (210, 210, 210)
            t = self.font_mono.render(text, True, color)
            screen.blit(t, (text_x, y))

            self._tree_hitboxes.append((line_rect.copy(), node.id))
            y += line_h

    def _render_attrs_panel(self, screen: pygame.Surface) -> None:
        rect = self.attrs_rect
        if rect.width <= 0 or rect.height <= 0:
            return

        pygame.draw.rect(screen, (30, 30, 30), rect, border_radius=6)
        self._draw_section_header(screen, rect, "Atribs")

        node = self.model.selected_node()
        if node is None:
            self._draw_empty_inspector(screen, rect)
            return

        self._draw_attrs(screen, rect, node, self._selected_label())

    def _draw_empty_inspector(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        msg = self.font_mono.render("No entities. Pick one from palette.", True, (160, 160, 160))
        screen.blit(msg, (rect.x + 10, rect.y + 40))

    # ---------------- Utilities ----------------

    def _mouse_local(self, app: AppLike) -> tuple[int, int]:
        """Mouse en coords de esta escena (útil si el core usa viewport/HUD)."""
        mx, my = pygame.mouse.get_pos()
        if hasattr(app, "scene_viewport"):
            vp = app.scene_viewport()
            return (mx - vp.x, my - vp.y)
        return (mx, my)

    def _draw_section_header(self, screen: pygame.Surface, rect: pygame.Rect, title: str) -> None:
        t = self.font.render(title, True, (220, 220, 220))
        screen.blit(t, (rect.x + 10, rect.y + 8))
        pygame.draw.line(
            screen, (70, 70, 70),
            (rect.x + 8, rect.y + 28),
            (rect.right - 8, rect.y + 28),
            1
        )

    def _draw_attrs(self, screen: pygame.Surface, rect: pygame.Rect, node, label: str) -> None:
        y = rect.y + 36
        xk = rect.x + 10
        xv = rect.x + rect.width // 2

        entries: list[tuple[str, str]] = []
        if label:
            entries.append(("Nombre", label))
        entries.append(("Tipo", node.kind.title()))
        parent_label = self.model.parent_label(node.id) or "Scene Root"
        entries.append(("Parent", parent_label))
        children = ", ".join(self.model.child_labels(node.id)) or "-"
        entries.append(("Hijos", children))

        for key, value in entries:
            ksurf = self.font_mono.render(key, True, (200, 200, 200))
            vsurf = self.font_mono.render(value, True, (220, 200, 160))
            screen.blit(ksurf, (xk, y))
            screen.blit(vsurf, (xv, y))
            y += 20

        for k, v in self._iter_public_attrs(node.payload):
            if y > rect.bottom - 10:
                break
            ksurf = self.font_mono.render(k, True, (200, 200, 200))
            vsurf = self.font_mono.render(v, True, (160, 220, 160))
            screen.blit(ksurf, (xk, y))
            screen.blit(vsurf, (xv, y))
            y += 20

    def _iter_public_attrs(self, obj) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        if obj is None:
            return items
        d = getattr(obj, "__dict__", {})
        for k in sorted(d.keys()):
            if k.startswith("_"):
                continue
            items.append((k, self._safe_repr(d[k])))
        return items

    def _safe_repr(self, v) -> str:
        try:
            s = repr(v)
        except Exception:
            s = "<unrepr-able>"
        return s if len(s) <= 70 else s[:67] + "..."


    # ---------------- Interaction ----------------

    def handle_event(self, app: AppLike, ev: pygame.event.Event) -> None:
        # layout puede no existir todavía si llega evento muy pronto
        if self._last_size is None:
            return

        pos = self._event_pos_local(app, ev)

        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                self._delete_selected()
                return

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and pos is not None:
            # 1) palette -> spawn + drag
            hit = self._palette_hit(pos)
            if hit is not None:
                target, idx = hit
                self._spawn_from_palette(target, idx, pos)
                return

            # 2) tree view -> select
            if self._tree_hit(pos):
                return

            # 3) canvas -> select + drag
            if self.canvas_rect.collidepoint(pos):
                hit = self._select_node_at(pos)
                if hit is not None:
                    self._start_drag_existing(pos)
                return

        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self.dragging = False
            self.drag_mode = None
            return

        if ev.type == pygame.MOUSEMOTION and pos is not None:
            if self.dragging:
                self._drag_to(pos)
            return

        # passthrough
        for node in self.model.iter_drawable_nodes():
            h = getattr(node.payload, "handle_event", None)
            if callable(h):
                h(app, ev)

    def _event_pos_local(self, app: AppLike, ev: pygame.event.Event) -> tuple[int, int] | None:
        """Convierte ev.pos (coords ventana) a coords del viewport."""
        if not hasattr(ev, "pos"):
            return None
        mx, my = ev.pos
        if hasattr(app, "scene_viewport"):
            vp = app.scene_viewport()
            return (mx - vp.x, my - vp.y)
        return (mx, my)

    # ---------- Palette / Spawn ----------

    def _palette_hit(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        hit = self._palette_hit_column(pos, "entity", self.entities_palette_rect, self.entity_items_rects)
        if hit is not None:
            return hit
        return self._palette_hit_column(pos, "environment", self.environments_palette_rect, self.environment_items_rects)

    def _palette_hit_column(
        self,
        pos: tuple[int, int],
        target: str,
        rect: pygame.Rect,
        rects: list[pygame.Rect],
    ) -> tuple[str, int] | None:
        if rect.width <= 0 or rect.height <= 0:
            return None
        if not rect.collidepoint(pos):
            return None
        for i, r in enumerate(rects):
            if r.collidepoint(pos):
                return (target, i)
        return None

    # ---------- Tree panel ----------

    def _tree_hit(self, pos: tuple[int, int]) -> bool:
        if self.tree_rect.width <= 0 or self.tree_rect.height <= 0:
            return False
        if not self.tree_rect.collidepoint(pos):
            return False
        for rect, node_id in self._tree_hitboxes:
            if rect.collidepoint(pos):
                self.model.select_node(node_id)
                return True
        self.model.select_node(None)
        return True

    def _spawn_from_palette(self, target: str, idx: int, mouse_pos: tuple[int, int]) -> None:
        spawn_pos = pygame.Vector2(mouse_pos)
        if not self.canvas_rect.collidepoint(mouse_pos):
            spawn_pos = pygame.Vector2(self.canvas_rect.center)

        node = self.model.spawn_from_palette(target, idx, spawn_pos)
        if node is None:
            return

        self.drag_mode = "spawn-new"
        self._start_drag_existing(mouse_pos)

    # ---------- Select / Drag ----------

    def _select_node_at(self, mouse_pos: tuple[int, int]) -> int | None:
        return self.model.select_at_position(mouse_pos)

    def _start_drag_existing(self, mouse_pos: tuple[int, int]) -> None:
        node = self.model.selected_node()
        if node is None or node.payload is None:
            return
        p = getattr(node.payload, "pos", None)
        if p is None:
            return

        self.dragging = True
        self.drag_mode = self.drag_mode or "move-existing"
        self.drag_offset = pygame.Vector2(p) - pygame.Vector2(mouse_pos)

        self._drag_to(mouse_pos)

    def _drag_to(self, mouse_pos: tuple[int, int]) -> None:
        if self.model.selected_node() is None:
            return

        desired = pygame.Vector2(mouse_pos) + self.drag_offset
        self.model.move_selected_within(self.canvas_rect, desired)

    def _delete_selected(self) -> None:
        self.model.delete_selected()
        self.dragging = False
        self.drag_mode = None

    def _selected_label(self) -> str:
        return self.model.selected_label()
