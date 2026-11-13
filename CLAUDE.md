# CLAUDE.md: working notes for this repo

Fork: `n5ac/Waveshare-ePaper-10.85-dashboard` (upstream author: Mike).
Owner: Steve Hicks, N5AC. Mac copy: `~/Waveshare-ePaper-10.85-dashboard`.
Runs on: Raspberry Pi Zero 2 W, hostname `N5AC-MON`, at `~/Waveshare-ePaper-10.85-dashboard`.

## Hardware (as actually installed)

- **Panel: Waveshare 10.85" e-Paper (G)**, 1360x480, 4-color (black/white/yellow/red).
  It is *not* the B/W 10.85" panel the upstream code targets. Identify it by the
  round **"G" sticker** on the driver HAT.
- Driver board: 10.85" e-Paper HAT+ (G). It has only an Interface Config switch
  (set to 0 = 4-wire SPI) and no Display Config A/B switch. A passive FPC-to-FFC
  adapter board sits between the panel and the HAT.
- Two controllers: master = left 680 px (CS_M = GPIO8/CE0), slave = right 680 px
  (CS_S = GPIO7/CE1). RST 17, DC 25, BUSY 24 (LOW = busy), PWR 18.

## Current state (2026-11-13): working

The dashboard renders correctly on the (G) panel. A full refresh takes about 17-20 s,
every 300 s.

Commits made in this session (on top of upstream `ceced5e`):
1. `69c0ca5`: added the (G) driver, the `PANEL_TYPE` switch, an epdconfig
   digital_read fix, and a README section.
2. `4eb8f64`: moved the (G) driver onto Waveshare's DEV_Config library, because
   the panel ignored kernel-spidev traffic (see below).
3. This file.

## Key design decisions

- **`PANEL_TYPE` in main.py** (`'G'` or `'BW'`). Only the selected driver is
  imported. The B/W `epdconfig.py` claims GPIOs via gpiozero/lgpio *at import
  time*, which would conflict with the (G) library.
- **(G) driver = `lib/waveshare_epd/epd10in85g.py` + `epdconfig_g.py`**.
  `epdconfig_g` is a ctypes wrapper over Waveshare's `DEV_Config_{32,64}_{b,w}.so`
  (bcm2835 register access; `_w` is for the Pi 5), vendored in
  `lib/waveshare_epd/epd10in85g_lib/`. Register sequence is from Waveshare's
  `E-paper_Separate_Program/10.85inch_e-Paper_G` demo.
- **Why not spidev for (G):** with kernel spidev (hardware CE toggled per
  transfer), the (G) controllers silently ignore commands. BUSY releases
  instantly after PON and refresh, and nothing is drawn. The panel needs CS held
  low across each whole command sequence (`cs_all(0) ... cs_all(1)`), and the
  frame load is done with CS held per controller. Don't "simplify" this back to
  spidev.
- **No partial refresh on (G).** The main loop does init → display → sleep (deep
  sleep) every `REFRESH_INTERVAL_G` (300 s). Startup does init+sleep only (no
  Clear) and waits 20 s before the first frame so the data thread can fill in.
  The B/W path (partial refresh every 60 s) is unchanged.
- `epd10in85g.getbuffer()` quantizes any PIL image to the 4-color palette
  **without dithering** and packs 2bpp with `bytes.translate` plus big-int OR
  (byte-identical to Waveshare's loop, about 10 ms on the Zero 2 W). Rendering
  is still 1-bit (`render_screen` makes a mode '1' image); red/yellow are
  available as `epd.RED` / `epd.YELLOW` if the renderer moves to RGB.
- `ReadBusy()` in the (G) driver has a 60 s timeout and returns False. main.py
  turns that into `HardwareTimeoutError`, and the existing handler re-execs the
  process. A SIGALRM watchdog (150 s) also guards each (G) frame.
- `epdconfig.py` fix: `digital_read()` for RST/DC/PWR read `.value` on the int
  pin number. It now reads the gpiozero device.

## Debug history (in case it recurs)

1. Symptom: `ReadBusy: BUSY still LOW ... TIMEOUT`, blank panel.
2. Ruled out: platform detection (the RaspberryPi class loads), PWR pin
   (GPIO18 driven high), BUSY wiring (pull-up and pull-down tests showed the
   controller actively drives it), SPI (the controller reacted to PON).
3. Root cause 1: wrong panel. The B/W init sequence on a (G) controller makes
   the boost converter never finish after PON, so BUSY stays low. Waveshare's
   (G) demo worked.
4. Root cause 2: the first (G) port used spidev, and BUSY released in 0.00 s
   with nothing drawn. Switched to Waveshare's library, and the test pattern
   (red/yellow quadrants, black block across the seam) rendered correctly.

Bring-up test for the driver alone (run on the Pi, about 25 s):
```python
import sys; sys.path.insert(0, 'lib')
from PIL import Image, ImageDraw
from waveshare_epd import epd10in85g
e = epd10in85g.EPD(); print(e.init())
im = Image.new('RGB', (1360, 480), 'white'); d = ImageDraw.Draw(im)
d.rectangle((0, 0, 679, 239), fill='red'); d.rectangle((680, 240, 1359, 479), fill='yellow')
d.rectangle((600, 200, 760, 280), fill='black')
print(e.display(e.getbuffer(im))); e.sleep()
```
A healthy run logs BUSY released after about 17-20 s on `display`.

## Workflow and gotchas

- **Line endings:** `main.py` and `lib/waveshare_epd/epdconfig.py` (and
  `epd10in85.py`) are **CRLF**. Preserve CRLF when editing, or the whole file
  shows as changed. New files are LF.
- **Pushing:** the Mac remote is SSH (`git@github.com:n5ac/...`). Push from the
  Mac. The Pi pulls over HTTPS.
- **Pi has local, uncommitted edits to `main.py`** (real config/API settings,
  possibly other tweaks). Update with `git stash && git pull && git stash pop`.
  Never commit the Pi's config. Untracked secrets on the Pi:
  `claude_creds.json`, `usage.json`, tokens, logs.
- Stop the dashboard before hardware tests: `pkill -f main.py`.
- `pinctrl get 17,18,24,25` shows the live pin state (Bookworm).

## Open items / ideas

- The clock shows the time of the last refresh (up to 5 min stale). Options:
  show "updated HH:MM" or shorten the interval (each refresh is a full ~20 s
  flash; check Waveshare's recommended minimum interval for the (G) panel first).
- Use red/yellow for alerts (high AQI, printer error, unread mail) by rendering
  in RGB.
- `PANEL_ROTATE_180` option if the enclosure mounts the panel inverted.
- Consider a systemd service instead of running in tmux.
