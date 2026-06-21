from enum import Enum
import time

import serial.tools.list_ports
from serial import Serial

from .exceptions import ProtocolError
from .utils import get_packet

HEAD = b"\x57\xab"
ADDR = b"\x00"

# Wichtig! auf lizenz achten
CH9329_VID = 0x1A86
CH9329_PID = 0x7523

CMD_GET_INFO = b"\x01"
LEN_GET_INFO = b"\x00"

CMD_GET_PARA_CFG = b"\x08"
LEN_GET_PARA_CFG = b"\x00"
DATA_GET_PARA_CFG = b""

CMD_SET_PARA_CFG = b"\x09"
LEN_SET_PARA_CFG = b"\x32"

CMD_SET_DEFAULT_CFG = b"\x0c"
LEN_SET_DEFAULT_CFG = b"\x00"

USB_STRING_ENABLE_FLAG = b"\x87"

CMD_GET_USB_STRING = b"\x0a"
LEN_GET_USB_STRING = b"\x01"


class USBStringDescriptor(Enum):
    MANUFACTURER = b"\x00"
    PRODUCT = b"\x01"
    SERIAL_NUMBER = b"\x02"


CMD_SET_USB_STRING = b"\x0b"

PARA_CFG_DATA_LEN = 50
GET_PARA_CFG_RESPONSE_LEN = 56
SET_PARA_CFG_RESPONSE_LEN = 7
RESPONSE_SET_PARA_CFG = b"W\xab\x00\x89\x01\x00\x8c"
RESPONSE_SET_DEFAULT_CFG = b"W\xab\x00\x8c\x01\x00\x8f"
CONFIG_IO_TIMEOUT = 1.0
SERIAL_OPEN_DELAY = 0.3
CONFIG_RETRY_COUNT = 3
CONFIG_PROBE_RETRIES = 3

# Template only used when read-modify-write is impossible.
FACTORY_PARA_CFG = bytes(
    [
        0x00,
        0x00,
        0x00,
        0x80,
        0x25,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x86,
        0x1A,
        0x29,
        0xE1,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
    ]
)


class WorkingMode(Enum):
    KEYBOARD_MOUSE_CUSTOM_HID = 0
    KEYBOARD_ONLY = 1
    KEYBOARD_MOUSE = 2
    CUSTOM_HID_ONLY = 3


WORKING_MODE_LABELS = {
    WorkingMode.KEYBOARD_MOUSE_CUSTOM_HID: "0: Tastatur + Maus + Custom HID",
    WorkingMode.KEYBOARD_ONLY: "1: USB Tastatur",
    WorkingMode.KEYBOARD_MOUSE: "2: USB Tastatur + Maus",
    WorkingMode.CUSTOM_HID_ONLY: "3: Custom HID",
}

DEFAULT_BAUDRATES = (9600, 19200, 38400, 57600, 115200)
USB_VENDOR_NAME = "PyVIC"
USB_PRODUCT_NAME = "PyVIC HID"


class CommunicationMode(Enum):
    PROTOCOL = 0
    ASCII = 1
    TRANSPARENT = 2


def find_ch9329_port() -> str:
    ports = list(serial.tools.list_ports.comports())
    ch9329_ports = [port for port in ports if port.vid == CH9329_VID and port.pid == CH9329_PID]

    if ch9329_ports:
        cu_ports = [port.device for port in ch9329_ports if "/cu." in port.device]
        if cu_ports:
            return cu_ports[0]
        return ch9329_ports[0].device

    fallback_ports = [
        port.device
        for port in ports
        if "usbserial" in port.device.lower() or "ttyusb" in port.device.lower()
    ]
    cu_fallback = [device for device in fallback_ports if "/cu." in device]
    if cu_fallback:
        fallback_ports = cu_fallback + [
            device for device in fallback_ports if device not in cu_fallback
        ]

    if len(fallback_ports) == 1:
        return fallback_ports[0]
    if not fallback_ports:
        raise RuntimeError("No CH9329 serial device found.")
    raise RuntimeError(
        "Multiple serial devices found. Connect only one CH9329 or use VID 1A86 / PID 7523."
    )


def prepare_serial_port(ser: Serial, config_mode: bool = False) -> None:
    # NOTE: do NOT toggle DTR/RTS here. On common USB-serial adapters this
    # resets/disturbs the CH9329 so it stops answering GET_PARA_CFG (0 bytes).
    # The working version never touched these lines.
    time.sleep(SERIAL_OPEN_DELAY)
    if hasattr(ser, "reset_input_buffer"):
        ser.reset_input_buffer()
    elif ser.in_waiting:
        ser.read(ser.in_waiting)
    if hasattr(ser, "reset_output_buffer"):
        ser.reset_output_buffer()


def _clear_input(ser: Serial) -> None:
    if hasattr(ser, "reset_input_buffer"):
        ser.reset_input_buffer()
    elif ser.in_waiting:
        ser.read(ser.in_waiting)


def _read_response(ser: Serial, min_length: int = 1) -> bytes:
    old_timeout = ser.timeout
    ser.timeout = CONFIG_IO_TIMEOUT
    try:
        deadline = time.monotonic() + CONFIG_IO_TIMEOUT
        data = bytearray()
        while time.monotonic() < deadline:
            waiting = ser.in_waiting
            if waiting:
                data.extend(ser.read(waiting))
            if len(data) >= min_length:
                break
            time.sleep(0.02)
        if len(data) < min_length:
            line = ser.readline()
            if line:
                data.extend(line)
        return bytes(data)
    finally:
        ser.timeout = old_timeout


def _extract_para_cfg(data: bytes) -> bytearray | None:
    if len(data) < GET_PARA_CFG_RESPONSE_LEN:
        return None
    for offset in range(len(data) - GET_PARA_CFG_RESPONSE_LEN + 1):
        chunk = data[offset : offset + GET_PARA_CFG_RESPONSE_LEN]
        if chunk[:2] == HEAD and chunk[2:3] == ADDR and chunk[3:4] == b"\x88":
            return bytearray(chunk[5:55])
    return None


def probe_chip(ser: Serial) -> bool:
    packet = get_packet(HEAD, ADDR, CMD_GET_INFO, LEN_GET_INFO, b"")
    _clear_input(ser)
    ser.write(packet)
    ser.flush()
    time.sleep(0.1)
    data = _read_response(ser, min_length=6)
    return len(data) >= 6 and data[:2] == HEAD


def _read_para_cfg(ser: Serial, retries: int = CONFIG_RETRY_COUNT) -> bytearray:
    packet = get_packet(
        HEAD, ADDR, CMD_GET_PARA_CFG, LEN_GET_PARA_CFG, DATA_GET_PARA_CFG
    )
    last_error: ProtocolError | None = None

    for attempt in range(retries):
        _clear_input(ser)
        ser.write(packet)
        ser.flush()
        time.sleep(0.08 + attempt * 0.05)

        old_timeout = ser.timeout
        ser.timeout = CONFIG_IO_TIMEOUT
        try:
            data = ser.readline()
            if len(data) < GET_PARA_CFG_RESPONSE_LEN:
                data += ser.readall()
        finally:
            ser.timeout = old_timeout

        config = _extract_para_cfg(data)
        if config is not None:
            return config
        last_error = ProtocolError(
            f"expected {GET_PARA_CFG_RESPONSE_LEN} bytes in GET_PARA_CFG response, "
            f"received {len(data)}"
        )

    assert last_error is not None
    raise last_error


def _write_para_cfg(ser: Serial, data: bytes, require_ack: bool = True) -> None:
    if len(data) != PARA_CFG_DATA_LEN:
        raise ValueError(
            f"expected {PARA_CFG_DATA_LEN} bytes of config data, got {len(data)}"
        )
    modified_packet = get_packet(
        HEAD, ADDR, CMD_SET_PARA_CFG, LEN_SET_PARA_CFG, data
    )
    _clear_input(ser)
    ser.write(modified_packet)
    ser.flush()
    if not require_ack:
        time.sleep(0.8)
        return

    time.sleep(0.15)
    return_packet = _read_response(ser, min_length=SET_PARA_CFG_RESPONSE_LEN)
    if RESPONSE_SET_PARA_CFG not in return_packet:
        raise ProtocolError(
            f"expected response {RESPONSE_SET_PARA_CFG!r}, received {return_packet!r}"
        )


def restore_factory_defaults(ser: Serial) -> None:
    packet = get_packet(
        HEAD, ADDR, CMD_SET_DEFAULT_CFG, LEN_SET_DEFAULT_CFG, b""
    )
    _clear_input(ser)
    ser.write(packet)
    ser.flush()
    time.sleep(0.4)
    response = _read_response(ser, min_length=SET_PARA_CFG_RESPONSE_LEN)
    if RESPONSE_SET_DEFAULT_CFG not in response:
        raise ProtocolError(
            f"factory reset failed, received {response!r}"
        )


def build_para_cfg(mode: WorkingMode, base: bytes | bytearray | None = None) -> bytes:
    config = bytearray(base if base is not None else FACTORY_PARA_CFG)
    config[0] = mode.value
    config[1] = CommunicationMode.PROTOCOL.value
    return bytes(config)


def apply_working_mode(ser: Serial, mode: WorkingMode) -> bool:
    config = _read_para_cfg(ser)
    changed = config[0] != mode.value or config[1] != CommunicationMode.PROTOCOL.value
    if not changed:
        return False
    config[0] = mode.value
    config[1] = CommunicationMode.PROTOCOL.value
    try:
        _write_para_cfg(ser, bytes(config), require_ack=True)
    except ProtocolError:
        _write_para_cfg(ser, bytes(config), require_ack=False)
    return True


def enable_usb_strings_in_config(ser: Serial) -> bool:
    config = _read_para_cfg(ser)
    if config[36] == USB_STRING_ENABLE_FLAG[0]:
        return False
    config[36] = USB_STRING_ENABLE_FLAG[0]
    try:
        _write_para_cfg(ser, bytes(config), require_ack=True)
    except ProtocolError:
        _write_para_cfg(ser, bytes(config), require_ack=False)
    return True


def blind_set_working_mode(ser: Serial, mode: WorkingMode, require_ack: bool = False) -> None:
    config = _read_para_cfg(ser)
    config[0] = mode.value
    config[1] = CommunicationMode.PROTOCOL.value
    _write_para_cfg(ser, bytes(config), require_ack=require_ack)


def get_working_mode(ser: Serial) -> WorkingMode:
    return WorkingMode(_read_para_cfg(ser)[0])


def set_working_mode(ser: Serial, mode: WorkingMode) -> bool:
    return apply_working_mode(ser, mode)


def apply_device_config(ser: Serial, mode: WorkingMode) -> bool:
    return apply_working_mode(ser, mode)


def _try_configure_mode(ser: Serial, mode: WorkingMode) -> tuple[bool, str]:
    prepare_serial_port(ser)
    config = _read_para_cfg(ser, retries=CONFIG_PROBE_RETRIES)
    try:
        current = WorkingMode(config[0] & 0x7F)
        print(
            f"CH9329 aktueller Modus: {current.value} "
            f"({WORKING_MODE_LABELS[current]})"
        )
    except ValueError:
        print(f"CH9329 aktueller Modus: unbekannt (raw={config[0]})")

    changed = config[0] != mode.value or config[1] != CommunicationMode.PROTOCOL.value
    if changed:
        config[0] = mode.value
        config[1] = CommunicationMode.PROTOCOL.value
        _write_para_cfg(ser, bytes(config), require_ack=True)
    return changed, "read_write"


def connect_and_configure(
    port: str, mode: WorkingMode, preferred_baudrate: int = 9600
) -> tuple[Serial, int, bool, str]:
    baudrates = [preferred_baudrate]
    if preferred_baudrate != 9600:
        baudrates.append(9600)

    last_error: Exception | None = None
    for baudrate in baudrates:
        ser = None
        try:
            ser = Serial(
                port=port,
                baudrate=baudrate,
                timeout=CONFIG_IO_TIMEOUT,
                write_timeout=0.3,
            )
            changed, method = _try_configure_mode(ser, mode)
            ser.timeout = 0
            ser.write_timeout = 0.1
            return ser, baudrate, changed, method
        except Exception as error:
            last_error = error
            if ser and ser.is_open:
                ser.close()

    ser = Serial(
        port=port,
        baudrate=preferred_baudrate,
        timeout=0,
        write_timeout=0.1,
    )
    prepare_serial_port(ser, config_mode=False)
    return ser, preferred_baudrate, False, f"hid_only: {last_error}"


def configure_keyboard_mouse_only(ser: Serial) -> bool:
    changed = set_working_mode(ser, WorkingMode.KEYBOARD_MOUSE)
    if changed:
        print(
            "CH9329 configured for USB keyboard + mouse (mode 2). "
            "Reconnect USB if the device does not respond."
        )
    else:
        print("CH9329 already in USB keyboard + mouse mode (mode 2).")
    return changed


def set_device_descriptors(
    ser: Serial,
    descriptor_type: USBStringDescriptor,
    description: str,
    require_ack: bool = True,
):
    if len(description) > 23:
        raise ValueError("length of description should not be more than 23")

    description_bytes = description.encode("utf-8")
    get_packet_cmd = get_packet(
        HEAD,
        ADDR,
        CMD_GET_USB_STRING,
        LEN_GET_USB_STRING,
        descriptor_type.value,
    )
    _clear_input(ser)
    ser.write(get_packet_cmd)
    ser.flush()
    time.sleep(0.2 if not require_ack else 0.1)
    if require_ack:
        _read_response(ser, min_length=7)

    descriptor_length = len(description_bytes) or 1
    modified_data = (
        bytes([descriptor_type.value[0]])
        + bytes([descriptor_length])
        + description_bytes
    )
    modified_packet = get_packet(
        HEAD,
        ADDR,
        CMD_SET_USB_STRING,
        bytes([len(modified_data)]),
        modified_data,
    )
    ser.write(modified_packet)
    ser.flush()
    time.sleep(0.5 if not require_ack else 0.15)
    if require_ack:
        return_packet = _read_response(ser, min_length=7)
        expected_packet = b"W\xab\x00\x8b\x01\x00\x8e"
        if expected_packet not in return_packet:
            raise ProtocolError(
                f"expected: {expected_packet}, received: {return_packet}"
            )


def set_usb_identity(
    ser: Serial,
    manufacturer: str = USB_VENDOR_NAME,
    product: str = USB_PRODUCT_NAME,
) -> str:
    prepare_serial_port(ser, config_mode=True)
    try:
        enable_usb_strings_in_config(ser)
    except ProtocolError:
        print("Hinweis: USB-String-Flag konnte nicht gesetzt werden.")

    try:
        set_device_descriptors(
            ser, USBStringDescriptor.MANUFACTURER, manufacturer
        )
        set_device_descriptors(ser, USBStringDescriptor.PRODUCT, product)
        prepare_serial_port(ser, config_mode=False)
        return "confirmed"
    except ProtocolError:
        set_device_descriptors(
            ser,
            USBStringDescriptor.MANUFACTURER,
            manufacturer,
            require_ack=False,
        )
        set_device_descriptors(
            ser,
            USBStringDescriptor.PRODUCT,
            product,
            require_ack=False,
        )
        prepare_serial_port(ser, config_mode=False)
        return "sent"


def get_parameters(ser: Serial):
    packet = get_packet(
        HEAD, ADDR, CMD_GET_PARA_CFG, LEN_GET_PARA_CFG, DATA_GET_PARA_CFG
    )
    ser.write(packet)
    data = _read_response(ser, min_length=1)
    if not data:
        raise ProtocolError("expected a response, received nothing")
    return data


def get_usb_string(ser: Serial, descriptor: USBStringDescriptor):
    _clear_input(ser)
    packet = get_packet(
        HEAD,
        ADDR,
        CMD_GET_USB_STRING,
        LEN_GET_USB_STRING,
        descriptor.value,
    )
    ser.write(packet)
    data = _read_response(ser, min_length=7)
    if len(data) < 7:
        raise ProtocolError(
            f"expected a response of a least 7 bytes, received {len(data)} bytes"
        )
    length = data[6]
    return data[7 : 7 + length].decode()


def get_serial_number(ser: Serial):
    return get_usb_string(ser, USBStringDescriptor.SERIAL_NUMBER)


def get_manufacturer(ser: Serial):
    return get_usb_string(ser, USBStringDescriptor.MANUFACTURER)


def get_product(ser: Serial):
    return get_usb_string(ser, USBStringDescriptor.PRODUCT)


def set_device_ids(
    ser: Serial, vid: int, pid: int, custom_descriptor: bool = False
):
    config = _read_para_cfg(ser)
    vid_bytes = vid.to_bytes(2, "little")
    pid_bytes = pid.to_bytes(2, "little")
    config[11:13] = vid_bytes
    config[13:15] = pid_bytes
    if custom_descriptor:
        config[36] = USB_STRING_ENABLE_FLAG[0]
    _write_para_cfg(ser, bytes(config))
