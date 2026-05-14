# Modi Desktop Character — Hai to Mumkin Hai! 🇮🇳

An always-on-top transparent desktop companion built in Python. Modi walks, idles, and waves on top of all your other windows while you work.

---

## Preview

```
┌──────────────────────────────────────────────┐
│  Your browser / editor / anything            │
│                                              │
│         🧍 (Modi walks across here)          │
│                                              │
└──────────────────────────────────────────────┘
```

The character floats over every window with a fully transparent background — only the character is visible.

---

## Features

- Transparent, borderless, always-on-top overlay window
- Autonomous AI movement — walks, pauses, waves, and turns on its own
- Uses your own PNG image (AI-generated, photo, illustration — anything works)
- Falls back to a drawn geometric character if no image is provided
- Drag to reposition anywhere on screen
- System tray icon (Show/Hide/Quit)
- Packaged as a standalone `.exe` — no Python installation needed to run

---

## Project Structure

```
modi-hai-to-mumkin-hai/
├── main.py              — entire application source
├── requirements.txt     — Python dependencies
├── assets/
│   ├── modi.png         — character sprite (PNG with transparent background)
│   └── modi.ico         — app icon (auto-generated from modi.png)
├── dist/
│   └── ModiCharacter/   — built .exe and all dependencies (run this)
│       ├── ModiCharacter.exe
│       └── _internal/
├── docs/
│   └── code-walkthrough.md   — detailed explanation of main.py
├── CLAUDE.md            — project notes for Claude Code
└── README.md
```

---

## Quick Start

### Option A — Run from source (requires Python)

```bash
# 1. Install dependencies
pip install pillow pystray

# 2. Add your character image
#    Drop a PNG with transparent background into assets/modi.png
#    Character should face RIGHT in the image

# 3. Run
python main.py
```

### Option B — Run the built .exe (no Python needed)

```
dist\ModiCharacter\ModiCharacter.exe
```

Double-click to launch. To make it start with Windows, drop a shortcut into:
```
Win+R  →  shell:startup  →  paste shortcut here
```

---

## Adding Your Own Character Image

1. Generate or find a PNG of any character (AI tools like Midjourney, DALL-E, Adobe Firefly work great)
2. Remove the background — use [remove.bg](https://www.remove.bg) or any image editor
3. Save as `assets/modi.png` — character should **face right** in the image (left-facing is auto-mirrored)
4. Restart the app

The window automatically resizes to fit your image (max 180×260 px).

---

## Controls

| Input | Action |
|-------|--------|
| Arrow keys | Move character manually (25 px per press) |
| Space | Trigger wave animation |
| Double-click | Trigger wave animation |
| Right-click | Context menu (Wave / Quit) |
| Click + drag | Reposition anywhere on screen |
| Escape or Q | Quit |
| System tray | Show / Hide / Quit |

---

## Building the .exe yourself

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --onedir --name "ModiCharacter" \
            --icon "assets\modi.ico" --add-data "assets;assets" main.py
```

Output: `dist\ModiCharacter\ModiCharacter.exe`

---

## Dependencies

| Package | Purpose | Required? |
|---------|---------|-----------|
| `tkinter` | Window, canvas, animations | Yes (ships with Python) |
| `pillow` | Load PNG sprites, create tray icon | Optional (enables image mode) |
| `pystray` | System tray icon | Optional |
| `pyinstaller` | Build standalone .exe | Build-time only |

---

## Roadmap

- [ ] Speech bubbles with quotes
- [ ] More animations: run, namaste, jump
- [ ] Multiple character support
- [ ] Sound effects (toggleable)
- [ ] Config file (speed, quotes, startup behavior)

---

## License

MIT
