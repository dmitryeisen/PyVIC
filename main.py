import asyncio
import pygame
from pygame.locals import *
from ch9329 import keyboard, mouse
from serial import Serial
import cv2
import sys
import serial.tools.list_ports
import threading
from utils import map_to_de, detect_keyboard_layout


def find_usbserial_port():
    """
    Searches for a serial device with 'usbserial' in the name.
    Works on Linux and macOS.
    """
    ports = serial.tools.list_ports.comports()
    usbserial_ports = [
        port.device for port in ports if "usbserial" in port.device.lower() or "ttyusb" in port.device.lower()
    ]

    if len(usbserial_ports) == 1:
        return usbserial_ports[0]
    elif len(usbserial_ports) == 0:
        raise Exception("No USB-serial device found.")
    else:
        raise Exception("Multiple USB-serial devices found. Please specify.")


# Setup für den seriellen Anschluss (Anpassung für dein Gerät)
def setup_ch9329_serial():
    try:
        port = find_usbserial_port()
        ser = Serial(port=port, baudrate=9600, timeout=0, write_timeout=0.1)
        print("CH9329 connected.")
        return ser
    except Exception as e:
        print(f"Error CH9329: {e}")
        return None


latest_frame = None
frame_lock = threading.Lock()
stop_capture = False  # Kontrollvariable für Thread
layout = "us"


def capture_frames_thread(cap):
    global latest_frame, stop_capture
    while not stop_capture:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        with frame_lock:
            latest_frame = frame


async def test_unit(serial_conn, frame_width, frame_height, layout):
    global latest_frame
    pygame.init()
    # screen = pygame.display.set_mode((frame_width, frame_height))
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
                await handle_pygame_event(serial_conn, event, layout)

        with frame_lock:
            if latest_frame is not None:
                frame_surface = pygame.surfarray.make_surface(latest_frame.swapaxes(0, 1))
                # frame_surface = pygame.image.frombuffer(latest_frame.tobytes(), latest_frame.shape[1::-1], "RGB")
                screen.blit(frame_surface, (0, 0))

        pygame.display.flip()
        clock.tick(60)

async def handle_pygame_event(serial_conn, event, layout):
    if event.type == KEYDOWN:
        key_code = event.unicode
        special_key = {
            pygame.K_RETURN: "enter",
            pygame.K_BACKSPACE: "backspace",
            pygame.K_DELETE: "delete",
            pygame.K_TAB: "tab",
            pygame.K_ESCAPE: "escape",
            pygame.K_UP: "arrow_up",
            pygame.K_DOWN: "arrow_down",
            pygame.K_LEFT: "arrow_left",
            pygame.K_RIGHT: "arrow_right",
        }.get(event.key, None)
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
            print(f"Fehler beim Senden von KEYDOWN: {e}")

    elif event.type == KEYUP:
        key_code = event.unicode
        try:
            if key_code:
                keyboard.release(serial_conn)
        except Exception as e:
            print(f"Fehler beim Senden von KEYUP: {e}")

    elif event.type == MOUSEBUTTONDOWN:
        # Translate Pygame-Mouse-Buttons to CH9329-Button
        mouse_button_map = {1: "left", 2: "middle", 3: "right"}
        mouse_button = mouse_button_map.get(event.button, None)
        if mouse_button:
            try:
                mouse.click(serial_conn, mouse_button)
            except Exception as e:
                print(f"Fehler beim Senden von MOUSEBUTTONDOWN: {e}")
        else:
            print(f"Unbekannter Mausbutton: {event.button}")

    elif event.type == MOUSEBUTTONUP:
        mouse_button = event.button
        try:
            mouse.release(serial_conn)
        except Exception as e:
            print(f"Fehler beim Senden von MOUSEBUTTONUP: {e}")
    elif event.type == MOUSEMOTION:
        abs_x, abs_y = event.pos  # Absolute Mausposition im Fenster
        try:
            mouse.move(serial_conn, abs_x, abs_y, relative=False)  # relative=False für absolute Bewegung
        except Exception as e:
            print(f"Fehler beim Senden von absoluter MOUSEMOTION: {e}")
        """
        Relative Mouse
        dx, dy = event.rel  # Relative Bewegung der Maus
        dx = max(min(dx, 127), -127)  # CH9329 max. Werte von -127 bis 127
        dy = max(min(dy, 127), -127)
        # print(f"Maus bewegt: dx={dx}, dy={dy}")
        try:
            mouse.move(serial_conn, dx, dy, relative=True)
        except Exception as e:
            print(f"Fehler beim Senden von MOUSEMOTION: {e}")

        """


async def main():
    global layout
    global stop_capture
    layout = detect_keyboard_layout()
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Fehler beim Öffnen der Kamera.")
        sys.exit()
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    capture_thread = threading.Thread(target=capture_frames_thread, args=(cap,), daemon=True)
    capture_thread.start()
    serial_conn = setup_ch9329_serial()
    if serial_conn:
        try:
            await test_unit(serial_conn, frame_width, frame_height, layout)
        finally:
            stop_capture = True
            capture_thread.join()
            cap.release()
            pygame.quit()
            print("Verbindung und Kamera geschlossen.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Programm beendet durch Benutzer.")
    finally:
        pygame.quit()
