# AIXAI-zoom-breakout-helper

[繁體中文](README.md) | **English**

A small Windows tool that **creates Zoom breakout rooms and renames them from a list** — in one click.

> **Unofficial.** This is a third-party personal tool. It is not affiliated with, endorsed by, or sponsored by Zoom Communications, Inc. "Zoom" is a trademark of its owner.

## Why
For ad-hoc meetings (for example a fixed Personal Meeting ID), splitting people into groups means: create N rooms, then click "Rename" on each room and paste the name from a notepad. Zoom's REST API cannot manage breakout rooms **inside a meeting that is already running**, so this tool **simulates mouse and keyboard input** to do that repetitive work for you.

## Features
- Multiple saved room-name lists; the number of rooms follows the number of lines in the list
- Build mode (dropdown): create + rename / rename only / create only
- Assignment mode: automatic / manual / let participants choose
- One-time guided calibration (record positions with F8; on laptops press Fn + F8)
- Detects changes in Zoom version or screen settings and reminds you to recalibrate (a reminder only, never forced)
- Checks whether the screen looks abnormal after renaming
- Minimal borderless dark window (gold and blue theme), resizable from all four edges
- "Check for updates": connects only when you click it, compares with the latest GitHub release, never downloads or replaces anything by itself
- "Report a problem": write a description, choose whether to attach diagnostics, **review the full content before it is sent and press Send yourself**; if sending fails the content is copied to your clipboard so you can use GitHub Issues instead. See [PRIVACY.md](PRIVACY.md) (Traditional Chinese)

## Requirements
- Windows 10 / 11
- Zoom desktop client (tested with the Traditional Chinese UI; because the tool works by screen coordinates, other languages should work as long as the layout is the same)
- Python 3.10+ only if you run from source (not needed for the exe)

## Download (no Python needed)
1. Download `AIXAI-zoom-breakout-helper.exe` (a single file) from [Releases](../../releases).
2. Put it anywhere and double-click it.
3. Nothing is created next to the exe. Your lists, calibration and logs are stored in `%APPDATA%\AIXAI-zoom-breakout-helper\` (open it from the **View** menu).
4. To **carry your data with you** (USB drive, a borrowed PC), put an empty file named `portable.txt` next to the exe; the data is then stored in a single folder `AIXAI-zoom-breakout-helper-data\` beside it.

Notes:
- A single-file exe unpacks itself to a temporary folder every time, so it **takes about 2–3 seconds to start**. This is normal.
- This kind of program simulates mouse and keyboard input and is not code-signed, so Windows SmartScreen or antivirus software may warn about it or flag it by mistake. The full source code is public; you can inspect it or run from source instead. Each release lists a SHA256 hash so you can verify the file.
- If the program is force-killed (for example from Task Manager), a folder starting with `_MEI` may be left in your temp directory. You can delete it.

## Run from source
1. Install [Python](https://www.python.org/downloads/) (tick *Add python.exe to PATH*).
2. Double-click `安裝套件.bat` (installs `pyautogui` and `pyperclip`; only once).
3. Double-click `啟動.bat`.

To build the exe yourself, run `build.bat` (needs Python); the result is in `dist\`.

## How to use
### First time: calibrate
1. Open **Breakout Rooms** in your Zoom meeting.
2. Click **☰** at the top-left of the tool window → **Calibrate** → **Full guided calibration**.
3. Follow the small calibration window: move the mouse to the position it describes and press **F8** (**Fn + F8** on many laptops). Optional steps can be skipped with **Esc**. If you only want renaming, the 4 required steps (room 1 name, Rename button, confirm "Yes" button, room 2 name) are enough.

> Calibration is tied to your **screen resolution, display scaling and Zoom version**. Recalibrate after changing computers or after a major Zoom UI change.

### Every time
1. Pick a list and edit the room names (one per line).
2. If you chose a "create" mode, open Zoom's **Create breakout rooms** window first.
3. Click **▶ Run** and take your hands off the mouse.
4. To stop: press **Esc**, or throw the mouse to the top-left corner of the screen.

## Where your data is stored
| Version | Location |
|---|---|
| exe (default) | `%APPDATA%\AIXAI-zoom-breakout-helper\` — the exe's folder stays clean |
| exe + `portable.txt` | `AIXAI-zoom-breakout-helper-data\` next to the exe (carry it with you) |
| from source | inside the project folder |

| Item | Content |
|---|---|
| `清單\*.json` (lists) | Room names + build mode + assignment mode (editable in Notepad) |
| `資料\calibration.json` | Calibration coordinates and the environment at calibration time |
| `資料\settings.json` | Wait times, last used list, always-on-top |
| `紀錄\` (logs) | Usage log and environment-change log |

These are personal data and are excluded from Git by `.gitignore`.

## Known limitations
- It works by **screen coordinates**: a Zoom UI redesign, moving the Zoom window, or changing display scaling may require recalibration.
- No auto-scroll: rooms that fall below the bottom edge of the screen are not processed (make the breakout window taller).
- Do not touch the mouse or keyboard while it is running.
- If Zoom runs as administrator, this tool must also run as administrator, otherwise Windows blocks the simulated input.
- Managed work or school computers may forbid running this kind of automation tool.

## Privacy
No telemetry and nothing is sent in the background. The program connects to the network only when you press Send in "Report a problem" or click "Check for updates". Details: [PRIVACY.md](PRIVACY.md).

## License
- Code: [MIT License](LICENSE)
- App icon (images in `assets/`): all rights reserved by AIXAI and **not** covered by the MIT license — see [assets/NOTICE.md](assets/NOTICE.md). If you fork or redistribute, please replace it with your own icon.
