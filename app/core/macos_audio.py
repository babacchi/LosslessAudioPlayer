"""macOS CoreAudio native bindings via ctypes for bit-perfect hardware clock switching."""
import platform
import struct
import time
from typing import Optional, List, Dict

IS_MACOS = platform.system() == "Darwin"

if IS_MACOS:
    import ctypes
    import ctypes.util

    ca_path = ctypes.util.find_library("CoreAudio") or "/System/Library/Frameworks/CoreAudio.framework/CoreAudio"
    cf_path = ctypes.util.find_library("CoreFoundation") or "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"

    ca = ctypes.cdll.LoadLibrary(ca_path)
    cf = ctypes.cdll.LoadLibrary(cf_path)

    cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
    cf.CFStringGetCString.restype = ctypes.c_bool
    cf.CFRelease.argtypes = [ctypes.c_void_p]

    class AudioObjectPropertyAddress(ctypes.Structure):
        _fields_ = [
            ("mSelector", ctypes.c_uint32),
            ("mScope", ctypes.c_uint32),
            ("mElement", ctypes.c_uint32)
        ]

    class AudioValueRange(ctypes.Structure):
        _fields_ = [
            ("mMinimum", ctypes.c_double),
            ("mMaximum", ctypes.c_double)
        ]

    def _fourcc(s: str) -> int:
        return struct.unpack(">I", s.encode("ascii"))[0]

    PROP_DEVICES = _fourcc("dev#")
    PROP_NAME = _fourcc("lnam")
    PROP_NOMINAL_SAMPLE_RATE = _fourcc("nsrt")
    PROP_AVAILABLE_SAMPLE_RATES = _fourcc("nsr#")
    SCOPE_GLOBAL = _fourcc("glob")
    ELEMENT_MAIN = 0


def get_coreaudio_devices_map() -> Dict[str, int]:
    """Map device name (trimmed) to CoreAudio AudioDeviceID."""
    if not IS_MACOS:
        return {}

    try:
        addr = AudioObjectPropertyAddress(PROP_DEVICES, SCOPE_GLOBAL, ELEMENT_MAIN)
        size = ctypes.c_uint32(0)
        ca.AudioObjectGetPropertyDataSize(1, ctypes.byref(addr), 0, None, ctypes.byref(size))
        count = size.value // ctypes.sizeof(ctypes.c_uint32)
        device_ids = (ctypes.c_uint32 * count)()
        ca.AudioObjectGetPropertyData(1, ctypes.byref(addr), 0, None, ctypes.byref(size), device_ids)

        mapping = {}
        for dev_id in device_ids:
            name_addr = AudioObjectPropertyAddress(PROP_NAME, SCOPE_GLOBAL, ELEMENT_MAIN)
            cf_str = ctypes.c_void_p()
            str_size = ctypes.c_uint32(ctypes.sizeof(ctypes.c_void_p))
            res = ca.AudioObjectGetPropertyData(
                dev_id, ctypes.byref(name_addr), 0, None, ctypes.byref(str_size), ctypes.byref(cf_str)
            )
            if res == 0 and cf_str.value:
                buf = ctypes.create_string_buffer(256)
                if cf.CFStringGetCString(cf_str, buf, 256, 0x08000100):
                    name = buf.value.decode("utf-8").strip()
                    mapping[name] = int(dev_id)
                cf.CFRelease(cf_str)
        return mapping
    except Exception:
        return {}


def find_coreaudio_device_id(device_name: str) -> Optional[int]:
    """Find CoreAudio AudioDeviceID by matching sounddevice device name."""
    if not IS_MACOS or not device_name:
        return None

    clean_name = device_name.strip()
    mapping = get_coreaudio_devices_map()

    # 1. Exact match
    if clean_name in mapping:
        return mapping[clean_name]

    # 2. Substring match
    for name, dev_id in mapping.items():
        if clean_name.lower() in name.lower() or name.lower() in clean_name.lower():
            return dev_id

    return None


def get_device_sample_rate(device_id: int) -> Optional[float]:
    """Read current hardware sample rate from CoreAudio device."""
    if not IS_MACOS:
        return None

    try:
        sr_addr = AudioObjectPropertyAddress(PROP_NOMINAL_SAMPLE_RATE, SCOPE_GLOBAL, ELEMENT_MAIN)
        sr = ctypes.c_double(0.0)
        sr_size = ctypes.c_uint32(ctypes.sizeof(ctypes.c_double))
        res = ca.AudioObjectGetPropertyData(
            device_id, ctypes.byref(sr_addr), 0, None, ctypes.byref(sr_size), ctypes.byref(sr)
        )
        if res == 0:
            return float(sr.value)
    except Exception:
        pass
    return None


def set_device_sample_rate(device_id: int, target_rate: float) -> bool:
    """
    Set hardware clock nominal sample rate on CoreAudio DAC.
    Returns True if hardware sample rate matches target_rate after switching.
    """
    if not IS_MACOS:
        return False

    try:
        current_rate = get_device_sample_rate(device_id)
        if current_rate is not None and abs(current_rate - target_rate) < 1.0:
            return True

        sr_addr = AudioObjectPropertyAddress(PROP_NOMINAL_SAMPLE_RATE, SCOPE_GLOBAL, ELEMENT_MAIN)
        target = ctypes.c_double(float(target_rate))
        sr_size = ctypes.c_uint32(ctypes.sizeof(ctypes.c_double))

        res = ca.AudioObjectSetPropertyData(
            device_id, ctypes.byref(sr_addr), 0, None, sr_size, ctypes.byref(target)
        )
        if res != 0:
            return False

        # Wait up to 500ms for hardware PLL clock to lock
        for _ in range(10):
            time.sleep(0.05)
            rate = get_device_sample_rate(device_id)
            if rate is not None and abs(rate - target_rate) < 1.0:
                return True

        return False
    except Exception:
        return False
