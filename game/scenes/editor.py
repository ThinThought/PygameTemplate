from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pygame
from game.compositions import load_composition
from game.scenes.base import Scene, AppLike
import game.entities as entities
import game.environments as environments
from game.editor import EditorModel, PaletteRegistry, PaletteItem
from game.input import ActionBinding, InputBinding, ControllerProfile


@dataclass
class AttrEntry:
    label: str
    display: str
    editable: bool = False
    attr_name: str | None = None
    raw_value: Any = None
    component: str | None = None


class EditorScene(Scene):
    INPUT_ACTIONS = [
        ActionBinding(
            action="Eliminar seleccion",
            description="Delete/Backspace elimina el nodo activo.",
            bindings=(
                InputBinding(device="keyboard", control="K_DELETE", label="Delete"),
                InputBinding(
                    device="keyboard", control="K_BACKSPACE", label="Backspace"
                ),
            ),
        ),
        ActionBinding(
            action="Guardar composicion",
            description="Ctrl+S guarda la composicion abierta.",
            bindings=(
                InputBinding(
                    device="keyboard", control="K_s", label="S", modifiers=("CTRL",)
                ),
            ),
        ),
        ActionBinding(
            action="Inspector navegar",
            description="Flechas arriba/abajo mueven el foco del inspector.",
            bindings=(
                InputBinding(device="keyboard", control="K_UP", label="Flecha arriba"),
                InputBinding(device="keyboard", control="K_DOWN", label="Flecha abajo"),
            ),
        ),
        ActionBinding(
            action="Inspector editar",
            description="Enter inicia edicion, Esc cancela, usa teclado para escribir.",
            bindings=(
                InputBinding(device="keyboard", control="K_RETURN", label="Enter"),
            ),
        ),
        ActionBinding(
            action="VCursor mover",
            description="El stick izquierdo controla el cursor virtual.",
            bindings=(
                InputBinding(
                    device="joystick_axis", control="left_x", label="Stick izquierdo X"
                ),
                InputBinding(
                    device="joystick_axis", control="left_y", label="Stick izquierdo Y"
                ),
            ),
        ),
        ActionBinding(
            action="VCursor primario",
            description="Emula clic izquierdo con A/B para la edicion rapida.",
            bindings=(
                InputBinding(device="joystick_button", control="a", label="Boton A"),
                InputBinding(device="joystick_button", control="b", label="Boton B"),
                InputBinding(
                    device="mouse", control="button1", label="Click izquierdo"
                ),
            ),
        ),
        ActionBinding(
            action="VCursor secundario",
            description="Emula clic derecho/context menu con botones Y/X.",
            bindings=(
                InputBinding(device="joystick_button", control="y", label="Boton Y"),
                InputBinding(device="joystick_button", control="x", label="Boton X"),
                InputBinding(device="mouse", control="button3", label="Click derecho"),
            ),
        ),
    ]

    def __init__(self) -> None:
        self.registry = PaletteRegistry.from_modules(entities, environments)
        self.model = EditorModel(self.registry)

        self.dragging = False
        self.drag_mode: str | None = None
        self.drag_offset = pygame.Vector2(0, 0)

        self.font = pygame.font.Font(None, 20)
        self.font_mono = pygame.font.Font(None, 18)
        self.toolbar_title = "Scene"
        self._toolbar_label_pad = 20

        self.margin = 20
        self.gap = 12
        self.palette_item_h = 28
        self.tree_line_h = 20
        self.attr_line_h = 20
        self.preview_scale = 0.6  # 60% de la resolución objetivo
        self.canvas_scale = 1.0
        self.entity_items_rects: list[pygame.Rect] = []
        self.environment_items_rects: list[pygame.Rect] = []
        self.tree_rect = pygame.Rect(0, 0, 0, 0)
        self.attrs_rect = pygame.Rect(0, 0, 0, 0)
        self._tree_hitboxes: list[tuple[pygame.Rect, int]] = []
        self.section_header_h = 36
        self.section_body_pad = 8
        self.scroll_step = 28
        self.palette_scroll: dict[str, int] = {"entity": 0, "environment": 0}
        self.tree_scroll = 0
        self.attrs_scroll = 0
        self.attr_focus_index = 0
        self._attr_focus_changed = False
        self.attr_editing = False
        self.attr_input = ""
        self.attr_cursor_pos = 0
        self._attr_edit_attr: str | None = None
        self._attr_edit_node_id: int | None = None
        self._attr_edit_component: str | None = None
        self._attr_edit_raw_value: Any = None
        self._last_attr_node_id: int | None = None

        self._last_size: tuple[int, int] | None = None
        self._last_saved_path: Path | None = None
        self._composition_path: Path | None = None

        self.scene_width = 0
        self.scene_height = 0
        self.canvas_rect = pygame.Rect(0, 0, 0, 0)
        self.scene_canvas_rect = pygame.Rect(0, 0, 0, 0)  # espacio virtual editable
        self._canvas_surface: pygame.Surface | None = None
        self._canvas_surface_size: tuple[int, int] | None = None
        self.toolbar_rect = pygame.Rect(0, 0, 0, 0)
        self.toolbar_buttons: list[tuple[str, str]] = [
            ("save", "Guardar"),
            ("play", "Play"),
        ]
        self.toolbar_button_rects: dict[str, pygame.Rect] = {}

        self.vcursor_enabled = False
        self.vcursor_pos = pygame.Vector2(80, 80)
        self.vcursor_vel = pygame.Vector2(0, 0)
        self.vcursor_speed = 220.0  # px/s
        self.vcursor_deadzone = 0.18
        self.vcursor_buttons: dict[int, bool] = {1: False, 3: False}  # LMB/RMB
        self.context_menu_active = False
        self.context_menu_rect = pygame.Rect(0, 0, 0, 0)
        self.context_menu_item_rects: list[tuple[str, pygame.Rect]] = []
        self.context_menu_items: list[tuple[str, str]] = [("delete", "Delete")]
        self.context_menu_target_id: int | None = None
        self.context_menu_hover: str | None = None
        self.context_menu_stage: str = "root"
        self.context_menu_stage_data: dict[str, Any] = {}
        root = Path(__file__).resolve().parents[2]
        self._controller_cfg_path = root / "configs" / "controllers" / "generic.toml"
        self.controller_profile = ControllerProfile.default()
        self._vcursor_axes: tuple[int, int] = (0, 1)
        self._vcursor_primary_buttons: tuple[int, ...] = (0,)
        self._vcursor_secondary_buttons: tuple[int, ...] = (1,)
        self._vscroll_axis: int = self._controller_axis_index(
            "right_y", 3
        )  # fallback típico
        self._vscroll_value: float = 0.0

        self._vscroll_deadzone: float = 0.18
        self._vscroll_speed_steps: float = 14.0  # pasos/seg cuando stick está al 100%
        self._vscroll_accum: float = 0.0

        self._load_controller_profile()

    def on_enter(self, app: AppLike) -> None:
        self._init_scene_canvas(app)
        self._sync_vcursor_enabled()
        self._load_initial_composition()

    # ---------------- Layout ----------------

    def _init_scene_canvas(self, app: AppLike) -> None:
        cfg = getattr(app, "cfg", None)
        width = getattr(cfg, "width", None)
        height = getattr(cfg, "height", None)
        if not width or not height:
            width, height = 1028, 720  # fallback
        self.scene_canvas_rect = pygame.Rect(0, 0, int(width), int(height))
        self._canvas_surface = None
        self._canvas_surface_size = None

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
        canvas_area = pygame.Rect(m, m, max(0, left_w - m), max(0, h - 2 * m))
        self.canvas_scale = self._compute_canvas_scale(
            canvas_area.width, canvas_area.height
        )
        target_w = self.scene_canvas_rect.width or 1
        target_h = self.scene_canvas_rect.height or 1
        scaled_w = int(target_w * self.canvas_scale)
        scaled_h = int(target_h * self.canvas_scale)
        scaled_w = max(0, min(canvas_area.width, scaled_w))
        scaled_h = max(0, min(canvas_area.height, scaled_h))
        cx = canvas_area.x + max(0, (canvas_area.width - scaled_w) // 2)
        cy = canvas_area.y + max(0, (canvas_area.height - scaled_h) // 2)
        self.canvas_rect = pygame.Rect(cx, cy, scaled_w, scaled_h)

        right_x = canvas_area.right + gap
        right_w = max(0, w - right_x - m)
        right_panel_rect = pygame.Rect(right_x, m, right_w, h - 2 * m)

        toolbar_h = min(44, right_panel_rect.height)
        self.toolbar_rect = pygame.Rect(
            right_panel_rect.x, right_panel_rect.y, right_panel_rect.width, toolbar_h
        )

        palette_y = self.toolbar_rect.bottom + gap
        palette_bottom_limit = right_panel_rect.bottom
        available_palettes_h = max(0, palette_bottom_limit - palette_y)
        palette_h = (
            min(180, available_palettes_h // 3) if available_palettes_h > 0 else 0
        )
        palette_width = right_panel_rect.width
        column_gap = min(gap, palette_width)
        entity_w = max(0, (palette_width - column_gap) // 2)
        env_w = max(0, palette_width - entity_w - column_gap)

        palette_x = right_panel_rect.x
        self.entities_palette_rect = pygame.Rect(
            palette_x, palette_y, entity_w, palette_h
        )
        env_x = self.entities_palette_rect.right + column_gap
        self.environments_palette_rect = pygame.Rect(env_x, palette_y, env_w, palette_h)

        palettes_bottom = max(
            self.entities_palette_rect.bottom, self.environments_palette_rect.bottom
        )
        insp_y = palettes_bottom + gap
        insp_h = right_panel_rect.bottom - insp_y
        self.inspector_rect = pygame.Rect(
            right_panel_rect.x, insp_y, right_panel_rect.width, max(0, insp_h)
        )

        tree_h = min(
            max(120, int(self.inspector_rect.height * 0.45)), self.inspector_rect.height
        )
        attr_y = self.inspector_rect.y + tree_h + gap
        attr_y = min(attr_y, self.inspector_rect.bottom)
        attr_h = max(0, self.inspector_rect.bottom - attr_y)

        self.tree_rect = pygame.Rect(
            self.inspector_rect.x,
            self.inspector_rect.y,
            self.inspector_rect.width,
            tree_h,
        )
        self.attrs_rect = pygame.Rect(
            self.inspector_rect.x, attr_y, self.inspector_rect.width, attr_h
        )
        self._tree_hitboxes = []

        self._rebuild_palette_item_rects()
        self._rebuild_toolbar_buttons()
        self._clamp_scroll_states()

    def _compute_canvas_scale(self, available_w: int, available_h: int) -> float:
        if available_w <= 0 or available_h <= 0:
            return 0.0
        target_w = max(1, self.scene_canvas_rect.width)
        target_h = max(1, self.scene_canvas_rect.height)
        max_scale_w = available_w / target_w
        max_scale_h = available_h / target_h
        scale = min(self.preview_scale, max_scale_w, max_scale_h)
        return max(0.0, scale)

    def _ensure_canvas_surface(self) -> pygame.Surface:
        size = (
            max(1, self.scene_canvas_rect.width),
            max(1, self.scene_canvas_rect.height),
        )
        if self._canvas_surface is None or self._canvas_surface_size != size:
            self._canvas_surface = pygame.Surface(size).convert()
            self._canvas_surface_size = size
        return self._canvas_surface

    def _rebuild_palette_item_rects(self) -> None:
        self.entity_items_rects = self._build_palette_rects(
            self.entities_palette_rect, len(self.registry.entities)
        )
        self.environment_items_rects = self._build_palette_rects(
            self.environments_palette_rect,
            len(self.registry.environments),
        )

    def _rebuild_toolbar_buttons(self) -> None:
        self.toolbar_button_rects = {}
        rect = self.toolbar_rect
        if rect.width <= 0 or rect.height <= 0 or not self.toolbar_buttons:
            return

        pad_x = 12
        btn_gap = 10
        btn_count = len(self.toolbar_buttons)
        label_w = self.font.size(self.toolbar_title)[0] + self._toolbar_label_pad
        pad_left = pad_x + label_w
        pad_right = pad_x
        available_w = rect.width - pad_left - pad_right - (btn_gap * (btn_count - 1))
        available_w = max(0, available_w)
        btn_w = available_w // btn_count if btn_count else 0
        if btn_count and btn_w <= 0:
            btn_w = max(0, rect.width // btn_count)

        btn_h = max(0, rect.height - 16)
        y = rect.y + (rect.height - btn_h) // 2
        x = rect.x + pad_left

        for key, _ in self.toolbar_buttons:
            self.toolbar_button_rects[key] = pygame.Rect(x, y, btn_w, btn_h)
            x += btn_w + btn_gap

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

    def _section_body_bounds(self, rect: pygame.Rect) -> tuple[int, int]:
        top = rect.y + self.section_header_h
        bottom = rect.bottom - self.section_body_pad
        if bottom < top:
            bottom = top
        return top, bottom

    def _visible_body_height(self, rect: pygame.Rect) -> int:
        top, bottom = self._section_body_bounds(rect)
        return max(0, bottom - top)

    def _palette_content_height(self, count: int) -> int:
        if count <= 0:
            return 0
        gap = 6
        return count * self.palette_item_h + max(0, (count - 1) * gap)

    def _palette_max_scroll(self, rect: pygame.Rect, count: int) -> int:
        visible = self._visible_body_height(rect)
        content = self._palette_content_height(count)
        return max(0, content - visible)

    def _tree_max_scroll(self) -> int:
        visible = self._visible_body_height(self.tree_rect)
        if visible <= 0:
            return 0
        total_lines = sum(1 for _ in self.model.iter_tree())
        content = total_lines * self.tree_line_h
        return max(0, content - visible)

    def _attrs_max_scroll(self, entries: list[AttrEntry]) -> int:
        visible = self._visible_body_height(self.attrs_rect)
        if visible <= 0:
            return 0
        content = len(entries) * self.attr_line_h
        return max(0, content - visible)

    def _clamp_scroll(self, value: int, max_scroll: int) -> int:
        if max_scroll <= 0:
            return 0
        return max(0, min(value, max_scroll))

    def _apply_scroll_delta(self, value: int, delta: float, max_scroll: int) -> int:
        if max_scroll <= 0:
            return 0
        new_value = value + int(delta)
        return self._clamp_scroll(new_value, max_scroll)

    def _clamp_scroll_states(self) -> None:
        entity_max = self._palette_max_scroll(
            self.entities_palette_rect, len(self.registry.entities)
        )
        env_max = self._palette_max_scroll(
            self.environments_palette_rect, len(self.registry.environments)
        )
        self.palette_scroll["entity"] = self._clamp_scroll(
            self.palette_scroll["entity"], entity_max
        )
        self.palette_scroll["environment"] = self._clamp_scroll(
            self.palette_scroll["environment"], env_max
        )
        self.tree_scroll = self._clamp_scroll(self.tree_scroll, self._tree_max_scroll())
        entries = self._current_attr_entries()
        self.attrs_scroll = (
            self._clamp_scroll(self.attrs_scroll, self._attrs_max_scroll(entries))
            if entries
            else 0
        )

    # ---------------- Update / Events ----------------

    def update(self, app: AppLike, dt: float) -> None:
        self._sync_vcursor_enabled()

        if self.vcursor_enabled:
            self.vcursor_pos += self.vcursor_vel * dt
            self.vcursor_pos.x = max(0, min(self.scene_width - 1, self.vcursor_pos.x))
            self.vcursor_pos.y = max(0, min(self.scene_height - 1, self.vcursor_pos.y))

            # 🎮 right stick scroll -> "wheel steps"
            if self._vscroll_value != 0.0:
                # Invertimos: stick arriba suele ser negativo; queremos "scroll up"
                steps_per_sec = self._vscroll_speed_steps * (-self._vscroll_value)
                self._vscroll_accum += steps_per_sec * dt

                steps = int(self._vscroll_accum)
                if steps != 0:
                    self._vscroll_accum -= steps
                    self._handle_scroll_input(
                        (int(self.vcursor_pos.x), int(self.vcursor_pos.y)),
                        steps,
                    )

    # ---------------- Render (orquestador) ----------------

    def render(self, app, screen: pygame.Surface) -> None:
        self._ensure_layout(screen)

        screen.fill("black")

        self._render_canvas(app, screen)
        self._render_toolbar(app, screen)
        self._render_palettes(app, screen)
        self._render_inspector(app, screen)
        self._render_context_menu(screen)
        if self.vcursor_enabled:
            x, y = int(self.vcursor_pos.x), int(self.vcursor_pos.y)

            BLACK = (15, 15, 15)
            WHITE = (245, 245, 245)
            ACCENT = (40, 120, 255)  # azul frío, opcional

            # --- halo exterior (blanco, se ve sobre fondos oscuros) ---
            pygame.draw.circle(screen, WHITE, (x, y), 9, 2)

            # --- outline principal (negro, se ve sobre blanco) ---
            pygame.draw.circle(screen, BLACK, (x, y), 7, 2)

            # --- núcleo sólido (negro) ---
            pygame.draw.circle(screen, BLACK, (x, y), 2)

            # --- cruz con doble capa ---
            arm = 6

            # sombra / outline
            pygame.draw.line(screen, BLACK, (x - arm, y), (x + arm, y), 3)
            pygame.draw.line(screen, BLACK, (x, y - arm), (x, y + arm), 3)

            # capa clara encima
            pygame.draw.line(screen, WHITE, (x - arm, y), (x + arm, y), 1)
            pygame.draw.line(screen, WHITE, (x, y - arm), (x, y + arm), 1)

            # --- punto de vida / dirección ---
            pygame.draw.circle(screen, ACCENT, (x + 4, y - 4), 1)

    # ---------------- Render helpers ----------------

    def _render_canvas(self, app: AppLike, screen: pygame.Surface) -> None:
        rect = self.canvas_rect
        if rect.width <= 0 or rect.height <= 0 or self.canvas_scale <= 0:
            return

        target = self._ensure_canvas_surface()
        target.fill("white")

        for node in self.model.iter_drawable_nodes():
            renderer = getattr(node.payload, "render", None)
            if callable(renderer):
                renderer(app, target)
            if node.id == self.model.selected_id:
                self._render_selection_ring(target, node)

        if (target.get_width(), target.get_height()) == (rect.width, rect.height):
            screen.blit(target, rect.topleft)
        else:
            scaled = pygame.transform.smoothscale(target, (rect.width, rect.height))
            screen.blit(scaled, rect.topleft)

        pygame.draw.rect(screen, (200, 200, 200), rect, width=1, border_radius=6)

    def _render_toolbar(self, app: AppLike, screen: pygame.Surface) -> None:
        rect = self.toolbar_rect
        if rect.width <= 0 or rect.height <= 0:
            return

        pygame.draw.rect(screen, (25, 25, 25), rect, border_radius=6)

        mouse = self._mouse_local(app)
        for key, label in self.toolbar_buttons:
            btn_rect = self.toolbar_button_rects.get(key)
            if btn_rect is None or btn_rect.width <= 0 or btn_rect.height <= 0:
                continue
            hovered = btn_rect.collidepoint(mouse)
            base = (50, 50, 50)
            if key == "play":
                base = (40, 80, 40)
            elif key == "save":
                base = (60, 60, 60)

            if hovered:
                if key == "play":
                    base = (60, 110, 60)
                elif key == "save":
                    base = (85, 75, 35)
                else:
                    base = (70, 70, 70)
            pygame.draw.rect(screen, base, btn_rect, border_radius=6)
            pygame.draw.rect(
                screen, (120, 120, 120), btn_rect, width=1, border_radius=6
            )

            text = self.font_mono.render(label, True, (235, 235, 235))
            tx = btn_rect.x + (btn_rect.width - text.get_width()) // 2
            ty = btn_rect.y + (btn_rect.height - text.get_height()) // 2
            screen.blit(text, (tx, ty))

        header = self.font.render(self.toolbar_title, True, (220, 220, 220))
        hx = rect.x + 12
        hy = rect.y + (rect.height - header.get_height()) // 2
        screen.blit(header, (hx, hy))

    def _render_selection_ring(self, surface: pygame.Surface, node) -> None:
        p = getattr(node.payload, "pos", None)
        if p is None:
            return
        r = int(getattr(node.payload, "radius", 26)) + 6
        pygame.draw.circle(surface, (255, 200, 0), (int(p.x), int(p.y)), r, 2)

    def _render_palettes(self, app: AppLike, screen: pygame.Surface) -> None:
        mouse = self._mouse_local(app)
        self._render_palette_column(
            screen,
            self.entities_palette_rect,
            "Entities",
            "entity",
            self.registry.entities,
            self.entity_items_rects,
            mouse,
        )
        self._render_palette_column(
            screen,
            self.environments_palette_rect,
            "Environments",
            "environment",
            self.registry.environments,
            self.environment_items_rects,
            mouse,
        )

    def _render_palette_column(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        title: str,
        kind: str,
        items: list[PaletteItem],
        item_rects: list[pygame.Rect],
        mouse_pos: tuple[int, int],
    ) -> None:
        if rect.width <= 0 or rect.height <= 0:
            return
        pygame.draw.rect(screen, (30, 30, 30), rect, border_radius=6)
        self._draw_section_header(screen, rect, title)

        max_scroll = self._palette_max_scroll(rect, len(items))
        scroll = self._clamp_scroll(self.palette_scroll.get(kind, 0), max_scroll)
        if scroll != self.palette_scroll.get(kind):
            self.palette_scroll[kind] = scroll
        body_top, body_bottom = self._section_body_bounds(rect)

        count = min(len(items), len(item_rects))
        for i in range(count):
            item = items[i]
            base_rect = item_rects[i]
            r = base_rect.move(0, -scroll)
            if r.bottom < body_top or r.top > body_bottom:
                continue
            hovered = r.collidepoint(mouse_pos)
            col = (55, 55, 55) if hovered else (45, 45, 45)
            pygame.draw.rect(screen, col, r, border_radius=6)
            t = self.font_mono.render(item.name, True, (220, 220, 220))
            screen.blit(t, (r.x + 8, r.y + 6))

    def _render_inspector(self, app: AppLike, screen: pygame.Surface) -> None:
        self._render_tree_panel(screen)
        self._render_attrs_panel(screen)

    def _render_context_menu(self, screen: pygame.Surface) -> None:
        if not self.context_menu_active:
            return
        rect = self.context_menu_rect
        if rect.width <= 0 or rect.height <= 0:
            return

        pygame.draw.rect(screen, (20, 20, 20), rect, border_radius=6)
        pygame.draw.rect(screen, (120, 120, 120), rect, width=1, border_radius=6)

        label_map = {key: label for key, label in self.context_menu_items}
        for key, item_rect in self.context_menu_item_rects:
            hovered = key == self.context_menu_hover
            color = (90, 50, 50) if hovered else (45, 45, 45)
            pygame.draw.rect(screen, color, item_rect, border_radius=4)
            text = label_map.get(key, key.title())
            surf = self.font_mono.render(text, True, (235, 235, 235))
            ty = item_rect.y + (item_rect.height - surf.get_height()) // 2
            screen.blit(surf, (item_rect.x + 10, ty))

    def _open_context_menu(self, pos: tuple[int, int], target_id: int) -> None:
        self.context_menu_target_id = target_id
        self._set_context_menu_stage("root")
        self._layout_context_menu(pos)
        self.context_menu_active = True
        self.context_menu_hover = None
        self.dragging = False
        self.drag_mode = None

    def _close_context_menu(self) -> None:
        self.context_menu_active = False
        self.context_menu_target_id = None
        self.context_menu_hover = None
        self.context_menu_item_rects = []
        self.context_menu_stage = "root"
        self.context_menu_stage_data = {}

    def _context_menu_hit(self, pos: tuple[int, int]) -> str | None:
        if not self.context_menu_active or not self.context_menu_rect.collidepoint(pos):
            return None
        for key, item_rect in self.context_menu_item_rects:
            if item_rect.collidepoint(pos):
                return key
        return None

    def _context_menu_click(self, app: AppLike, pos: tuple[int, int]) -> bool:
        key = self._context_menu_hit(pos)
        if key is None:
            return False
        should_close = self._perform_context_menu_action(app, key)
        if should_close:
            self._close_context_menu()
        return True

    def _update_context_menu_hover(self, pos: tuple[int, int]) -> None:
        if not self.context_menu_active:
            return
        self.context_menu_hover = self._context_menu_hit(pos)

    def _perform_context_menu_action(self, app: AppLike, key: str) -> bool:
        target_id = self.context_menu_target_id
        if target_id is None:
            return True

        if key == "noop":
            return False

        if key == "back":
            if self.context_menu_stage == "choose-kind":
                self._set_context_menu_stage("root")
            elif self.context_menu_stage == "choose-item":
                before = self.context_menu_stage_data.get("before")
                self._set_context_menu_stage("choose-kind", before=before)
            self._layout_context_menu()
            return False

        if self.context_menu_stage == "root":
            if key == "delete":
                if self.model.selected_id != target_id:
                    self.model.select_node(target_id)
                self._delete_selected()
                return True
            if key in {"add-before", "add-after"}:
                before = key == "add-before"
                if not self._context_menu_allowed_kinds(target_id):
                    return False
                self._set_context_menu_stage("choose-kind", before=before)
                self._layout_context_menu()
            return False

        if self.context_menu_stage == "choose-kind":
            if not key.startswith("kind-"):
                return False
            kind = key.split("-", 1)[1]
            if kind not in self._context_menu_allowed_kinds(target_id):
                return False
            before = bool(self.context_menu_stage_data.get("before"))
            self._set_context_menu_stage("choose-item", before=before, kind=kind)
            self._layout_context_menu()
            return False

        if self.context_menu_stage == "choose-item":
            if not key.startswith("item-"):
                return False
            try:
                idx = int(key.split("-", 1)[1])
            except ValueError:
                return False
            kind = self.context_menu_stage_data.get("kind")
            if kind not in {"entity", "environment"}:
                return False
            before = bool(self.context_menu_stage_data.get("before"))
            if self._context_menu_spawn_relative(kind, idx, before=before):
                return True
            return False

        return False

    def _set_context_menu_stage(
        self,
        stage: str,
        *,
        before: bool | None = None,
        kind: str | None = None,
    ) -> None:
        data: dict[str, Any] = {}
        if before is not None:
            data["before"] = before
        if kind is not None:
            data["kind"] = kind
        self.context_menu_stage = stage
        self.context_menu_stage_data = data
        if stage == "root":
            items = self._context_menu_root_items()
        elif stage == "choose-kind":
            items = self._context_menu_kind_items()
        elif stage == "choose-item":
            items = self._context_menu_palette_items(kind)
        else:
            items = []
        if not items:
            items = [("noop", "No actions")]
        self.context_menu_items = items

    def _layout_context_menu(self, pos: tuple[int, int] | None = None) -> None:
        width = 200
        item_h = 26
        pad = 8
        count = max(1, len(self.context_menu_items))
        height = pad * 2 + item_h * count

        if pos is None:
            x, y = self.context_menu_rect.x, self.context_menu_rect.y
        else:
            x, y = pos

        max_x = max(0, self.scene_width - width)
        max_y = max(0, self.scene_height - height)
        x = min(max(0, x), max_x)
        y = min(max(0, y), max_y)
        rect = pygame.Rect(x, y, width, height)

        item_rects: list[tuple[str, pygame.Rect]] = []
        item_y = rect.y + pad
        for key, _ in self.context_menu_items:
            item_rects.append(
                (key, pygame.Rect(rect.x + 4, item_y, rect.width - 8, item_h))
            )
            item_y += item_h

        self.context_menu_rect = rect
        self.context_menu_item_rects = item_rects
        self.context_menu_hover = None

    def _context_menu_root_items(self) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        allowed = self._context_menu_allowed_kinds(self.context_menu_target_id)
        if allowed:
            items.append(("add-before", "Add Before..."))
            items.append(("add-after", "Add After..."))
        items.append(("delete", "Delete"))
        return items

    def _context_menu_kind_items(self) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = [("back", "← Back")]
        allowed = self._context_menu_allowed_kinds(self.context_menu_target_id)
        labels = {"entity": "Entities", "environment": "Environments"}
        for kind in allowed:
            items.append((f"kind-{kind}", labels.get(kind, kind.title())))
        return items

    def _context_menu_palette_items(self, kind: str | None) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = [("back", "← Back")]
        if kind == "entity":
            collection = self.registry.entities
        elif kind == "environment":
            collection = self.registry.environments
        else:
            collection = []
        for idx, entry in enumerate(collection):
            items.append((f"item-{idx}", entry.name))
        return items

    def _context_menu_allowed_kinds(self, target_id: int | None) -> list[str]:
        allowed: list[str] = []
        if target_id is None:
            return allowed
        for kind in ("entity", "environment"):
            if self.model.can_add_sibling(target_id, kind):
                allowed.append(kind)
        return allowed

    def _context_menu_spawn_relative(
        self,
        kind: str,
        idx: int,
        *,
        before: bool,
    ) -> bool:
        target_id = self.context_menu_target_id
        if target_id is None:
            return False
        if kind not in self._context_menu_allowed_kinds(target_id):
            return False
        reference = self.model.node_by_id(target_id)
        if reference is None:
            return False
        pos = reference.position()
        if pos is None:
            pos = pygame.Vector2(self.scene_canvas_rect.center)
        new_node = self.model.spawn_from_palette_relative(
            kind,
            idx,
            (int(pos.x), int(pos.y)),
            target_id,
            before=before,
        )
        if new_node is None:
            self._print_status("[Editor] No pude insertar el elemento.")
            return False
        self._save_composition()
        return True

    def _handle_context_menu_request(self, pos: tuple[int, int]) -> None:
        target_id: int | None = None

        if (
            self.tree_rect.width > 0
            and self.tree_rect.height > 0
            and self.tree_rect.collidepoint(pos)
        ):
            target_id = self._tree_node_at(pos)
            if target_id == self.model.root_id:
                target_id = None
            elif target_id is not None:
                self.model.select_node(target_id)
        elif self.canvas_rect.collidepoint(pos):
            scene_pos = self._canvas_point_to_scene(pos, clamp=False)
            if scene_pos is not None:
                target_id = self._select_node_at_scene(scene_pos)

        if target_id is None:
            self._close_context_menu()
            return

        self._open_context_menu(pos, target_id)

    def _render_tree_panel(self, screen: pygame.Surface) -> None:
        rect = self.tree_rect
        if rect.width <= 0 or rect.height <= 0:
            self._tree_hitboxes = []
            return

        pygame.draw.rect(screen, (30, 30, 30), rect, border_radius=6)
        self._draw_section_header(screen, rect, "Tree")

        body_top, body_bottom = self._section_body_bounds(rect)
        visible = max(0, body_bottom - body_top)
        nodes = list(self.model.iter_tree())
        line_h = self.tree_line_h
        max_scroll = max(0, len(nodes) * line_h - visible)
        scroll = self._clamp_scroll(self.tree_scroll, max_scroll)
        if scroll != self.tree_scroll:
            self.tree_scroll = scroll

        y = body_top - scroll
        self._tree_hitboxes = []

        for depth, node in nodes:
            line_rect = pygame.Rect(rect.x + 6, y - 2, rect.width - 12, line_h)
            if line_rect.bottom < body_top:
                y += line_h
                continue
            if line_rect.top > body_bottom:
                break
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
            self.attrs_scroll = 0
            self._draw_empty_inspector(screen, rect)
            self._last_attr_node_id = None
            self._cancel_attr_edit()
            return

        if self._last_attr_node_id != node.id:
            self._last_attr_node_id = node.id
            self.attr_focus_index = 0
            self._attr_focus_changed = True
            self._cancel_attr_edit()

        entries = self._collect_attr_entries(node, self._selected_label())
        self._sync_attr_focus(entries, node.id)
        self._draw_attrs(screen, rect, entries)

    def _draw_empty_inspector(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        msg = self.font_mono.render(
            "No entities. Pick one from palette.", True, (160, 160, 160)
        )
        screen.blit(msg, (rect.x + 10, rect.y + 40))

    # ---------------- Toolbar ----------------

    def _toolbar_hit(self, pos: tuple[int, int]) -> str | None:
        if self.toolbar_rect.width <= 0 or self.toolbar_rect.height <= 0:
            return None
        if not self.toolbar_rect.collidepoint(pos):
            return None
        for key, rect in self.toolbar_button_rects.items():
            if rect.collidepoint(pos):
                return key
        return None

    # ---------------- Utilities ----------------

    def _mouse_local(self, app: AppLike) -> tuple[int, int]:
        """Mouse en coords de esta escena (útil si el core usa viewport/HUD)."""
        mx, my = pygame.mouse.get_pos()
        if hasattr(app, "scene_viewport"):
            vp = app.scene_viewport()
            return (mx - vp.x, my - vp.y)
        return (mx, my)

    def _canvas_point_to_scene(
        self,
        pos: tuple[int, int],
        *,
        clamp: bool = True,
    ) -> pygame.Vector2 | None:
        rect = self.canvas_rect
        if rect.width <= 0 or rect.height <= 0 or self.canvas_scale <= 0:
            return None
        local_x = pos[0] - rect.x
        local_y = pos[1] - rect.y
        if not clamp and not rect.collidepoint(pos):
            return None
        if clamp:
            local_x = max(0, min(rect.width, local_x))
            local_y = max(0, min(rect.height, local_y))
        # evita divisiones extra si la escala es cero
        if self.canvas_scale <= 0:
            return None
        scene_x = local_x / self.canvas_scale
        scene_y = local_y / self.canvas_scale
        return pygame.Vector2(scene_x, scene_y)

    def _draw_section_header(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        title: str,
    ) -> None:
        t = self.font.render(title, True, (220, 220, 220))
        screen.blit(t, (rect.x + 10, rect.y + 8))
        pygame.draw.line(
            screen,
            (70, 70, 70),
            (rect.x + 8, rect.y + 28),
            (rect.right - 8, rect.y + 28),
            1,
        )

    def _draw_attrs(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        entries: list[AttrEntry],
    ) -> None:
        if not entries:
            return
        xk = rect.x + 10
        xv = rect.x + rect.width // 2
        body_top, body_bottom = self._section_body_bounds(rect)
        visible = max(0, body_bottom - body_top)
        if visible <= 0:
            return

        max_scroll = self._attrs_max_scroll(entries)
        scroll = self._clamp_scroll(self.attrs_scroll, max_scroll)
        if scroll != self.attrs_scroll:
            self.attrs_scroll = scroll

        y = body_top - scroll
        cursor_on = (pygame.time.get_ticks() // 400) % 2 == 0
        for idx, entry in enumerate(entries):
            line_rect = pygame.Rect(rect.x + 4, y, rect.width - 8, self.attr_line_h)
            if line_rect.bottom >= body_top:
                if line_rect.top > body_bottom:
                    break
                is_focus = idx == self.attr_focus_index
                if is_focus:
                    color = (90, 70, 40) if entry.editable else (60, 60, 60)
                    pygame.draw.rect(screen, color, line_rect, border_radius=4)

                key_color = (210, 210, 210)
                value_color = (235, 210, 160) if entry.editable else (180, 180, 180)
                value_text = entry.display
                if self.attr_editing and is_focus:
                    value_text = self.attr_input
                    if cursor_on:
                        pre = self.attr_input[: self.attr_cursor_pos]
                        post = self.attr_input[self.attr_cursor_pos :]
                        value_text = f"{pre}|{post}"

                ksurf = self.font_mono.render(entry.label, True, key_color)
                vsurf = self.font_mono.render(value_text, True, value_color)
                screen.blit(ksurf, (xk, y))
                screen.blit(vsurf, (xv, y))
            y += self.attr_line_h

    def _sync_attr_focus(self, entries: list[AttrEntry], node_id: int) -> None:
        if not entries:
            self.attr_focus_index = 0
            self._cancel_attr_edit()
            return
        max_idx = len(entries) - 1

        old_idx = self.attr_focus_index
        self.attr_focus_index = max(0, min(self.attr_focus_index, max_idx))
        if old_idx != self.attr_focus_index:
            self._attr_focus_changed = True

        if self.attr_editing and self._attr_edit_node_id != node_id:
            self._cancel_attr_edit()

        if self._attr_focus_changed:
            self._scroll_attr_focus_into_view(entries)
            self._attr_focus_changed = False

    def _scroll_attr_focus_into_view(self, entries: list[AttrEntry]) -> None:
        if not entries:
            return
        rect = self.attrs_rect
        body_top, body_bottom = self._section_body_bounds(rect)
        visible = body_bottom - body_top
        if visible <= 0:
            return
        idx = max(0, min(self.attr_focus_index, len(entries) - 1))
        entry_top = idx * self.attr_line_h
        entry_bottom = entry_top + self.attr_line_h
        view_top = self.attrs_scroll
        view_bottom = self.attrs_scroll + visible
        if entry_top < view_top:
            self.attrs_scroll = entry_top
        elif entry_bottom > view_bottom:
            self.attrs_scroll = entry_bottom - visible
        max_scroll = self._attrs_max_scroll(entries)
        self.attrs_scroll = self._clamp_scroll(self.attrs_scroll, max_scroll)

    def _collect_attr_entries(self, node, label: str) -> list[AttrEntry]:
        entries: list[AttrEntry] = []
        if label:
            entries.append(AttrEntry("Nombre", label))
        entries.append(AttrEntry("Tipo", node.kind.title()))
        parent_label = self.model.parent_label(node.id) or "Scene Root"
        entries.append(AttrEntry("Parent", parent_label))
        children = ", ".join(self.model.child_labels(node.id)) or "-"
        entries.append(AttrEntry("Hijos", children))
        entries.extend(self._iter_public_attrs(node.payload))
        return entries

    def _current_attr_entries(self) -> list[AttrEntry]:
        node = self.model.selected_node()
        if node is None:
            return []
        return self._collect_attr_entries(node, self._selected_label())

    def _iter_public_attrs(self, obj) -> list[AttrEntry]:
        items: list[AttrEntry] = []
        if obj is None:
            return items

        seen_attrs = set()

        # Iterate through the MRO to find attributes, respecting definition order
        for cls in reversed(obj.__class__.__mro__):
            if cls is object:
                continue

            # Separated attributes for this class level
            class_level_attrs: list[AttrEntry] = []

            # Process attributes defined in this class
            for k in sorted(cls.__dict__.keys()):
                if k.startswith("_") or k in seen_attrs:
                    continue

                v = cls.__dict__[k]

                # We are interested in properties and data attributes on instances
                is_property = isinstance(v, property)
                is_data_like = not callable(v) or is_property

                if not is_data_like:
                    continue

                try:
                    value = getattr(obj, k)
                except AttributeError:
                    continue

                # An attribute is editable if it's a property with a setter,
                # or if it's a direct instance attribute (in __dict__)
                editable = False
                if is_property:
                    editable = v.fset is not None and self._attr_supports_edit(value)
                elif k in obj.__dict__:
                    editable = self._attr_supports_edit(value)

                # Expand Vector2 into its components for direct editing
                if isinstance(value, pygame.Vector2):
                    class_level_attrs.extend(self._vector_attr_entries(k, value))
                else:
                    class_level_attrs.append(
                        AttrEntry(
                            k,
                            self._safe_repr(value),
                            editable=editable,
                            attr_name=k,
                            raw_value=value,
                        )
                    )
                seen_attrs.add(k)

            if class_level_attrs:
                items.append(AttrEntry(f"[{cls.__name__}]", "", editable=False))
                items.extend(sorted(class_level_attrs, key=lambda x: x.label))

        # Add any remaining instance attributes not defined in any class (dynamic)
        remaining_instance_attrs: list[AttrEntry] = []
        for k, value in sorted(obj.__dict__.items()):
            if k.startswith("_") or k in seen_attrs:
                continue

            editable = self._attr_supports_edit(value)
            if isinstance(value, pygame.Vector2):
                remaining_instance_attrs.extend(self._vector_attr_entries(k, value))
            else:
                remaining_instance_attrs.append(
                    AttrEntry(
                        k,
                        self._safe_repr(value),
                        editable=editable,
                        attr_name=k,
                        raw_value=value,
                    )
                )
            seen_attrs.add(k)

        if remaining_instance_attrs:
            items.append(AttrEntry("[Instance]", "", editable=False))
            items.extend(sorted(remaining_instance_attrs, key=lambda x: x.label))

        return items

    def _vector_attr_entries(self, name: str, vec: pygame.Vector2) -> list[AttrEntry]:
        entries = [AttrEntry(name, self._safe_repr(vec))]
        for axis in ("x", "y"):
            comp_label = f"{name}.{axis}"
            comp_value = float(getattr(vec, axis))
            entries.append(
                AttrEntry(
                    comp_label,
                    self._safe_repr(comp_value),
                    editable=True,
                    attr_name=name,
                    raw_value=comp_value,
                    component=axis,
                )
            )
        return entries

    def _safe_repr(self, v) -> str:
        try:
            s = repr(v)
        except Exception:
            s = "<unrepr-able>"
        return s if len(s) <= 70 else s[:67] + "..."

    def _attr_supports_edit(self, value: Any) -> bool:
        if isinstance(value, (int, float, str, bool)) or value is None:
            return True
        return self._is_editable_sequence(value)

    def _is_editable_sequence(self, value: Any) -> bool:
        if not isinstance(value, (list, tuple)):
            return False
        if not value:
            return True
        return all(isinstance(item, str) for item in value)

    def _handle_attr_text_input(self, text: str) -> None:
        if not self.attr_editing or not text:
            return
        pre = self.attr_input[: self.attr_cursor_pos]
        post = self.attr_input[self.attr_cursor_pos :]
        self.attr_input = f"{pre}{text}{post}"
        self.attr_cursor_pos += len(text)

    def _handle_attr_keydown(self, ev: pygame.event.Event) -> bool:
        if ev.key == pygame.K_RETURN:
            self._commit_attr_edit()
            return True
        if ev.key in (pygame.K_ESCAPE, pygame.K_TAB):
            self._cancel_attr_edit()
            return True
        if ev.key == pygame.K_LEFT:
            self.attr_cursor_pos = max(0, self.attr_cursor_pos - 1)
            return True
        if ev.key == pygame.K_RIGHT:
            self.attr_cursor_pos = min(len(self.attr_input), self.attr_cursor_pos + 1)
            return True
        if ev.key == pygame.K_HOME:
            self.attr_cursor_pos = 0
            return True
        if ev.key == pygame.K_END:
            self.attr_cursor_pos = len(self.attr_input)
            return True
        if ev.key == pygame.K_BACKSPACE:
            if self.attr_cursor_pos > 0:
                pre = self.attr_input[: self.attr_cursor_pos - 1]
                post = self.attr_input[self.attr_cursor_pos :]
                self.attr_input = f"{pre}{post}"
                self.attr_cursor_pos -= 1
            return True
        if ev.key == pygame.K_DELETE:
            if self.attr_cursor_pos < len(self.attr_input):
                pre = self.attr_input[: self.attr_cursor_pos]
                post = self.attr_input[self.attr_cursor_pos + 1 :]
                self.attr_input = f"{pre}{post}"
            return True
        # swallow any other key while editing
        return True

    def _begin_attr_edit(self, node, entry: AttrEntry) -> None:
        if not entry.editable or entry.attr_name is None or node.payload is None:
            return
        self.attr_editing = True
        self.attr_input = self._format_attr_value(entry.raw_value)
        self.attr_cursor_pos = len(self.attr_input)
        self._attr_edit_attr = entry.attr_name
        self._attr_edit_node_id = node.id
        self._attr_edit_raw_value = entry.raw_value
        self._attr_edit_component = entry.component
        pygame.key.start_text_input()

    def _cancel_attr_edit(self) -> None:
        if self.attr_editing:
            pygame.key.stop_text_input()
        self.attr_editing = False
        self.attr_input = ""
        self.attr_cursor_pos = 0
        self._attr_edit_attr = None
        self._attr_edit_node_id = None
        self._attr_edit_raw_value = None
        self._attr_edit_component = None

    def _commit_attr_edit(self) -> None:
        if (
            not self.attr_editing
            or self._attr_edit_attr is None
            or self._attr_edit_node_id is None
        ):
            self._cancel_attr_edit()
            return
        node = self.model.selected_node()
        if node is None or node.payload is None or node.id != self._attr_edit_node_id:
            self._cancel_attr_edit()
            return

        current_value = getattr(node.payload, self._attr_edit_attr, None)
        if self._attr_edit_component is not None and isinstance(
            current_value, pygame.Vector2
        ):
            original_value = getattr(
                current_value, self._attr_edit_component, self._attr_edit_raw_value
            )
        else:
            original_value = current_value
        if original_value is None and self._attr_edit_raw_value is not None:
            original_value = self._attr_edit_raw_value
        success, parsed = self._parse_attr_input(original_value, self.attr_input)
        if not success:
            self._print_status(f"[Editor] Valor inválido para {self._attr_edit_attr}.")
            self._cancel_attr_edit()
            return

        if self._attr_edit_component is None:
            setattr(node.payload, self._attr_edit_attr, parsed)
        else:
            vec = (
                pygame.Vector2(current_value)
                if current_value is not None
                else pygame.Vector2(0, 0)
            )
            setattr(vec, self._attr_edit_component, float(parsed))
            setattr(node.payload, self._attr_edit_attr, vec)
        self._cancel_attr_edit()

    def _format_attr_value(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if self._is_editable_sequence(value):
            return ", ".join(value)
        return str(value)

    def _parse_attr_input(self, original: Any, text: str) -> tuple[bool, Any]:
        if isinstance(original, bool):
            value = text.strip().lower()
            if value in ("1", "true", "on", "si", "sí", "yes"):
                return True, True
            if value in ("0", "false", "off", "no"):
                return True, False
            return False, original
        if isinstance(original, int) and not isinstance(original, bool):
            try:
                return True, int(text.strip())
            except ValueError:
                return False, original
        if isinstance(original, float):
            try:
                return True, float(text.strip())
            except ValueError:
                return False, original
        if isinstance(original, (list, tuple)) and self._is_editable_sequence(original):
            parsed = self._parse_sequence_input(text)
            if isinstance(original, tuple):
                return True, tuple(parsed)
            return True, parsed
        if isinstance(original, str) or original is None:
            return True, text
        # unsupported type, treat as string
        return True, text

    def _parse_sequence_input(self, text: str) -> list[str]:
        if not text.strip():
            return []
        normalized = text.replace("\r\n", ",").replace("\n", ",").replace(";", ",")
        parts = normalized.split(",")
        values = [part.strip() for part in parts if part.strip()]
        return values

    # ---------------- VCursor helpers ----------------

    def _load_controller_profile(self) -> None:
        try:
            self.controller_profile = ControllerProfile.from_toml(
                self._controller_cfg_path
            )
        except (OSError, ValueError):
            self.controller_profile = ControllerProfile.default()
        self._vscroll_axis = self._controller_axis_index("right_y", 3)
        self._vscroll_deadzone = getattr(
            self.controller_profile, "deadzone", self._vscroll_deadzone
        )

        self._vcursor_axes = (
            self._controller_axis_index("left_x", 0),
            self._controller_axis_index("left_y", 1),
        )
        self._vcursor_primary_buttons = self._controller_button_indices(
            ("a", "b"), (0, 1, 5, 4)
        )
        self._vcursor_secondary_buttons = self._controller_button_indices(
            ("y", "x"), (3, 2, 6, 7)
        )
        self.vcursor_deadzone = getattr(
            self.controller_profile, "deadzone", self.vcursor_deadzone
        )

    def _controller_button_indices(
        self,
        names: tuple[str, ...],
        fallback: tuple[int, ...],
    ) -> tuple[int, ...]:
        seen: set[int] = set()
        result: list[int] = []
        for name in names:
            idx = self.controller_profile.button_index(name)
            if idx is None or idx in seen:
                continue
            result.append(idx)
            seen.add(idx)

        for idx in fallback:
            if idx in seen:
                continue
            result.append(idx)
            seen.add(idx)

        return tuple(result) if result else (0,)

    def _controller_axis_index(self, name: str, fallback: int) -> int:
        idx = self.controller_profile.axis_index(name)
        return idx if idx is not None else fallback

    def _sync_vcursor_enabled(self) -> None:
        self._set_vcursor_enabled(self._has_any_joystick())

    def _has_any_joystick(self) -> bool:
        if not pygame.joystick.get_init():
            return False
        try:
            return pygame.joystick.get_count() > 0
        except pygame.error:
            return False

    def _set_vcursor_enabled(self, enabled: bool) -> None:
        if self.vcursor_enabled == enabled:
            return
        self.vcursor_enabled = enabled
        if not enabled:
            self.vcursor_vel.xy = (0.0, 0.0)
            pos = (int(self.vcursor_pos.x), int(self.vcursor_pos.y))
            for button, was_down in list(self.vcursor_buttons.items()):
                if was_down:
                    self._pointer_up(button, pos)
                self.vcursor_buttons[button] = False

    # ---------------- Scroll helpers ----------------

    def _handle_scroll_input(self, pos: tuple[int, int] | None, steps: int) -> None:
        if pos is None or steps == 0:
            return
        delta = -steps * self.scroll_step
        if self.entities_palette_rect.collidepoint(pos):
            self._scroll_palette("entity", delta)
            return
        if self.environments_palette_rect.collidepoint(pos):
            self._scroll_palette("environment", delta)
            return
        if self.tree_rect.collidepoint(pos):
            self._scroll_tree(delta)
            return
        if self.attrs_rect.collidepoint(pos):
            self._scroll_attrs(delta)

    def _scroll_palette(self, kind: str, delta: float) -> None:
        rect = (
            self.entities_palette_rect
            if kind == "entity"
            else self.environments_palette_rect
        )
        items = (
            self.registry.entities if kind == "entity" else self.registry.environments
        )
        max_scroll = self._palette_max_scroll(rect, len(items))
        self.palette_scroll[kind] = self._apply_scroll_delta(
            self.palette_scroll[kind], delta, max_scroll
        )

    def _scroll_tree(self, delta: float) -> None:
        self.tree_scroll = self._apply_scroll_delta(
            self.tree_scroll, delta, self._tree_max_scroll()
        )

    def _scroll_attrs(self, delta: float) -> None:
        node = self.model.selected_node()
        if node is None:
            self.attrs_scroll = 0
            return
        entries = self._collect_attr_entries(node, self._selected_label())
        max_scroll = self._attrs_max_scroll(entries)
        self.attrs_scroll = self._apply_scroll_delta(
            self.attrs_scroll, delta, max_scroll
        )

    # ---------------- Interaction ----------------

    def handle_event(self, app: AppLike, ev: pygame.event.Event) -> None:
        # layout puede no existir todavía si llega evento muy pronto
        if self._last_size is None:
            return

        pos = self._event_pos_local(app, ev)
        if ev.type == pygame.TEXTINPUT and self.attr_editing:
            self._handle_attr_text_input(ev.text)
            return

        if ev.type == pygame.MOUSEWHEEL:
            self._handle_scroll_input(self._mouse_local(app), ev.y)
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and pos is not None:
            self._pointer_down(app, ev.button, pos)
            return
        if ev.type == pygame.MOUSEBUTTONUP and pos is not None:
            self._pointer_up(ev.button, pos)
            return
        if ev.type == pygame.MOUSEMOTION and pos is not None:
            self._pointer_move(pos)
            return

        if ev.type == pygame.KEYDOWN:
            if self.attr_editing and self._handle_attr_keydown(ev):
                return
            if ev.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                self._delete_selected()
                return
            if ev.key == pygame.K_s and (ev.mod & pygame.KMOD_CTRL):
                self._save_composition(app)
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
                scene_pos = self._canvas_point_to_scene(pos, clamp=False)
                if scene_pos is not None:
                    hit = self._select_node_at_scene(scene_pos)
                    if hit is not None:
                        self._start_drag_existing(scene_pos)
                return

        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self.dragging = False
            self.drag_mode = None
            return

        if ev.type == pygame.MOUSEMOTION and pos is not None:
            if self.dragging:
                scene_pos = self._canvas_point_to_scene(pos, clamp=True)
                self._drag_to_scene(scene_pos)
            return

        if ev.type == pygame.JOYAXISMOTION and self.vcursor_enabled:
            joy = pygame.joystick.Joystick(ev.joy)

            # --- vcursor move (left stick) ---
            if ev.axis in self._vcursor_axes:
                ax_idx, ay_idx = self._vcursor_axes
                ax = joy.get_axis(ax_idx)
                ay = joy.get_axis(ay_idx)

                def dz(v: float, dead: float) -> float:
                    return 0.0 if abs(v) < dead else v

                ax = dz(ax, self.vcursor_deadzone)
                ay = dz(ay, self.vcursor_deadzone)

                self.vcursor_vel.x = ax * self.vcursor_speed
                self.vcursor_vel.y = ay * self.vcursor_speed

                self._pointer_move(
                    (int(self.vcursor_pos.x), int(self.vcursor_pos.y))
                )

            # --- scroll (right stick Y) ---
            if ev.axis == self._vscroll_axis:
                v = joy.get_axis(self._vscroll_axis)
                self._vscroll_value = 0.0 if abs(v) < self._vscroll_deadzone else v

            return

        if ev.type == pygame.JOYHATMOTION and self.vcursor_enabled:
            hx, hy = ev.value  # -1/0/1
            self.vcursor_vel.x = hx * self.vcursor_speed
            self.vcursor_vel.y = (
                -hy * self.vcursor_speed
            )  # ojo: arriba suele ser +1, invertimos Y
            self._pointer_move((int(self.vcursor_pos.x), int(self.vcursor_pos.y)))
            return

        if (
            ev.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP)
            and self.vcursor_enabled
        ):
            is_down = ev.type == pygame.JOYBUTTONDOWN

            if ev.button in self._vcursor_primary_buttons:
                self.vcursor_buttons[1] = is_down
                if is_down:
                    self._pointer_down(
                        app, 1, (int(self.vcursor_pos.x), int(self.vcursor_pos.y))
                    )
                else:
                    self._pointer_up(
                        1, (int(self.vcursor_pos.x), int(self.vcursor_pos.y))
                    )
                return

            if ev.button in self._vcursor_secondary_buttons:
                self.vcursor_buttons[3] = is_down
                if is_down:
                    self._pointer_down(
                        app, 3, (int(self.vcursor_pos.x), int(self.vcursor_pos.y))
                    )
                else:
                    self._pointer_up(
                        3, (int(self.vcursor_pos.x), int(self.vcursor_pos.y))
                    )
                return

    def _event_pos_local(
        self,
        app: AppLike,
        ev: pygame.event.Event,
    ) -> tuple[int, int] | None:
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
        hit = self._palette_hit_column(
            pos,
            "entity",
            self.entities_palette_rect,
            self.entity_items_rects,
            len(self.registry.entities),
        )
        if hit is not None:
            return hit
        return self._palette_hit_column(
            pos,
            "environment",
            self.environments_palette_rect,
            self.environment_items_rects,
            len(self.registry.environments),
        )

    def _palette_hit_column(
        self,
        pos: tuple[int, int],
        target: str,
        rect: pygame.Rect,
        rects: list[pygame.Rect],
        count: int,
    ) -> tuple[str, int] | None:
        if rect.width <= 0 or rect.height <= 0:
            return None
        if not rect.collidepoint(pos):
            return None
        scroll = self.palette_scroll.get(target, 0)
        limit = min(count, len(rects))
        body_top, body_bottom = self._section_body_bounds(rect)
        for i in range(limit):
            r = rects[i].move(0, -scroll)
            if r.bottom < body_top or r.top > body_bottom:
                continue
            if r.collidepoint(pos):
                return (target, i)
        return None

    # ---------- Tree panel ----------

    def _tree_hit(self, pos: tuple[int, int]) -> bool:
        if self.tree_rect.width <= 0 or self.tree_rect.height <= 0:
            return False
        if not self.tree_rect.collidepoint(pos):
            return False
        node_id = self._tree_node_at(pos)
        if node_id is not None:
            self.model.select_node(node_id)
        else:
            self.model.select_node(None)
        return True

    def _tree_node_at(self, pos: tuple[int, int]) -> int | None:
        if self.tree_rect.width <= 0 or self.tree_rect.height <= 0:
            return None
        if not self.tree_rect.collidepoint(pos):
            return None
        for rect, node_id in self._tree_hitboxes:
            if rect.collidepoint(pos):
                return node_id
        return None

    # ---------- Attr panel ----------

    def _attr_panel_hit(self, pos: tuple[int, int]) -> bool:
        if self.attrs_rect.width <= 0 or self.attrs_rect.height <= 0:
            return False
        if not self.attrs_rect.collidepoint(pos):
            return False

        node = self.model.selected_node()
        if node is None:
            return False

        entries = self._collect_attr_entries(node, self._selected_label())
        if not entries:
            return False

        idx = self._attr_entry_index_at(pos, entries)
        if idx is None:
            return False

        self.attr_focus_index = idx
        self._attr_focus_changed = True
        entry = entries[idx]
        if entry.editable:
            if isinstance(entry.raw_value, bool):
                self._toggle_boolean_attr(node, entry)
            else:
                self._begin_attr_edit(node, entry)
        return True

    def _attr_entry_index_at(
        self,
        pos: tuple[int, int],
        entries: list[AttrEntry],
    ) -> int | None:
        rect = self.attrs_rect
        body_top, body_bottom = self._section_body_bounds(rect)
        if pos[1] < body_top or pos[1] >= body_bottom:
            return None
        visible = body_bottom - body_top
        if visible <= 0:
            return None
        relative_y = (pos[1] - body_top) + self.attrs_scroll
        if relative_y < 0:
            return None
        idx = int(relative_y // self.attr_line_h)
        return idx if 0 <= idx < len(entries) else None

    def _toggle_boolean_attr(self, node, entry: AttrEntry) -> None:
        if not entry.editable or not isinstance(entry.raw_value, bool):
            return
        if node.payload is None or entry.attr_name is None:
            return

        current_value = getattr(node.payload, entry.attr_name, None)
        if isinstance(current_value, bool):
            setattr(node.payload, entry.attr_name, not current_value)

    def _spawn_from_palette(
        self,
        target: str,
        idx: int,
        mouse_pos: tuple[int, int],
    ) -> None:
        spawn_pos_vec = self._canvas_point_to_scene(mouse_pos, clamp=False)
        if spawn_pos_vec is None:
            spawn_pos_vec = pygame.Vector2(self.scene_canvas_rect.center)

        node = self.model.spawn_from_palette(
            target, idx, (int(spawn_pos_vec.x), int(spawn_pos_vec.y))
        )
        if node is None:
            return

        self.drag_mode = "spawn-new"
        self._start_drag_existing(spawn_pos_vec)

    # ---------- Select / Drag ----------

    def _select_node_at_scene(self, scene_pos: pygame.Vector2) -> int | None:
        return self.model.select_at_position((int(scene_pos.x), int(scene_pos.y)))

    def _start_drag_existing(self, scene_pos: pygame.Vector2) -> None:
        node = self.model.selected_node()
        if node is None or node.payload is None:
            return
        p = getattr(node.payload, "pos", None)
        if p is None:
            return

        self.dragging = True
        self.drag_mode = self.drag_mode or "move-existing"
        self.drag_offset = pygame.Vector2(p) - pygame.Vector2(scene_pos)

        self._drag_to_scene(scene_pos)

    def _drag_to_scene(self, scene_pos: pygame.Vector2 | None) -> None:
        if scene_pos is None:
            return
        if self.model.selected_node() is None:
            return

        desired = pygame.Vector2(scene_pos) + self.drag_offset
        self.model.move_selected_within(self.scene_canvas_rect, desired)

    def _delete_selected(self) -> None:
        node = self.model.selected_node()
        if node is None:
            return

        self._cancel_attr_edit()
        self.model.delete_selected()
        self.dragging = False
        self.drag_mode = None
        self._save_composition()
        self._close_context_menu()

    def _selected_label(self) -> str:
        return self.model.selected_label()

    # ---------- Saving ----------

    def _composition_output_path(self) -> Path:
        if self._composition_path is not None:
            return self._composition_path
        root = Path(__file__).resolve().parents[2]
        return root / "configs" / "compositions" / "editor_export.eei.json"

    def _composition_candidates(self) -> list[Path]:
        root = Path(__file__).resolve().parents[2] / "configs" / "compositions"
        return [
            root / "editor_export.eei.json",
            root / "demo_face.eei.json",
        ]

    def _initial_composition_path(self) -> Path | None:
        for candidate in self._composition_candidates():
            if candidate.exists():
                return candidate
        return None

    def _load_initial_composition(self) -> None:
        path = self._initial_composition_path()
        if path is None:
            self._print_status(
                "[Editor] No hay composición inicial. Empieza una nueva escena."
            )
            return
        try:
            runtime = load_composition(path)
        except FileNotFoundError:
            self._print_status(f"[Editor] El archivo inicial no existe: {path}")
            return
        except Exception as exc:  # pragma: no cover - feedback
            self._print_status(f"[Editor] Error al cargar composición: {exc}")
            return

        self.model.load_from_runtime(runtime)
        self._composition_path = path
        self._last_saved_path = path
        self._print_status(f"[Editor] Composición cargada desde {path.name}")

    def _save_composition(self, app: AppLike | None = None) -> bool:
        target = self._composition_output_path()
        canvas = [
            self.scene_canvas_rect.width or 640,
            self.scene_canvas_rect.height or 360,
        ]
        try:
            path = self.model.save_composition(
                target,
                metadata={"name": target.stem},
                scene={"canvas": canvas, "origin": [0, 0]},
            )
        except Exception as exc:  # pragma: no cover - feedback
            self._print_status(f"[Editor] Error al guardar composición: {exc}")
            return False

        self._last_saved_path = path
        self._composition_path = path
        self._print_status(f"[Editor] Composición guardada en {path}")
        return True

    def _handle_toolbar_click(self, app: AppLike, key: str) -> None:
        if key == "save":
            self._save_composition(app)
        elif key == "play":
            self._play_from_editor(app)

    def _play_from_editor(self, app: AppLike) -> None:
        if self._save_composition(app):
            self._goto_main_scene(app)

    def _goto_main_scene(self, app: AppLike) -> None:
        set_scene = getattr(app, "set_scene", None)
        scene_list = getattr(app, "scenes", None)
        if not callable(set_scene) or not scene_list:
            self._print_status("[Editor] No puedo saltar a MainScene desde aquí.")
            return

        for idx, scene_cls in enumerate(scene_list):
            if getattr(scene_cls, "__name__", "") == "MainScene":
                self._print_status("[Editor] Ejecutando composición en MainScene...")
                set_scene(idx)
                return

        self._print_status("[Editor] MainScene no está registrada en esta app.")

    def _print_status(self, msg: str) -> None:
        print(msg)

    def _pointer_down(self, app: AppLike, button: int, pos: tuple[int, int]) -> None:
        if self.attr_editing:
            self._cancel_attr_edit()

        if button == 3:
            self.dragging = False
            self.drag_mode = None
            self._handle_context_menu_request(pos)
            return

        if button != 1:
            return

        if self.context_menu_active:
            if self._context_menu_click(app, pos):
                return
            self._close_context_menu()

        toolbar_hit = self._toolbar_hit(pos)
        if toolbar_hit is not None:
            self._handle_toolbar_click(app, toolbar_hit)
            return

        hit = self._palette_hit(pos)
        if hit is not None:
            target, idx = hit
            self._spawn_from_palette(target, idx, pos)
            return

        if self._tree_hit(pos):
            return

        if self._attr_panel_hit(pos):
            return

        if self.canvas_rect.collidepoint(pos):
            scene_pos = self._canvas_point_to_scene(pos, clamp=False)
            if scene_pos is None:
                return
            hit2 = self._select_node_at_scene(scene_pos)
            if hit2 is not None:
                self._start_drag_existing(scene_pos)
            return

    def _pointer_move(self, pos: tuple[int, int]) -> None:
        if self.context_menu_active:
            self._update_context_menu_hover(pos)
            if not self.dragging:
                return
        if self.dragging:
            scene_pos = self._canvas_point_to_scene(pos, clamp=True)
            self._drag_to_scene(scene_pos)

    def _pointer_up(self, button: int, pos: tuple[int, int]) -> None:
        if button == 1:
            was_spawn_new = self.drag_mode == "spawn-new"
            self.dragging = False
            self.drag_mode = None
            if was_spawn_new:
                self._save_composition()
