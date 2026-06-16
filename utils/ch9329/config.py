from enum import Enum

from serial import Serial

from .exceptions import ProtocolError
from .utils import get_packet

HEAD = b"\x57\xab"  # Frame header
ADDR = b"\x00"  # Address

CMD_GET_PARA_CFG = b"\x08"
LEN_GET_PARA_CFG = b"\x00"
DATA_GET_PARA_CFG = b""

CMD_SET_PARA_CFG = b"\x09"
LEN_SET_PARA_CFG = b"\x32"

USB_STRING_ENABLE_FLAG = b"\x87"

CMD_GET_USB_STRING = b"\x0a"
LEN_GET_USB_STRING = b"\x01"


class USBStringDescriptor(Enum):
    MANUFACTURER = b"\x00"
    PRODUCT = b"\x01"
    SERIAL_NUMBER = b"\x02"


CMD_SET_USB_STRING = b"\x0b"

PARA_CFG_DATA_LEN = 50
RESPONSE_SET_PARA_CFG = b"W\xab\x00\x89\x01\x00\x8c"


class WorkingMode(Enum):
    KEYBOARD_MOUSE_CUSTOM_HID = 0
    KEYBOARD_ONLY = 1
    KEYBOARD_MOUSE = 2
    CUSTOM_HID_ONLY = 3


class CommunicationMode(Enum):
    PROTOCOL = 0
    ASCII = 1
    TRANSPARENT = 2


def _read_para_cfg(ser: Serial) -> bytearray:
    ser.readall()
    packet = get_packet(
        HEAD, ADDR, CMD_GET_PARA_CFG, LEN_GET_PARA_CFG, DATA_GET_PARA_CFG
    )
    ser.write(packet)
    received_packet = ser.readline()
    if len(received_packet) < 56:
        raise ProtocolError(
            "expected at least 56 bytes in GET_PARA_CFG response, "
            f"received {len(received_packet)}"
        )
    return bytearray(received_packet[5:55])


def _write_para_cfg(ser: Serial, data: bytes) -> None:
    if len(data) != PARA_CFG_DATA_LEN:
        raise ValueError(
            f"expected {PARA_CFG_DATA_LEN} bytes of config data, got {len(data)}"
        )
    modified_packet = get_packet(
        HEAD, ADDR, CMD_SET_PARA_CFG, LEN_SET_PARA_CFG, data
    )
    ser.write(modified_packet)
    return_packet = ser.readline()
    if return_packet != RESPONSE_SET_PARA_CFG:
        raise ProtocolError(
            f"expected response {RESPONSE_SET_PARA_CFG}, received {return_packet}"
        )


def get_working_mode(ser: Serial) -> WorkingMode:
    return WorkingMode(_read_para_cfg(ser)[0])


def set_working_mode(ser: Serial, mode: WorkingMode) -> bool:
    config = _read_para_cfg(ser)
    if (
        config[0] == mode.value
        and config[1] == CommunicationMode.PROTOCOL.value
    ):
        return False
    config[0] = mode.value
    config[1] = CommunicationMode.PROTOCOL.value
    _write_para_cfg(ser, bytes(config))
    return True


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
    ser: Serial, descriptor_type: USBStringDescriptor, description: str
):
    if len(description) > 23:
        raise ValueError("length of description should not be more than 23")

    description_bytes = description.encode("utf-8")
    packet = get_packet(
        HEAD,
        ADDR,
        CMD_GET_USB_STRING,
        LEN_GET_USB_STRING,
        descriptor_type.value,
    )
    ser.write(packet)
    ser.readline()  # Read the response packet

    # Construct the packet for CMD_SET_USB_STRING
    descriptor_length = len(description_bytes)
    if descriptor_length == 0:
        descriptor_length = (
            1  # Ensure there's at least one byte for an empty string
        )

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
    return_packet = ser.readline()
    # this packet is expected in response when the VID and PID are
    # successfully set
    expected_packet = b"W\xab\x00\x8b\x01\x00\x8e"
    if return_packet != expected_packet:
        raise ProtocolError(
            f"expected: {expected_packet}, received: {return_packet}"
        )


def get_parameters(ser: Serial):
    # this packet is sent to ch9329 in response to which it sends the
    # current configuration
    packet = get_packet(
        HEAD, ADDR, CMD_GET_PARA_CFG, LEN_GET_PARA_CFG, DATA_GET_PARA_CFG
    )
    ser.write(packet)
    data = ser.readall()
    if not data:
        raise ProtocolError(f"expected a response, received nothing")
    return data


def get_usb_string(ser: Serial, descriptor: USBStringDescriptor):
    ser.readall()  # clear old packets
    packet = get_packet(
        HEAD,
        ADDR,
        CMD_GET_USB_STRING,
        LEN_GET_USB_STRING,
        descriptor.value,
    )
    ser.write(packet)
    data = ser.readall()
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
