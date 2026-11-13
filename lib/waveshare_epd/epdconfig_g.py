# *****************************************************************************
# * | File        :   epdconfig_g.py
# * | Function    :   Hardware interface for the 10.85inch e-Paper (G)
# * | Info        :   Wraps Waveshare's DEV_Config shared library (bcm2835 /
# * |                 lgpio based), copied from Waveshare's
# * |                 E-paper_Separate_Program/10.85inch_e-Paper_G demo.
# *----------------
# * | Why not the gpiozero/spidev epdconfig used for the B/W panel?
# * |   The (G) controllers ignore commands sent through the kernel spidev
# * |   driver (hardware CE0/CE1): BUSY never asserts and nothing refreshes.
# * |   Waveshare's library drives both chip selects as plain GPIOs, which the
# * |   panel requires, so the (G) driver uses it unchanged.
# ******************************************************************************/
import ctypes
import os
import time

EPD_SCK_PIN  = 11
EPD_MOSI_PIN = 10
EPD_CS_M_PIN = 8
EPD_CS_S_PIN = 7
EPD_DC_PIN   = 25
EPD_RST_PIN  = 17
EPD_BUSY_PIN = 24
EPD_PWR_PIN  = 18

_LIB_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'epd10in85g_lib')


def _load_library():
    bits = 64 if ctypes.sizeof(ctypes.c_void_p) == 8 else 32
    try:
        with open('/proc/device-tree/model', 'rb') as f:
            model = f.read().decode(errors='ignore')
    except OSError:
        model = ''
    # '_w' build is for the Raspberry Pi 5 (RP1), '_b' for every earlier Pi.
    variant = 'w' if 'Raspberry Pi 5' in model else 'b'
    path = os.path.join(_LIB_DIR, f'DEV_Config_{bits}_{variant}.so')
    if not os.path.exists(path):
        raise RuntimeError(f'10.85in (G) driver library not found: {path}')
    return ctypes.CDLL(path)


_lib = _load_library()


def digital_write(pin, value):
    _lib.DEV_Digital_Write(pin, value)


def digital_read(pin):
    return _lib.DEV_Digital_Read(pin)


def spi_writebyte(value):
    _lib.DEV_SPI_SendData(value)


def spi_writebytes(buf):
    n = len(buf)
    arr = (ctypes.c_ubyte * n).from_buffer_copy(bytes(buf))
    _lib.DEV_SPI_SendData_nByte(arr, ctypes.c_ulong(n))


def delay_ms(delaytime):
    time.sleep(delaytime / 1000.0)


_initialized = False


def module_init():
    # Initialise the library once. The driver calls init() before every
    # refresh, and re-running DEV_ModuleInit each time would keep re-mapping
    # the GPIO/SPI registers.
    global _initialized
    if not _initialized:
        _lib.DEV_ModuleInit()
        _initialized = True
    return 0


def module_exit():
    global _initialized
    if _initialized:
        _lib.DEV_ModuleExit()
        _initialized = False
