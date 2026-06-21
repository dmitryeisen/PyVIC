from __future__ import annotations

from dataclasses import dataclass

import pygame
from pygame.locals import (
    K_BACKSPACE,
    K_DOWN,
    K_ESCAPE,
    K_RETURN,
    K_TAB,
    K_UP,
    MOUSEBUTTONDOWN,
    MOUSEMOTION,
    QUIT,
)

from utils.ch9329.config import (
    DEFAULT_BAUDRATES,
    USB_PRODUCT_NAME,
    USB_VENDOR_NAME,
    WORKING_MODE_LABELS,
    WorkingMode,
)

MENU_WIDTH = 780
MENU_HEIGHT = 560

BG_COLOR = (24, 28, 36)
PANEL_COLOR = (32, 38, 48)
FIELD_COLOR = (44, 52, 66)
FIELD_HOVER_COLOR = (58, 70, 90)
FIELD_ACTIVE_COLOR = (40, 60, 86)
OPTION_HOVER_COLOR = (50, 110, 200)
TEXT_COLOR = (230, 235, 245)
MUTED_COLOR = (140, 150, 170)
ACCENT_COLOR = (80, 160, 255)
BORDER_COLOR = (70, 82, 100)
ACTIVE_BORDER_COLOR = (80, 160, 255)
BUTTON_COLOR = (50, 120, 220)
BUTTON_HOVER_COLOR = (70, 150, 255)

# CH9329 limits USB string descriptors to 23 characters.
MAX_NAME_LENGTH = 23

LABEL_X = 50
FIELD_X = 290
FIELD_WIDTH = 440
FIELD_HEIGHT = 42
ROW_GAP = 64
FIRST_ROW_Y = 150
OPTION_HEIGHT = 38


@dataclass
class StartupConfig:
    baudrate: int = 9600
    working_mode: WorkingMode = WorkingMode.KEYBOARD_MOUSE
    mouse_relative: bool = True
    manufacturer: str = USB_VENDOR_NAME
    product: str = USB_PRODUCT_NAME


class Dropdown:
    """A mouse-controllable selection list (combo box)."""

    def __init__(self, label: str, options: list, display_fn=str, index: int = 0):
        self.label = label
        self.options = options
        self.display_fn = display_fn
        self.index = index
        self.open = False
        self.rect = pygame.Rect(0, 0, 0, 0)

    @property
    def value(self):
        return self.options[self.index]

    def header_text(self) -> str:
        return self.display_fn(self.options[self.index])

    def option_rects(self) -> list:
        return [
            pygame.Rect(
                self.rect.x,
                self.rect.bottom + i * OPTION_HEIGHT,
                self.rect.width,
                OPTION_HEIGHT,
            )
            for i in range(len(self.options))
        ]


class TextInput:
    """A mouse-focusable, keyboard-editable text field."""

    def __init__(self, label: str, text: str = "", max_length: int = MAX_NAME_LENGTH):
        self.label = label
        self.text = text
        self.max_length = max_length
        self.active = False
        self.rect = pygame.Rect(0, 0, 0, 0)

    @property
    def value(self) -> str:
        return self.text

    def handle_key(self, event) -> None:
        if event.key == K_BACKSPACE:
            self.text = self.text[:-1]
            return
        char = event.unicode
        if char and char.isprintable() and len(self.text) < self.max_length:
            self.text += char


def _ensure_unique(values: list) -> list:
    seen = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def run_startup_menu() -> StartupConfig | None:
    config = StartupConfig()

    baud_options = _ensure_unique([config.baudrate, *DEFAULT_BAUDRATES])
    mode_options = list(WorkingMode)
    mouse_options = [True, False]

    dropdowns = [
        Dropdown("Baudrate", baud_options, str, baud_options.index(config.baudrate)),
        Dropdown(
            "Arbeitsmodus",
            mode_options,
            lambda m: WORKING_MODE_LABELS[m],
            mode_options.index(config.working_mode),
        ),
        Dropdown(
            "Mausmodus",
            mouse_options,
            lambda v: "Relativ" if v else "Absolut",
            0 if config.mouse_relative else 1,
        ),
    ]
    text_inputs = [
        TextInput("Hersteller", config.manufacturer),
        TextInput("Produktname", config.product),
    ]

    # Ordered rows: dropdowns first, then text inputs.
    rows = [*dropdowns, *text_inputs]
    for index, row in enumerate(rows):
        row.rect = pygame.Rect(
            FIELD_X, FIRST_ROW_Y + index * ROW_GAP, FIELD_WIDTH, FIELD_HEIGHT
        )

    def sync_config() -> None:
        config.baudrate = dropdowns[0].value
        config.working_mode = dropdowns[1].value
        config.mouse_relative = dropdowns[2].value
        config.manufacturer = text_inputs[0].value.strip() or USB_VENDOR_NAME
        config.product = text_inputs[1].value.strip() or USB_PRODUCT_NAME

    start_button = pygame.Rect(MENU_WIDTH - 230, MENU_HEIGHT - 70, 180, 46)

    pygame.init()
    pygame.key.set_repeat(300, 30)
    screen = pygame.display.set_mode((MENU_WIDTH, MENU_HEIGHT))
    pygame.display.set_caption("PyVIC – Konfiguration")
    font_title = pygame.font.SysFont(None, 40)
    font_item = pygame.font.SysFont(None, 28)
    font_hint = pygame.font.SysFont(None, 22)
    clock = pygame.time.Clock()

    selected = 0
    running = True
    started = False

    def close_all_dropdowns(except_dd=None) -> None:
        for dd in dropdowns:
            if dd is not except_dd:
                dd.open = False

    def deactivate_inputs(except_ti=None) -> None:
        for ti in text_inputs:
            if ti is not except_ti:
                ti.active = False

    while running:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == QUIT:
                running = False

            elif event.type == MOUSEBUTTONDOWN and event.button == 1:
                open_dd = next((dd for dd in dropdowns if dd.open), None)

                if open_dd is not None:
                    handled = False
                    for i, opt_rect in enumerate(open_dd.option_rects()):
                        if opt_rect.collidepoint(mouse_pos):
                            open_dd.index = i
                            open_dd.open = False
                            sync_config()
                            handled = True
                            break
                    if not handled:
                        open_dd.open = False
                        if not open_dd.rect.collidepoint(mouse_pos):
                            close_all_dropdowns()
                    continue

                clicked = False
                for index, dd in enumerate(dropdowns):
                    if dd.rect.collidepoint(mouse_pos):
                        close_all_dropdowns(except_dd=dd)
                        deactivate_inputs()
                        dd.open = not dd.open
                        selected = index
                        clicked = True
                        break

                if not clicked:
                    for index, ti in enumerate(text_inputs):
                        if ti.rect.collidepoint(mouse_pos):
                            close_all_dropdowns()
                            deactivate_inputs(except_ti=ti)
                            ti.active = True
                            selected = len(dropdowns) + index
                            clicked = True
                            break

                if not clicked:
                    if start_button.collidepoint(mouse_pos):
                        sync_config()
                        started = True
                        running = False
                    else:
                        close_all_dropdowns()
                        deactivate_inputs()

            elif event.type == MOUSEMOTION:
                for index, row in enumerate(rows):
                    if row.rect.collidepoint(mouse_pos):
                        selected = index
                        break

            elif event.type == pygame.KEYDOWN:
                active_input = next((ti for ti in text_inputs if ti.active), None)

                if active_input is not None:
                    if event.key == K_RETURN:
                        sync_config()
                        started = True
                        running = False
                    elif event.key in (K_ESCAPE, K_TAB):
                        active_input.active = False
                    else:
                        active_input.handle_key(event)
                    continue

                if event.key == K_ESCAPE:
                    running = False
                elif event.key == K_RETURN:
                    sync_config()
                    started = True
                    running = False
                elif event.key == K_UP:
                    close_all_dropdowns()
                    selected = (selected - 1) % len(rows)
                elif event.key == K_DOWN:
                    close_all_dropdowns()
                    selected = (selected + 1) % len(rows)

        # --- Drawing ---
        screen.fill(BG_COLOR)
        pygame.draw.rect(
            screen, PANEL_COLOR, (24, 24, MENU_WIDTH - 48, MENU_HEIGHT - 48),
            border_radius=10,
        )

        title = font_title.render("PyVIC Startkonfiguration", True, TEXT_COLOR)
        screen.blit(title, (LABEL_X, 48))
        hint = font_hint.render(
            "Auswahl per Maus · Namen als Text eingeben · Start zum Fortfahren",
            True,
            MUTED_COLOR,
        )
        screen.blit(hint, (LABEL_X, 92))

        # Labels and field bodies
        open_dd = None
        for index, row in enumerate(rows):
            label_color = ACCENT_COLOR if index == selected else TEXT_COLOR
            label_surface = font_item.render(f"{row.label}:", True, label_color)
            screen.blit(
                label_surface,
                (LABEL_X, row.rect.y + (FIELD_HEIGHT - label_surface.get_height()) // 2),
            )

            hovered = row.rect.collidepoint(mouse_pos)

            if isinstance(row, Dropdown):
                field_color = FIELD_HOVER_COLOR if hovered or row.open else FIELD_COLOR
                pygame.draw.rect(screen, field_color, row.rect, border_radius=6)
                pygame.draw.rect(screen, BORDER_COLOR, row.rect, width=1, border_radius=6)
                value_surface = font_item.render(row.header_text(), True, TEXT_COLOR)
                screen.blit(
                    value_surface,
                    (row.rect.x + 12, row.rect.y + (FIELD_HEIGHT - value_surface.get_height()) // 2),
                )
                arrow = "▴" if row.open else "▾"
                arrow_surface = font_item.render(arrow, True, MUTED_COLOR)
                screen.blit(
                    arrow_surface,
                    (row.rect.right - 28, row.rect.y + (FIELD_HEIGHT - arrow_surface.get_height()) // 2),
                )
                if row.open:
                    open_dd = row
            else:  # TextInput
                if row.active:
                    field_color = FIELD_ACTIVE_COLOR
                    border_color = ACTIVE_BORDER_COLOR
                elif hovered:
                    field_color = FIELD_HOVER_COLOR
                    border_color = BORDER_COLOR
                else:
                    field_color = FIELD_COLOR
                    border_color = BORDER_COLOR
                pygame.draw.rect(screen, field_color, row.rect, border_radius=6)
                pygame.draw.rect(screen, border_color, row.rect, width=2 if row.active else 1, border_radius=6)

                display_text = row.text if row.text else ""
                text_color = TEXT_COLOR if row.text else MUTED_COLOR
                shown = display_text if row.text else "(leer)"
                text_surface = font_item.render(shown, True, text_color)
                screen.blit(
                    text_surface,
                    (row.rect.x + 12, row.rect.y + (FIELD_HEIGHT - text_surface.get_height()) // 2),
                )
                if row.active:
                    caret_x = row.rect.x + 12 + font_item.size(display_text)[0] + 2
                    if (pygame.time.get_ticks() // 500) % 2 == 0:
                        pygame.draw.line(
                            screen,
                            TEXT_COLOR,
                            (caret_x, row.rect.y + 8),
                            (caret_x, row.rect.bottom - 8),
                            2,
                        )

        # Open dropdown list drawn last to overlay
        if open_dd is not None:
            for i, opt_rect in enumerate(open_dd.option_rects()):
                hovered = opt_rect.collidepoint(mouse_pos)
                bg = OPTION_HOVER_COLOR if hovered else FIELD_COLOR
                pygame.draw.rect(screen, bg, opt_rect)
                pygame.draw.rect(screen, BORDER_COLOR, opt_rect, width=1)
                opt_text = open_dd.display_fn(open_dd.options[i])
                opt_surface = font_item.render(opt_text, True, TEXT_COLOR)
                screen.blit(
                    opt_surface,
                    (opt_rect.x + 12, opt_rect.y + (OPTION_HEIGHT - opt_surface.get_height()) // 2),
                )

        # Start button
        btn_hovered = start_button.collidepoint(mouse_pos)
        pygame.draw.rect(
            screen,
            BUTTON_HOVER_COLOR if btn_hovered else BUTTON_COLOR,
            start_button,
            border_radius=8,
        )
        btn_label = font_item.render("Start", True, (255, 255, 255))
        screen.blit(
            btn_label,
            (
                start_button.centerx - btn_label.get_width() // 2,
                start_button.centery - btn_label.get_height() // 2,
            ),
        )

        footer = font_hint.render(
            "Serial und HID starten erst nach Klick auf Start (oder Enter).",
            True,
            MUTED_COLOR,
        )
        screen.blit(footer, (LABEL_X, MENU_HEIGHT - 58))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    if started:
        return config
    return None
