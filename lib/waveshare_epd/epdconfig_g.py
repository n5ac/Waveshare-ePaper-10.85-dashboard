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
# * |   panel requires, so the (G) driver uses it for GPIO and chip select.
# * |
# * | SPI data: Waveshare's DEV_SPI_SendData bit-bangs SCLK/MOSI with no
# * |   delays, so clock pulses are a few CPU instructions wide and uneven.
# * |   Occasionally the panel misses or double-counts one, and the rest of
# * |   that controller's frame is shifted by one bit: white (01) reads as
# * |   yellow (10). So by default the bytes go out through the SPI hardware
# * |   (/dev/spidev0.0) in SPI_NO_CS mode: an even clock, while the kernel
# * |   never touches CE0/CE1 and the driver keeps holding chip select itself.
# * |   EPD_G_SPI=soft (environment) forces the old bit-banging; it is also
# * |   the automatic fallback if spidev is unavailable.
# ******************************************************************************/
import ctypes
import logging
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


SPI_SPEED_HZ = 2_000_000          # hardware SPI clock; a frame (163 KB) takes ~0.7 s
_BCM2835_GPIO_FSEL_ALT0 = 4       # GPIO 10/11 function = SPI0 MOSI/SCLK
_spi = None                       # spidev.SpiDev when using hardware SPI


def _open_hw_spi():
    """Open /dev/spidev0.0 for SPI_NO_CS mode-0 writes, or return None."""
    if os.environ.get('EPD_G_SPI', 'hw').lower() == 'soft':
        return None
    spi = None
    try:
        import spidev
        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.mode = 0
        spi.no_cs = True
        spi.max_speed_hz = SPI_SPEED_HZ
        return spi
    except Exception as e:
        try:
            if spi: spi.close()
        except Exception:
            pass
        logging.warning(f"(G) panel: hardware SPI unavailable ({e}); using bit-banged SPI")
        return None


def spi_writebyte(value):
    if _spi:
        _spi.writebytes([value & 0xFF])
    else:
        _lib.DEV_SPI_SendData(value)


def spi_writebytes(buf):
    if _spi:
        _spi.writebytes2(bytes(buf))
        return
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
    global _initialized, _spi
    if not _initialized:
        _lib.DEV_ModuleInit()          # GPIOs, incl. CS 8/7 as plain outputs
        if _spi is None:
            _spi = _open_hw_spi()
            if _spi:
                logging.info(f"(G) panel: hardware SPI at {SPI_SPEED_HZ / 1e6:g} MHz")
        if _spi:
            # DEV_ModuleInit made SCLK/MOSI plain GPIO outputs for bit-banging;
            # hand them back to the SPI block. CS pins stay GPIO outputs.
            for pin in (EPD_SCK_PIN, EPD_MOSI_PIN):
                _lib.bcm2835_gpio_fsel(pin, _BCM2835_GPIO_FSEL_ALT0)
        _initialized = True
    return 0


def module_exit():
    global _initialized, _spi
    if _initialized:
        _lib.DEV_ModuleExit()
        _initialized = False
    if _spi:
        _spi.close()
        _spi = None
