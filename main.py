import asyncio
import pygame
from pygame.locals import *
from utils.ch9329 import keyboard, mouse
from utils.ch9329.config import (
    USB_PRODUCT_NAME,
    USB_VENDOR_NAME,
    WORKING_MODE_LABELS,
    apply_working_mode,
    connect_and_configure,
    find_ch9329_port,
    set_usb_identity,
)
from utils.ch9329.exceptions import ProtocolError
from utils.startup_menu import StartupConfig, run_startup_menu
import cv2
import sys
import threading
from utils import map_to_de, detect_keyboard_layout


def setup_ch9329_serial(config: StartupConfig):
    port = find_ch9329_port()
    print(f"CH9329 port: {port}")
    ser, active_baudrate, changed, method = connect_and_configure(
        port, config.working_mode, config.baudrate
    )
    mode_label = WORKING_MODE_LABELS[config.working_mode]

    if method.startswith("hid_only"):
        print(
            f"Warnung: Modus-Config beim Start fehlgeschlagen. "
            f"HID startet trotzdem ({active_baudrate} baud)."
        )

    manufacturer = config.manufacturer
    product = config.product
    identity_method = set_usb_identity(ser, manufacturer, product)
    if identity_method == "confirmed":
        print(f"USB gesetzt: Hersteller={manufacturer}, Produkt={product}")
    else:
        print(
            f"USB gesendet: Hersteller={manufacturer}, Produkt={product}. "
            "USB am Zielrechner neu verbinden."
        )

    if method.startswith("hid_only"):
        try:
            changed = apply_working_mode(ser, config.working_mode)
            method = "read_write_retry"
        except ProtocolError as error:
            print(f"Moduswechsel weiterhin fehlgeschlagen: {error}")
            changed = False

    if method == "read_write" and not changed:
        print(f"CH9329 Modus bereits aktiv: {mode_label}, {active_baudrate} baud.")
    elif changed:
        print(
            f"CH9329 Modus gesetzt ({method}): {mode_label}, {active_baudrate} baud. "
            "USB am Zielrechner neu verbinden."
        )
    elif not method.startswith("hid_only"):
        print(f"CH9329 verbunden ({method}): {mode_label}, {active_baudrate} baud.")

    if active_baudrate != config.baudrate:
        print(
            f"Hinweis: verbunden mit {active_baudrate} baud "
            f"(Menü: {config.baudrate})."
        )
    return ser


latest_frame = None
frame_lock = threading.Lock()
stop_capture = False
layout = "us"

SPECIAL_KEYS = {
    pygame.K_RETURN: "enter",
    pygame.K_BACKSPACE: "backspace",
    pygame.K_DELETE: "delete",
    pygame.K_TAB: "tab",
    pygame.K_ESCAPE: "escape",
    pygame.K_UP: "arrow_up",
    pygame.K_DOWN: "arrow_down",
    pygame.K_LEFT: "arrow_left",
    pygame.K_RIGHT: "arrow_right",
}


def capture_frames_thread(cap):
    global latest_frame, stop_capture
    while not stop_capture:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        with frame_lock:
            latest_frame = frame


async def test_unit(serial_conn, frame_width, frame_height, layout, config: StartupConfig):
    global latest_frame
    pygame.init()
    pygame.event.clear()
    screen = pygame.display.set_mode((frame_width, frame_height), pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption("PyVIC")
    pygame.mouse.set_visible(False)
    clock = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type in {MOUSEMOTION, MOUSEBUTTONDOWN, MOUSEBUTTONUP, KEYDOWN, KEYUP}:
                await handle_pygame_event(
                    serial_conn, event, layout, config, frame_width, frame_height
                )

        with frame_lock:
            if latest_frame is not None:
                frame_surface = pygame.surfarray.make_surface(latest_frame.swapaxes(0, 1))
                screen.blit(frame_surface, (0, 0))

        pygame.display.flip()
        clock.tick(60)


async def handle_pygame_event(
    serial_conn, event, layout, config: StartupConfig, frame_width, frame_height
):
    if event.type == MOUSEMOTION:
        if config.mouse_relative:
            dx, dy = event.rel
            dx = max(min(dx, 127), -127)
            dy = max(min(dy, 127), -127)
            try:
                mouse.move(serial_conn, dx, dy, relative=True)
            except Exception as e:
                print(f"Error while sending relative MOUSEMOTION: {e}")
        else:
            abs_x, abs_y = event.pos
            try:
                mouse.move(
                    serial_conn,
                    abs_x,
                    abs_y,
                    relative=False,
                    monitor_width=frame_width,
                    monitor_height=frame_height,
                )
            except Exception as e:
                print(f"Error while sending absolute MOUSEMOTION: {e}")

    elif event.type == KEYDOWN:
        special_key = SPECIAL_KEYS.get(event.key)
        key_code = event.unicode
        try:
            if special_key:
                keyboard.press(serial_conn, special_key)
            elif key_code:
                if layout == "de":
                    key_to_send = map_to_de(key_code)
                    keyboard.press(serial_conn, key_to_send)
                else:
                    keyboard.press(serial_conn, key_code)
        except Exception as e:
            print(f"Error while sending KEYDOWN: {e}")

    elif event.type == KEYUP:
        try:
            keyboard.release(serial_conn)
        except Exception as e:
            print(f"Error while sending KEYUP: {e}")

    elif event.type == MOUSEBUTTONDOWN:
        mouse_button_map = {1: "left", 2: "middle", 3: "right"}
        mouse_button = mouse_button_map.get(event.button, None)
        if mouse_button:
            try:
                mouse.click(serial_conn, mouse_button)
            except Exception as e:
                print(f"Error while sending MOUSEBUTTONDOWN: {e}")
        else:
            print(f"Unknown mouse button: {event.button}")

    elif event.type == MOUSEBUTTONUP:
        try:
            mouse.release(serial_conn)
        except Exception as e:
            print(f"Error while sending MOUSEBUTTONUP: {e}")


async def main():
    global layout
    global stop_capture

    config = run_startup_menu()
    if config is None:
        print("Start abgebrochen.")
        return

    layout = detect_keyboard_layout()

    try:
        serial_conn = setup_ch9329_serial(config)
    except Exception as e:
        print(f"Error CH9329: {e}")
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error while opening the camera.")
        serial_conn.close()
        sys.exit()
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    capture_thread = threading.Thread(target=capture_frames_thread, args=(cap,), daemon=True)
    capture_thread.start()

    try:
        await test_unit(serial_conn, frame_width, frame_height, layout, config)
    finally:
        stop_capture = True
        capture_thread.join()
        cap.release()
        serial_conn.close()
        pygame.quit()
        print("Connection and camera closed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program terminated by user.")
    finally:
        pygame.quit()
