# *****************************************************************************
# * | File        :   epd10in85g.py
# * | Function    :   Driver for the Waveshare 10.85inch e-Paper (G)
# * |                 1360x480, 4-color (black / white / yellow / red),
# * |                 dual controller (master = left 680 px, slave = right 680 px)
# * | Info        :   Register sequence and bus handling follow Waveshare's
# * |                 E-paper_Separate_Program/10.85inch_e-Paper_G demo. Uses
# * |                 epdconfig_g (Waveshare's DEV_Config library): the panel
# * |                 needs chip select held low across a whole command
# * |                 sequence, which the kernel spidev driver cannot do.
# *----------------
# * | Notes       :
# * |  - BUSY is LOW while the controller is busy, HIGH when idle.
# * |  - The (G) panel has no partial refresh. Every update is a full refresh
# * |    of roughly 20 s, so callers should refresh no faster than every few
# * |    minutes and put the panel to sleep in between.
# ******************************************************************************/
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.

import logging
import time
from PIL import Image
from . import epdconfig_g as epdconfig

EPD_WIDTH  = 1360          # full panel width (two 680 px controllers side by side)
EPD_HEIGHT = 480

HALF_WIDTH     = EPD_WIDTH // 2          # pixels per controller
ROW_BYTES      = EPD_WIDTH // 4          # 2 bits per pixel -> 340 bytes per full row
HALF_ROW_BYTES = HALF_WIDTH // 4         # 170 bytes per controller row

# Palette index -> 2-bit panel code
#   0 = black, 1 = white, 2 = yellow, 3 = red
PALETTE_RGB = (0, 0, 0,  255, 255, 255,  255, 255, 0,  255, 0, 0)

logger = logging.getLogger(__name__)

# Shift tables for packing four 2-bit indices into one byte at C speed
# (bytes.translate) instead of a 160k-iteration Python loop.
_SHL6 = bytes(((i & 3) << 6) for i in range(256))
_SHL4 = bytes(((i & 3) << 4) for i in range(256))
_SHL2 = bytes(((i & 3) << 2) for i in range(256))
_SHL0 = bytes((i & 3) for i in range(256))

try:
    _DITHER_NONE = Image.Dither.NONE
except AttributeError:          # Pillow < 9.1
    _DITHER_NONE = Image.NONE


class EPD:
    def __init__(self):
        self.cs_m_pin = epdconfig.EPD_CS_M_PIN
        self.cs_s_pin = epdconfig.EPD_CS_S_PIN
        self.reset_pin = epdconfig.EPD_RST_PIN
        self.dc_pin = epdconfig.EPD_DC_PIN
        self.busy_pin = epdconfig.EPD_BUSY_PIN
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT

        # Colors for drawing on an RGB image
        self.BLACK = (0, 0, 0)
        self.WHITE = (255, 255, 255)
        self.YELLOW = (255, 255, 0)
        self.RED = (255, 0, 0)

        self._pal_image = Image.new("P", (1, 1))
        self._pal_image.putpalette(PALETTE_RGB + (0, 0, 0) * 252)

    # ------------------------------------------------------------------ low level
    def reset(self):
        epdconfig.digital_write(self.reset_pin, 1)
        epdconfig.delay_ms(200)
        epdconfig.digital_write(self.reset_pin, 0)
        epdconfig.delay_ms(2)
        epdconfig.digital_write(self.reset_pin, 1)
        epdconfig.delay_ms(200)

    def cs_all(self, value):
        epdconfig.digital_write(self.cs_m_pin, value)
        epdconfig.digital_write(self.cs_s_pin, value)

    def send_command(self, command):
        epdconfig.digital_write(self.dc_pin, 0)
        epdconfig.spi_writebyte(command)

    def send_data(self, data):
        epdconfig.digital_write(self.dc_pin, 1)
        epdconfig.spi_writebyte(data)

    def cmd(self, command, *data):
        """Send a command and its parameters to whichever controllers are selected."""
        self.send_command(command)
        for d in data:
            self.send_data(d)

    def _load(self, cs_pin, payload):
        """Load one controller's half-frame into its image RAM (command 0x10)."""
        epdconfig.digital_write(cs_pin, 0)
        self.send_command(0x10)
        epdconfig.digital_write(self.dc_pin, 1)
        for r in range(EPD_HEIGHT):
            epdconfig.spi_writebytes(payload[r * HALF_ROW_BYTES:(r + 1) * HALF_ROW_BYTES])
        self.cs_all(1)

    def ReadBusy(self, timeout_s=60):
        """Wait for BUSY to go HIGH (idle). Returns False on timeout."""
        epdconfig.delay_ms(100)
        start = time.time()
        deadline = start + timeout_s
        while epdconfig.digital_read(self.busy_pin) == 0:      # 0: busy, 1: idle
            epdconfig.delay_ms(20)
            if time.time() > deadline:
                logger.warning("ReadBusy: BUSY still LOW after %ss -> TIMEOUT", timeout_s)
                return False
        logger.debug("ReadBusy: released after %.2fs", time.time() - start)
        return True

    # ------------------------------------------------------------------ panel ops
    def init(self, fast=False):
        if epdconfig.module_init() != 0:
            return -1

        self.reset()
        self.ReadBusy()

        self.cs_all(0)               # both controllers receive the setup sequence
        self.cmd(0x4D, 0x78)
        self.cmd(0xE0, 0x01)
        self.cmd(0xE5, 0x08)
        self.cmd(0xA2, 0x01)
        self.cmd(0x00, 0x2F, 0x21)
        self.cmd(0xA2, 0x02)
        self.cmd(0x00, 0x2F, 0x21)
        self.cmd(0xA2, 0x00)
        self.cmd(0x01, 0x07, 0x00)
        self.cmd(0x06, 0x0D, 0x12, 0x30, 0x20, 0x19, 0x3D, 0x0C)
        self.cmd(0x30, 0x08)
        self.cmd(0x50, 0x37)
        # Resolution per controller: 680 x 480
        self.cmd(0x61, HALF_WIDTH >> 8, HALF_WIDTH & 0xFF,
                     EPD_HEIGHT >> 8, EPD_HEIGHT & 0xFF)
        self.cmd(0x65, 0x00, 0x00, 0x00, 0x00)
        self.cmd(0xE3, 0x88)
        self.cmd(0xE9, 0x01)
        self.cmd(0xB8, 0xB5)
        epdconfig.delay_ms(200)

        self.send_command(0x04)          # power on
        epdconfig.delay_ms(500)
        ok = self.ReadBusy()

        if ok and fast:
            self.cmd(0xE0, 0x03)
            self.cmd(0xE6, 92)
            self.cmd(0xA5, 0x00)
            ok = self.ReadBusy()
        self.cs_all(1)
        return 0 if ok else -1

    def TurnOnDisplay(self, timeout_s=60):
        self.cs_all(0)
        self.cmd(0x12, 0x00)
        self.cs_all(1)
        return self.ReadBusy(timeout_s)

    def getbuffer(self, image):
        """Convert a PIL image (any mode) to the packed 2bpp panel buffer.

        Colors are mapped to the nearest of black/white/yellow/red without
        dithering, so text and line art stay crisp."""
        w, h = image.size
        if (w, h) == (self.height, self.width):
            image = image.rotate(90, expand=True)
        elif (w, h) != (self.width, self.height):
            frame = Image.new("RGB", (self.width, self.height), self.WHITE)
            frame.paste(image, (0, 0))
            image = frame

        idx = image.convert("RGB").quantize(palette=self._pal_image, dither=_DITHER_NONE).tobytes()

        a = int.from_bytes(idx[0::4].translate(_SHL6), "big")
        b = int.from_bytes(idx[1::4].translate(_SHL4), "big")
        c = int.from_bytes(idx[2::4].translate(_SHL2), "big")
        d = int.from_bytes(idx[3::4].translate(_SHL0), "big")
        return (a | b | c | d).to_bytes(len(idx) // 4, "big")

    def _split(self, buf):
        """Split a full-width buffer into master (left) and slave (right) halves."""
        m = bytearray()
        s = bytearray()
        for r in range(EPD_HEIGHT):
            base = r * ROW_BYTES
            m += buf[base:base + HALF_ROW_BYTES]
            s += buf[base + HALF_ROW_BYTES:base + ROW_BYTES]
        return m, s

    def display(self, buf):
        m, s = self._split(buf)
        self._load(self.cs_m_pin, m)
        self._load(self.cs_s_pin, s)
        return self.TurnOnDisplay()

    def Clear(self, color=0x55):
        """Fill the panel with one color. 0x55 = white (index 1 in every pixel)."""
        payload = bytes([color]) * (HALF_ROW_BYTES * EPD_HEIGHT)
        self._load(self.cs_m_pin, payload)
        self._load(self.cs_s_pin, payload)
        return self.TurnOnDisplay()

    def sleep(self, exit_module=False):
        """Power the panel off and put both controllers in deep sleep.

        The next init() resets the controllers out of deep sleep. Pass
        exit_module=True only on shutdown, to release SPI and drop PWR."""
        self.cs_all(0)
        self.cmd(0x02, 0x00)             # power off
        epdconfig.delay_ms(100)
        self.cmd(0x07, 0xA5)             # deep sleep
        self.cs_all(1)
        epdconfig.delay_ms(100)
        if exit_module:
            epdconfig.module_exit()

### END OF FILE ###
