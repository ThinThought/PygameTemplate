from __future__ import annotations

import pygame
from game.scenes.base import Scene, AppLike
import game.entities as entities

class EntityEditorScene(Scene):
    def __init__(self) -> None:
        self.scene_width, self.scene_height = pygame.display.get_window_size()

        # Entities en el canvas
        self.entities: list[object] = []
        self.selected = 0

        # Palette: disponibles (nombre, factory(pos)->entity)
        self.available_entities: list[tuple[str, type]] = [
            (name, getattr(entities, name))
            for name in entities.__all__
        ]

        # Drag state
        self.dragging = False
        self.drag_mode: str | None = None  # "move-existing" | "spawn-new"
        self.drag_offset = pygame.Vector2(0, 0)

        self.font = pygame.font.Font(None, 20)
        self.font_mono = pygame.font.Font(None, 18)

        self.margin = 20
        self.gap = 12

        self.palette_item_h = 28
        self.palette_items_rects: list[pygame.Rect] = []

        self._recompute_layout()

    def _recompute_layout(self) -> None:
        w, h = pygame.display.get_window_size()
        self.scene_width, self.scene_height = w, h

        m = self.margin
        gap = self.gap

        left_w = int(w * 0.55)
        self.canvas_rect = pygame.Rect(m, m, left_w - m, h - 2 * m)

        right_x = self.canvas_rect.right + gap
        right_w = w - right_x - m
        self.inspector_rect = pygame.Rect(right_x, m, right_w, h - 2 * m)

        # Palette arriba del inspector
        palette_h = min(180, self.inspector_rect.height // 3)
        self.palette_rect = pygame.Rect(
            self.inspector_rect.x,
            self.inspector_rect.y,
            self.inspector_rect.width,
            palette_h,
        )

        # Inspector debajo
        insp_y = self.palette_rect.bottom + gap
        insp_h = self.inspector_rect.bottom - insp_y
        self.inspector_rect = pygame.Rect(self.inspector_rect.x, insp_y, self.inspector_rect.width, insp_h)

        self._rebuild_palette_item_rects()

    def _rebuild_palette_item_rects(self) -> None:
        self.palette_items_rects.clear()
        x = self.palette_rect.x + 10
        y = self.palette_rect.y + 36
        w = self.palette_rect.width - 20
        h = self.palette_item_h

        for _name, _factory in self.available_entities:
            self.palette_items_rects.append(pygame.Rect(x, y, w, h))
            y += h + 6

    def update(self, app: AppLike, dt: float) -> None:
        for entity in self.entities:
            entity.update(app, dt)

    def handle_event(self, app, ev: pygame.event.Event) -> None:
        if ev.type == pygame.QUIT:
            app.running = False
            return

        if ev.type == pygame.VIDEORESIZE:
            self._recompute_layout()
            return

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            # 1) Click en palette: spawn + drag
            idx = self._palette_hit_index(ev.pos)
            if idx is not None:
                self._spawn_from_palette(idx, ev.pos)
                return

            # 2) Click en canvas: seleccionar y mover
            if self.canvas_rect.collidepoint(ev.pos):
                hit = self._select_entity_at(ev.pos)
                if hit is not None:
                    self._start_drag_existing(ev.pos)
                return

        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self.dragging = False
            self.drag_mode = None
            return

        if ev.type == pygame.MOUSEMOTION:
            if self.dragging:
                self._drag_to(ev.pos)
            return

        for entity in self.entities:
            if hasattr(entity, "handle_event"):
                entity.handle_event(app, ev)

    # ---------- Palette / Spawn ----------

    def _palette_hit_index(self, pos: tuple[int, int]) -> int | None:
        if not self.palette_rect.collidepoint(pos):
            return None
        for i, r in enumerate(self.palette_items_rects):
            if r.collidepoint(pos):
                return i
        return None

    def _spawn_from_palette(self, idx: int, mouse_pos: tuple[int, int]) -> None:
        name, factory = self.available_entities[idx]

        # Spawn dentro del canvas (centro si aún no está encima)
        spawn_pos = pygame.Vector2(mouse_pos)
        if not self.canvas_rect.collidepoint(mouse_pos):
            spawn_pos = pygame.Vector2(self.canvas_rect.center)

        ent = factory(spawn_pos)
        self.entities.append(ent)
        self.selected = len(self.entities) - 1

        # Empezar drag como si fuese ya existente
        self.drag_mode = "spawn-new"
        self._start_drag_existing(mouse_pos)

    # ---------- Select / Drag existing ----------

    def _select_entity_at(self, mouse_pos: tuple[int, int]) -> int | None:
        mx, my = mouse_pos
        best_i = None
        best_d2 = None

        for i, e in enumerate(self.entities):
            p = getattr(e, "pos", None)
            if p is None:
                continue
            ex, ey = float(p.x), float(p.y)
            dx = mx - ex
            dy = my - ey
            d2 = dx * dx + dy * dy
            if best_d2 is None or d2 < best_d2:
                best_d2 = d2
                best_i = i

        if best_i is not None:
            self.selected = best_i
        return best_i

    def _start_drag_existing(self, mouse_pos: tuple[int, int]) -> None:
        if not self.entities:
            return
        ent = self.entities[self.selected]
        p = getattr(ent, "pos", None)
        if p is None:
            return

        self.dragging = True
        self.drag_mode = self.drag_mode or "move-existing"

        # Offset para no “pegar salto” al centro
        self.drag_offset = pygame.Vector2(p) - pygame.Vector2(mouse_pos)

        # Primer clamp inmediato
        self._drag_to(mouse_pos)

    def _drag_to(self, mouse_pos: tuple[int, int]) -> None:
        if not self.entities:
            return

        ent = self.entities[self.selected]
        p = getattr(ent, "pos", None)
        if p is None:
            return

        desired = pygame.Vector2(mouse_pos) + self.drag_offset

        # clamp: mantener dentro del canvas, usando radius si existe
        radius = float(getattr(ent, "radius", 0.0))
        left = self.canvas_rect.left + radius
        right = self.canvas_rect.right - radius
        top = self.canvas_rect.top + radius
        bottom = self.canvas_rect.bottom - radius

        desired.x = max(left, min(right, desired.x))
        desired.y = max(top, min(bottom, desired.y))

        p.x, p.y = desired.x, desired.y

    # ---------- Inspector helpers ----------

    def _iter_public_attrs(self, obj) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
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

    # ---------- Render ----------

    def render(self, app, screen: pygame.Surface) -> None:
        screen.fill("black")

        # Canvas
        pygame.draw.rect(screen, "white", self.canvas_rect, border_radius=6)

        prev_clip = screen.get_clip()
        screen.set_clip(self.canvas_rect.inflate(-4, -4))

        for i, entity in enumerate(self.entities):
            entity.render(app, screen)

            if i == self.selected:
                p = getattr(entity, "pos", None)
                if p is not None:
                    r = int(getattr(entity, "radius", 26)) + 6
                    pygame.draw.circle(screen, (255, 200, 0), (int(p.x), int(p.y)), r, 2)

        screen.set_clip(prev_clip)

        # Palette panel
        pygame.draw.rect(screen, (30, 30, 30), self.palette_rect, border_radius=6)
        self._draw_section_header(screen, self.palette_rect, "Entities")

        for i, (name, _factory) in enumerate(self.available_entities):
            r = self.palette_items_rects[i]
            hovered = r.collidepoint(pygame.mouse.get_pos())
            col = (55, 55, 55) if hovered else (45, 45, 45)
            pygame.draw.rect(screen, col, r, border_radius=6)
            t = self.font_mono.render(name, True, (220, 220, 220))
            screen.blit(t, (r.x + 8, r.y + 6))

        # Inspector panel
        pygame.draw.rect(screen, (30, 30, 30), self.inspector_rect, border_radius=6)
        self._draw_section_header(screen, self.inspector_rect, "Atribs")

        if self.entities:
            ent = self.entities[self.selected]
            self._draw_attrs(screen, self.inspector_rect, ent)

    def _draw_section_header(self, screen: pygame.Surface, rect: pygame.Rect, title: str) -> None:
        t = self.font.render(title, True, (220, 220, 220))
        screen.blit(t, (rect.x + 10, rect.y + 8))
        pygame.draw.line(
            screen, (70, 70, 70),
            (rect.x + 8, rect.y + 28),
            (rect.right - 8, rect.y + 28),
            1
        )

    def _draw_attrs(self, screen: pygame.Surface, rect: pygame.Rect, ent) -> None:
        y = rect.y + 36
        xk = rect.x + 10
        xv = rect.x + rect.width // 2

        for k, v in self._iter_public_attrs(ent):
            if y > rect.bottom - 10:
                break
            ksurf = self.font_mono.render(k, True, (200, 200, 200))
            vsurf = self.font_mono.render(v, True, (160, 220, 160))
            screen.blit(ksurf, (xk, y))
            screen.blit(vsurf, (xv, y))
            y += 20
