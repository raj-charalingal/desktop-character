# Modi Desktop Character — modi-hai-to-mumkin-hai

Always-on-top transparent overlay desktop pet written in Python.
The character walks, idles, waves, and reacts to user input while sitting on top of all other windows.

## Project Structure

```
modi-hai-to-mumkin-hai/
├── main.py          — entire application (window, sprite, AI, tray)
├── requirements.txt — optional dependencies (pillow, pystray)
├── assets/          — drop real PNG sprites here (see Sprite section below)
├── CLAUDE.md
└── .gitignore
```

## Running

```bash
python main.py
```

Requires Python 3.10+ (uses `list[int]` type hint syntax).
`tkinter` ships with Python on Windows — no install needed.

For the system tray icon:
```bash
pip install pillow pystray
```

## Key Architecture (main.py)

### Constants (top of file)
| Name | Purpose |
|------|---------|
| `WIN_W`, `WIN_H` | Overlay window size in pixels |
| `CX`, `CY` | Character anchor — feet at `(CX, CY)` on the canvas |
| `CHROMA` | `#00FF00` — pixels of this color become transparent on Windows |
| `FPS`, `ANIM_MS` | Animation rate |
| `WALK_SPEED` | Pixels per frame during AI walk |

### `State` (Enum)
Animation states: `IDLE`, `WALKL`, `WALKR`, `RUNL`, `RUNR`, `WAVE`.

### `Sprite`
Draws the character onto a `tk.Canvas` using geometric shapes (ovals, polygons, lines).
- `advance()` — increments frame counter and calls `_render()`
- `set_state(State)` — switches animation mode
- `_render()` — clears canvas items and redraws for the current frame/state

**To replace drawn shapes with real PNG sprites:**
1. Put frame PNGs in `assets/` (e.g. `walk_l_0.png` … `walk_l_7.png`)
2. In `Sprite.__init__`, load them with `ImageTk.PhotoImage`
3. In `_render()`, call `canvas.create_image(CX, CY, image=frame_img, anchor='s')`
   instead of the polygon/line drawing code

### `ModiApp`
Owns the `tk.Tk` root window and the `Sprite`.

**Transparent overlay setup** (Windows-specific):
```python
root.overrideredirect(True)            # remove title bar / borders
root.attributes('-topmost', True)      # float above all other windows
root.attributes('-transparentcolor', CHROMA)   # make CHROMA pixels see-through
root.config(bg=CHROMA)
```

**AI movement** (`_ai_step`):
- Moves `WALK_SPEED` px per frame in `_ai_dir` direction
- Bounces off screen edges (left/right margin = 30 px)
- At random waypoints: pause, wave, or turn around
- Paused automatically during drag, keyboard move, and wave

**Controls:**
| Input | Action |
|-------|--------|
| Arrow keys | Manual nudge (25 px) |
| Space / Double-click | Wave animation |
| Right-click | Context menu (Wave / Quit) |
| Click + drag | Reposition window |
| Escape / Q | Quit |

**System tray** (requires `pillow` + `pystray`):
- Show / Hide toggle
- Quit

## Roadmap / Next Steps

- [ ] Add real Modi PNG sprites (idle, walk L/R, wave, run)
- [ ] Speech bubbles with Modi quotes (triggered randomly or on click)
- [ ] More animations: namaste, run, jump
- [ ] Sound effects (optional, mutable)
- [ ] Config file for speed, screen region, quote list
- [ ] Installer / .exe via PyInstaller
