# Waveshare-ePaper-10.85 Dashboard

A fully functional E-ink dashboard running on a Raspberry Pi Zero 1W or 2W. Designed for large Waveshare e-Paper displays (e.g., 10.85"), this project aggregates essential daily information and smart home status into a clean, minimalist interface.

## Key Features
* **(NEW!) Now supporting both Raspberry Pi Zero 1 & 2!**
* **(NEW!) Codex usage data:** Displays usage data for Codex, showing the limit, and limit reset time.
* **Antigravity usage data:** Displays usage data for Antigravity, showing the limit, and limit reset time.
* **Claude Code usage data:** Displays usage data for Claude Code, showing the daily limit, weekly limit, and limit reset time.
* **Weather & Air Quality:** Real-time temperature, humidity, wind direction/speed, UV index, 4-hour forecast, and AQI (with visual inversion for high pollution levels) using the Open-Meteo API.
* **Strava Integration:** Displays total and yearly activity statistics (distance and ride counts), including specific breakdowns for biking and hiking.
* **Bambu Lab 3D Printer:** Live monitoring of print status, completion percentage, remaining time, and current layer progress.
* **Roborock Vacuum:** Live battery level, current status, and tracking for cleaned area during active cleaning.
* **Spotify:** Displays the currently playing track and artist.
* **Gmail:** Tracks the number of unread emails in your primary inbox.
* **System Fallbacks:** Automatically switches to displaying System Load (CPU/RAM usage) or Cryptocurrency prices (BTC/ETH) if certain hardware integrations are disabled or offline for demonstration of dashboard capabilities. The fallback wedgets are not required tokens and ready to go.
* **Optimized Rendering:** Uses partial screen refreshes to prevent flickering, with scheduled full refreshes to clear e-ink ghosting.

<img width="2400" height="1792" alt="dashboard_primary" src="https://github.com/user-attachments/assets/20be2eae-4a06-48e2-9ad4-efcba00dcb7f" />
<img width="2400" height="1792" alt="dashboard_fallback" src="https://github.com/user-attachments/assets/158d65ee-9a12-4f09-a9d3-ea66ca3055bc" />

---

## Prerequisites & Installation

### Hardware
* [Raspberry Pi Zero 1W](https://www.raspberrypi.com/products/raspberry-pi-zero-w/) OR [Raspberry Pi Zero 2W](https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/) OR [Orange Pi Zero 2W](https://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/service-and-support/Orange-Pi-Zero-2W.html)
* [Waveshare E-Ink Display 10.85"](https://www.waveshare.com/10.85inch-e-paper-hat-plus.htm?sku=29790)
  * **or** the 4-color [10.85" e-Paper HAT+ (G)](https://www.waveshare.com/10.85inch-e-paper-hat-plus-g.htm) (black/white/yellow/red). The B/W panel is often out of stock, and Waveshare recommends the (G) instead. Its driver HAT has a round **"G"** sticker. Set `PANEL_TYPE` in `main.py` to match (see below).

### 1. System Setup
Enable the SPI interface on your Raspberry Pi, which is required for communicating with the e-ink display:
```shell
sudo raspi-config
```
Go to Interfacing Options -> SPI -> Enable.

Update your system and install necessary system-level dependencies, including `tmux` for keeping the script running in the background:
```shell
sudo apt update
sudo apt install python3-pip python3-pil python3-numpy git tmux -y
```

### 2. Python Dependencies
Install the required standard Python packages:
```shell
pip3 install requests Pillow google-api-python-client google-auth-httplib2 google-auth-oauthlib aiomqtt python-roborock paho-mqtt gpiozero lgpio spidev
```

**Notes:**
The `bambulabs_api` library is already bundled in this package (in lib/), but its dependency paho-mqtt is not — it is included in the command above.
On Raspberry Pi OS (Bookworm) the GPIO/SPI packages are best installed via apt (a system-managed Python may reject pip for these). If pip3 complains about an "externally-managed-environment", install them with:
```shell
sudo apt install -y python3-gpiozero python3-lgpio python3-spidev
```

### 3. Display Library

* The **patched** version of the epd10in85 library with fixed partial refresh issue already included in this package.

* **(New)** Included support of Raspberry PI Zero 1.

* **(New)** Support for the 4-color **10.85" e-Paper (G)** panel (`lib/waveshare_epd/epd10in85g.py`). The (G) driver talks to the panel through Waveshare's own `DEV_Config` library (`lib/waveshare_epd/epd10in85g_lib/`). The panel ignores commands sent through the kernel SPI driver, because it needs chip select held low across a whole command sequence. Choose the panel in `main.py`:
  ```python
  PANEL_TYPE = 'G'          # 'BW' for the black/white panel, 'G' for the 4-color (G) panel
  REFRESH_INTERVAL_G = 300  # seconds between (G) refreshes
  ```
  The two panels use different controllers and are **not** interchangeable. Running the B/W driver on a (G) panel leaves the screen blank and logs `ReadBusy: BUSY still LOW ... TIMEOUT`.
  The (G) panel has **no partial refresh**: each update is a full refresh of about 20 s with a visible flash. The dashboard therefore redraws every `REFRESH_INTERVAL_G` seconds (default 5 minutes) and keeps the panel in deep sleep between updates. The clock shows the time of the last refresh. Colors in the rendered image are mapped to black/white/yellow/red without dithering.

---

## Configuration & Widget Setup

All widget toggles and API configurations are located at the top of the `main.py` script. You can enable or disable specific widgets using the `ENABLE_*` boolean variables.

### Codex (ChatGPT)
1. Codex limits are read from the official OpenAI Codex CLI tokens — unlike Claude, the dashboard does not run its own browser login flow.
2. Install the Codex CLI (for example `npm install -g @openai/codex`) and run codex login in the terminal.
3. A browser window opens — sign in with your ChatGPT account and click "Authorize". (Codex usage limits require a paid ChatGPT plan that includes Codex.)
4. After a successful login the CLI writes your tokens to `~/.codex/auth.json` (on Windows: `%USERPROFILE%\.codex\auth.json`).
5. Copy that file into the project root, next to `codex.py`, keeping the exact name `auth.json`.
6. Set `ENABLE_CODEX = True` in `main.py` and run the script. The dashboard reads `auth.json`, fetches your usage, and from then on refreshes and rotates the tokens automatically, updating auth.json in place.

### Claude Code
1. Run the `main.py` script from the terminal for the first time.
2. The script will pause, ask for your to copy the authorization URL and paste it on real browser.
3. Open that URL in your browser, click "Authorize", and you will be redirected to a dead `localhost` page.
7. Copy the whole URL containing `code=...` portion from your browser's address bar and paste it back into the terminal. The script will automatically fetch and save the required tokens to `claude_creds.json`.

### Strava
1. Go to your Strava API Settings and create an API Application. **Now only payed accounts supported**
2. Note down your **Client ID** and **Client Secret**.
3. Run the `main.py` script from the terminal for the first time.
4. The script will pause, ask for your ID/Secret, and print an authorization URL in the console. 
5. Open that URL in your browser, click "Authorize", and you will be redirected to a dead `localhost` page.
6. Copy the `code=...` portion from your browser's address bar and paste it back into the terminal. The script will automatically fetch and save the required `activity:read_all` tokens to `strava_token.json`.

### Roborock
1. Open `main.py` and input your Roborock account email address in the `ROBOROCK_CONF` dictionary.
2. Run the script from the terminal.
3. The script will request an OTP (One-Time Password) which will be sent to your email.
4. Enter the 6-digit code in the terminal. The script will securely save your session data locally.

### Bambu Lab 3D Printer
**You DON'T need to enable "LAN Mode" on your Bambu Lab printer to access local data.**
1. On your printer's screen, go to **Settings -> Network**.
2. Note your printer's **IP Address**, **Serial Number**, and **Access Code**. (Force on your router to map exact IP address)
3. Update the `PRINTER_CONF` dictionary in the script with these local credentials.

### Spotify (via Last.fm)
Since the official Spotify API requires running a local web server for complex token renewals, this dashboard uses Last.fm to fetch the current playing track reliably form Spotify. It's is transparent and working method.
1. Connect your Spotify account to Last.fm.
2. Create a Last.fm API account to generate an **API Key**.
3. Update `LASTFM_CONF` in the script with your API Key and Last.fm Username.
   
**After configuration, you no longer need to use the Last.fm service, and a paid Last.fm account is not required. You can continue to use only the Spotify service.**

### Tempest Weather Station
Set `ENABLE_TEMPEST = True` in `main.py`. Nothing else is needed: the dashboard listens for the Tempest hub's local UDP broadcasts (port 50222), so no API token or internet connection is used. The hub and the Pi must be on the same network (broadcasts don't cross VLANs or subnets).

While Tempest data is fresh (`TEMPEST_STALE_S`, default 5 min), wind, humidity and UV come from the Tempest, and the AQI area also shows rain in the last hour, whether it is raining now, lightning strikes in the last hour and the distance and time of the last strike (within 3 h). Otherwise the widget falls back to Open-Meteo. Rain and strike totals are summed by the dashboard, so they restart when it restarts. `RAIN_UNIT` (`'in'` or `'mm'`) also picks miles or km for the strike distance.

### Gmail
The dashboard only *reads* `token.json`; it never starts a sign-in itself. If the file is missing or invalid, the widget shows 0 unread. Create the token once on a computer with a web browser, then copy it to the Pi.

1. In the [Google Cloud Console](https://console.cloud.google.com/), create a project and enable the **Gmail API** (APIs & Services → Library).
2. Configure the consent screen (Google Auth Platform / OAuth consent screen):
   * **Internal** audience (Google Workspace accounts only): nothing else to do.
   * **External** audience (e.g. a @gmail.com account): under **Audience**, click **Publish app** so it is *In production*. In *Testing* status the token expires after 7 days and the count silently drops to 0. At sign-in you will see "Google hasn't verified this app"; choose **Advanced → Go to … (unsafe)**.
3. Under **Clients**, create a client of type **Desktop app** and download its JSON. Save it in this directory as `credentials.json`.
4. Run the helper (needs `pip install google-auth-oauthlib`):
   ```shell
   python3 gmail_auth.py
   ```
   Approve read-only access in the browser. It writes `token.json` and should report `refresh token: yes`.
5. Copy `token.json` to the dashboard directory on the Pi and restrict it:
   ```shell
   scp token.json pi@<pi-host>:~/Waveshare-ePaper-10.85-dashboard/
   ssh pi@<pi-host> chmod 600 ~/Waveshare-ePaper-10.85-dashboard/token.json
   ```
   The Pi refreshes the token on its own from then on. `credentials.json` is not needed on the Pi.

The count is unread messages in the whole Inbox (all tabs, not just Primary). `credentials.json` and `token.json` are listed in `.gitignore`; never commit them.

---

## Running the Dashboard

To ensure the dashboard continues running even after you close your SSH connection, use `tmux`.

1. Start a new tmux session:
```shell
tmux new -s dashboard
```

2. Run the script inside the tmux session:
```shell
python3 main.py
```

3. Detach from the session (leave it running in the background) by pressing:
`Ctrl+B`, then release and press `D`.

To reattach to the session later and view the logs or stop the script:
```shell
tmux attach -t dashboard
```

### Start at boot (systemd)

`epaper-dashboard.service` runs the dashboard at boot and restarts it if it exits. It assumes user `n5ac` and `/home/n5ac/Waveshare-ePaper-10.85-dashboard`; edit `User=`, `WorkingDirectory=` and `ExecStart=` if yours differ.

Do any first-time interactive sign-ins (Claude, Strava, Roborock) by running `python3 main.py` by hand first; a service has no keyboard. Stop any copy running in tmux (`pkill -f main.py`) so two instances don't drive the panel. Then:
```shell
sudo cp epaper-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now epaper-dashboard
```

| Task | Command |
|---|---|
| Status | `systemctl status epaper-dashboard` |
| Live output | `journalctl -u epaper-dashboard -f` |
| Restart (e.g. after `git pull`) | `sudo systemctl restart epaper-dashboard` |
| Stop / start | `sudo systemctl stop epaper-dashboard` / `start` |
| Don't start at boot | `sudo systemctl disable epaper-dashboard` |

Stopping sends SIGINT, so the panel is put into deep sleep cleanly.

## How It Works

The dashboard is built on a robust, multi-threaded architecture designed to keep the UI responsive and prevent hardware lockups.

* **Asynchronous Data Fetching:** Instead of fetching all data sequentially, the script spawns dedicated background threads. Each service (Weather, Strava, Roborock, Bambu Lab, etc.) pulls data asynchronously at its own specific interval. This ensures that a slow API response or a temporary network drop from one service will never block the others or freeze the system.
* **Scheduled Rendering:** The main application loop acts purely as a renderer. It collects the latest available information from a thread-safe global data store and pushes a new frame to the e-ink display exactly once per minute using a partial screen refresh. 

**Important Notes:**

* **Initial Data Population Delay:** When you first launch the script, you will notice that the widgets may show placeholders or zeros, and the full array of data takes a few minutes to completely appear on the screen. This is an intentional design choice to stagger initial network requests. It prevents sudden spikes in CPU usage, avoids overwhelming the Raspberry Pi's network stack, and respects the rate limits of the external APIs.
* **Hardware Refresh Limits:** The 60-second rendering interval is strictly enforced. Refreshing the screen more frequently than once a minute is strongly discouraged by the display manufacturer (Waveshare). Aggressive refresh rates on large e-paper panels can lead to severe ghosting and may cause permanent hardware damage to the display.

## The 3d printed case

You can download the case stl files [here](https://makerworld.com/en/models/2322517-epaper-dashboard-waveshare-10-85).

## Video assembly guide

**(Youtube clickable)**

[![Video Title](https://img.youtube.com/vi/H964RpaJvu0/0.jpg)](https://youtu.be/H964RpaJvu0)
