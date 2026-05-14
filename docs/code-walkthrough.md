# main.py — Code Walkthrough

A complete explanation of every section of `main.py`, from imports to the animation loop.

---

## Table of Contents

1. [Imports and optional dependencies](#1-imports-and-optional-dependencies)
2. [Configuration constants](#2-configuration-constants)
3. [The State enum](#3-the-state-enum)
4. [The Sprite class](#4-the-sprite-class)
   - [Image loading](#41-image-loading)
   - [Image-based rendering](#42-image-based-rendering)
   - [Drawn-character rendering](#43-drawn-character-rendering)
5. [The ModiApp class](#5-the-modiapp-class)
   - [Transparent overlay window](#51-transparent-overlay-window)
   - [Dynamic window resizing](#52-dynamic-window-resizing)
   - [Drag to reposition](#53-drag-to-reposition)
   - [Keyboard controls](#54-keyboard-controls)
   - [AI autonomous movement](#55-ai-autonomous-movement)
   - [System tray](#56-system-tray)
   - [Animation loop](#57-animation-loop)
6. [Entry point](#6-entry-point)
7. [Data flow diagram](#7-data-flow-diagram)

---

## 1. Imports and optional dependencies

```python
import os, tkinter as tk, math, random, threading
from enum import Enum

try:
    from PIL import Image, ImageDraw, ImageOps, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pystray
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False
```

**Why `try/except` for PIL and pystray?**

Both are optional. The app has two modes:

| PIL installed? | Mode |
|----------------|------|
| Yes | Loads `assets/modi.png`, displays real image |
| No | Falls back to drawing a geometric cartoon character |

`pystray` adds the system tray icon (Show/Hide/Quit). Without it, use right-click → Quit or press Escape.

The `HAS_PIL` and `HAS_PYSTRAY` booleans are checked throughout the code before calling any PIL/pystray functions.

---

## 2. Configuration constants

```python
WIN_W, WIN_H = 120, 165      # default overlay window size (px)
CHROMA       = '#00FF00'     # chroma-key colour → transparent on Windows
FPS          = 16
ANIM_MS      = 1000 // FPS   # milliseconds between animation frames (≈62ms)
WALK_SPEED   = 2             # pixels the character moves per frame

NFRAMES      = 8             # frames per animation cycle
IMG_MAX_W    = 180           # image is resized to fit within this box
IMG_MAX_H    = 260

_BASE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(_BASE, 'assets')
```

**The chroma key (`CHROMA = '#00FF00'`)**

This is the most important trick in the entire app. Windows lets you mark one exact colour in a window as "transparent" — clicks and rendering pass through it as if the window isn't there. We set the canvas background to `#00FF00` (lime green), then tell Windows:

```python
root.attributes('-transparentcolor', '#00FF00')
```

Every pixel that is exactly `#00FF00` becomes invisible. Every other pixel (the character) remains visible. The character appears to float directly on the desktop.

> **Why lime green?** It's a colour unlikely to appear in a portrait or cartoon character. Never use `#FFFFFF` (white) as chroma key — the character's kurta/clothing would disappear.

**`_MEIPASS` — PyInstaller frozen mode**

When you build a `.exe` with PyInstaller, all files are extracted to a temporary folder at runtime. `sys._MEIPASS` is the path to that folder. `getattr(sys, '_MEIPASS', fallback)` means:
- If frozen (running as `.exe`): use `sys._MEIPASS`
- If running as plain Python: use the directory of `main.py`

This makes `ASSETS_DIR` work correctly in both modes.

---

## 3. The State enum

```python
class State(Enum):
    IDLE  = 'idle'
    WALKL = 'walkl'
    WALKR = 'walkr'
    RUNL  = 'runl'
    RUNR  = 'runr'
    WAVE  = 'wave'
```

The character is always in exactly one state. The state drives two things:

1. **Which animation frames to draw** — leg/arm swing angles, bob amount
2. **Which direction to mirror the image** — `WALKL`/`RUNL` use the flipped image

State transitions happen in two places:
- **AI controller** (`_ai_step`) sets WALKL / WALKR / IDLE automatically
- **User input** (keyboard, drag, double-click) can force WALKL, WALKR, or WAVE

---

## 4. The Sprite class

```python
class Sprite:
    def __init__(self, canvas: tk.Canvas, cx: int, cy: int):
```

`cx, cy` is the anchor point — the character's **feet** are drawn at `(cx, cy)`. Everything else is calculated upward from there.

### 4.1 Image loading

```python
def _load_sprite_image(self):
    candidates = [f for f in os.listdir(ASSETS_DIR)
                  if f.lower().endswith('.png') and not f.startswith('.')]

    preferred = ['modi.png', 'character.png', 'sprite.png']
    chosen = next((f for f in preferred if f in candidates), candidates[0])

    img = Image.open(path).convert('RGBA')
    img.thumbnail((IMG_MAX_W, IMG_MAX_H), Image.LANCZOS)

    self._img_r = ImageTk.PhotoImage(img)               # right-facing
    self._img_l = ImageTk.PhotoImage(ImageOps.mirror(img))  # left-facing
```

Key points:

- **`convert('RGBA')`** — forces a 4-channel image so the transparent background is preserved. JPGs don't have an alpha channel; this step handles them safely.
- **`thumbnail()`** — resizes the image to fit within `IMG_MAX_W × IMG_MAX_H` while preserving aspect ratio. It only shrinks, never enlarges.
- **`ImageOps.mirror()`** — produces a horizontally flipped copy for left-facing walks. We store both versions upfront so there's no per-frame flipping cost.
- **PhotoImage references** — tkinter garbage-collects `PhotoImage` objects if they're not referenced. Storing them as `self._img_r` and `self._img_l` keeps them alive for the lifetime of the Sprite.

### 4.2 Image-based rendering

```python
def _render_image(self):
    phase   = (f / NFRAMES) * 2 * math.pi   # 0 → 2π over 8 frames
    bob_y   = int(abs(math.sin(phase)) * 4) if moving else 0
    img_ref = self._img_l if go_left else self._img_r

    self._put(c.create_image(x, y - bob_y, image=img_ref, anchor='s'))
```

**The bob effect**

`abs(math.sin(phase))` produces a value between 0 and 1 that peaks twice per animation cycle (once per step). Multiplying by 4 gives a 0–4 pixel vertical shift. The character appears to bounce slightly while walking, even though it's a single static image.

```
Frame:  0    1    2    3    4    5    6    7
Phase:  0   π/4  π/2  3π/4  π  5π/4 3π/2 7π/4
sin:    0   0.7   1   0.7   0  -0.7  -1  -0.7
|sin|:  0   0.7   1   0.7   0   0.7   1   0.7
bob_y:  0    3    4    3    0    3    4    3
```

**Waving overlay**

When `state == WAVE`, a saffron-coloured arc is drawn on top of the image. Its position oscillates using `sin` and `cos` to look like a waving hand:

```python
wx = x - img_w//4 + int(math.sin(phase * 2) * 12)   # side-to-side
wy = y - img_h    + int(math.cos(phase * 2) * 10)    # up-and-down
```

### 4.3 Drawn-character rendering

Used as fallback when no PNG is present. Every body part is a tkinter Canvas primitive (oval, polygon, line, arc). The draw order matters — parts drawn later appear on top:

```
1. Back leg       (behind body)
2. Kurta body     (white trapezoid polygon)
3. Front leg      (in front of body)
4. Back arm
5. Saffron scarf  (diagonal line)
6. Neck + Head    (oval)
7. Hair           (arc across top half of head)
8. Eyes + pupils
9. Mustache       (two small arcs)
10. Beard         (large lower arc)
11. Front arm     (or animated wave arm)
```

**Leg animation math**

```python
def leg_pts(hip_x: int, angle_deg: float):
    a  = math.radians(angle_deg)
    kx = hip_x + math.sin(a) * 22    # knee X (upper leg segment)
    ky = hip_y + math.cos(a) * 22    # knee Y
    a2 = math.radians(angle_deg * 0.3)
    return kx, ky, kx + math.sin(a2)*22, ky + math.cos(a2)*22  # foot
```

The upper leg swings by `angle_deg` from vertical. The lower leg swings at `angle_deg * 0.3` — only 30% of the upper swing — so the knee bends naturally rather than the whole leg rotating rigidly like a clock hand.

The swing angle itself is driven by a sine wave over the 8-frame cycle:

```python
leg_swing = math.sin(phase) * swing   # swing = 22° walk, 32° run
```

Left leg uses `+leg_swing`, right leg uses `-leg_swing` — they always swing in opposite directions.

**Back-to-front depth ordering**

When walking right, the right leg is behind the body and the left leg is in front. The code checks `going_right` and draws accordingly:

```python
if going_right:
    draw_leg(back=right_leg)   # drawn first → behind
    # ... draw body ...
    draw_leg(front=left_leg)   # drawn last → in front
```

---

## 5. The ModiApp class

Owns the window, canvas, sprite, and all user interaction.

### 5.1 Transparent overlay window

```python
def _init_window(self):
    r.overrideredirect(True)             # remove title bar and borders
    r.attributes('-topmost', True)       # float above all other windows
    r.attributes('-transparentcolor', CHROMA)   # make lime green transparent
    r.config(bg=CHROMA)
```

| Setting | Effect |
|---------|--------|
| `overrideredirect(True)` | Removes the OS window frame (title bar, resize handles, taskbar entry) |
| `attributes('-topmost', True)` | Window stays on top of everything including maximised apps |
| `attributes('-transparentcolor', CHROMA)` | **Windows only** — all pixels of exactly `#00FF00` are rendered transparent and don't receive mouse events |
| `config(bg=CHROMA)` | Sets the root window background to the chroma colour |

> **Platform note:** `-transparentcolor` is a Windows-only tkinter attribute. On macOS/Linux a different approach (shaped windows or compositing) would be needed.

### 5.2 Dynamic window resizing

The window starts at the fallback size `WIN_W × WIN_H`. After the Sprite loads the image and reports its dimensions, the window and canvas are resized to match:

```python
if self.sprite.has_image():
    iw = self.sprite.img_w
    ih = self.sprite.img_h + 12    # 12px padding under feet
    self.canvas.config(width=iw, height=ih)
    self.root.geometry(f'{iw}x{ih}')
    self.sprite.cx = iw // 2       # re-centre the anchor
    self.sprite.cy = ih - 6
```

This is done before the window is positioned on screen, so the user never sees the resize.

### 5.3 Drag to reposition

```python
def _drag_start(self, e):
    self._drag_ox = e.x_root - self._wx    # offset from window origin
    self._drag_oy = e.y_root - self._wy
    self._dragging = True
    self._ai_paused = True                 # suspend AI while dragging

def _drag_move(self, e):
    self._wx = e.x_root - self._drag_ox   # new window position
    self._wy = e.y_root - self._drag_oy
    self._clamp_pos()                      # keep within screen bounds
    self._apply_pos()                      # root.geometry('+x+y')
```

`e.x_root` and `e.y_root` are the cursor's absolute screen coordinates (not relative to the window). Subtracting the stored offset gives the new top-left corner of the window. `_clamp_pos()` prevents the window from being dragged off-screen.

### 5.4 Keyboard controls

```python
r.bind('<Left>',  lambda e: self._kbd_move(-1,  0))
r.bind('<Right>', lambda e: self._kbd_move( 1,  0))
```

```python
def _kbd_move(self, dx, dy):
    self._wx += dx * 25    # 25px per keypress
    self._wy += dy * 25
    self._clamp_pos()
    self._apply_pos()
    if dx < 0:   self.sprite.set_state(State.WALKL)
    elif dx > 0: self.sprite.set_state(State.WALKR)
    self._ai_paused = True
    self.root.after(600, lambda: setattr(self, '_ai_paused', False))
```

After a manual keypress, `_ai_paused` is set to `True` for 600ms. This prevents the AI from immediately overriding the user's input. After 600ms, `setattr(self, '_ai_paused', False)` re-enables autonomous movement.

### 5.5 AI autonomous movement

```python
def _ai_step(self):
    if self._ai_paused or not self.visible:
        return

    # Bounce off screen edges
    if self._wx <= margin:
        self._ai_dir = State.WALKR
    elif self._wx >= sw - self._win_w - margin:
        self._ai_dir = State.WALKL

    # Waypoint reached — pick a new behaviour
    self._ai_steps += 1
    if self._ai_steps >= self._ai_target:
        r = random.random()
        if   r < 0.25:  # pause and idle for 0.8–3 seconds
        elif r < 0.35:  # wave
        elif r < 0.55:  # turn around
        # else: keep going in same direction

    # Move one step
    self._wx += WALK_SPEED if self._ai_dir == State.WALKR else -WALK_SPEED
```

**How waypoints work**

`_ai_target` is a random number between 60 and 220. Every frame that the AI moves, `_ai_steps` increments. When `_ai_steps` reaches `_ai_target`, the character has reached a "waypoint" and randomly picks new behaviour. This makes movement feel organic — the character doesn't just walk in one direction forever.

**Probability table at each waypoint**

| Roll | Probability | Behaviour |
|------|-------------|-----------|
| < 0.25 | 25% | Pause (idle 0.8–3 s) |
| 0.25–0.35 | 10% | Wave for 3 seconds |
| 0.35–0.55 | 20% | Turn around |
| > 0.55 | 45% | Keep walking same direction |

### 5.6 System tray

```python
def _setup_tray(self):
    img = Image.new('RGBA', (32, 32), (0,0,0,0))   # transparent 32×32 icon
    # ... draw simple person shape with ImageDraw ...

    icon = pystray.Icon('Modi', img, 'Modi Character', menu)
    threading.Thread(target=icon.run, daemon=True).start()
```

`pystray` must run in its own thread because it has its own event loop. The thread is `daemon=True` so it automatically stops when the main program exits.

The tray callbacks use `self.root.after(0, ...)` to schedule tkinter operations on the main thread — tkinter is not thread-safe and must only be called from the thread that created it.

```python
def toggle(_icon, _item):
    self.root.after(0, self.root.withdraw)    # hide — scheduled on main thread
```

### 5.7 Animation loop

```python
def _tick(self):
    self._ai_step()       # move character one step (or skip if paused)
    self.sprite.advance() # increment frame counter and redraw
    self.root.after(ANIM_MS, self._tick)   # schedule next tick

def run(self):
    self.root.after(50, self._tick)   # first tick after 50ms startup delay
    self.root.mainloop()
```

`root.after(ms, callback)` is tkinter's non-blocking timer. It schedules `_tick` to run on the main event loop thread after `ANIM_MS` milliseconds (≈62ms at 16 FPS). This is preferable to `time.sleep` in a loop because it doesn't block the UI — tkinter can still process mouse/keyboard events between frames.

```
mainloop()
  │
  ├── after(62ms) → _tick()
  │     ├── _ai_step()        update window position
  │     ├── sprite.advance()  increment frame, redraw canvas
  │     └── after(62ms) → _tick()  schedule next frame
  │
  ├── <ButtonPress-1> → _drag_start()
  ├── <B1-Motion>     → _drag_move()
  └── <KeyPress-Left> → _kbd_move()
```

---

## 6. Entry point

```python
def main():
    # Print detected image / missing-PIL warnings
    ModiApp().run()

if __name__ == '__main__':
    main()
```

`if __name__ == '__main__'` ensures `main()` only runs when the file is executed directly, not when imported as a module (e.g. during testing).

---

## 7. Data flow diagram

```
startup
  │
  ├── ModiApp.__init__()
  │     ├── _init_window()       transparent, borderless, topmost
  │     ├── Canvas(bg=CHROMA)    lime-green background = transparent
  │     ├── Sprite()
  │     │     └── _load_sprite_image()
  │     │           ├── found PNG → _img_r, _img_l (PhotoImage)
  │     │           └── no PNG   → drawn fallback
  │     ├── resize window to image size (if image loaded)
  │     ├── _bind_events()       mouse, keyboard
  │     └── _setup_tray()        pystray thread
  │
  └── run() → mainloop()
        │
        └── every 62ms: _tick()
              ├── _ai_step()
              │     ├── bounce off edges
              │     ├── waypoint logic (pause / wave / turn / continue)
              │     └── root.geometry('+x+y')   ← moves the window
              └── sprite.advance()
                    ├── frame = (frame + 1) % 8
                    └── _render()
                          ├── _render_image()   if PNG loaded
                          │     ├── create_image(bob_y offset)
                          │     └── wave arc overlay (if WAVE state)
                          └── _render_drawn()   fallback
                                └── polygons, lines, arcs per body part
```

---

## Key concepts summary

| Concept | Where | What it does |
|---------|-------|--------------|
| Chroma key | `_init_window()` | Makes `#00FF00` pixels transparent so character floats on desktop |
| PhotoImage GC | `Sprite._img_r/l` | Keeps PIL images alive so tkinter doesn't discard them |
| `sys._MEIPASS` | `ASSETS_DIR` | Makes asset paths work in both `.py` and bundled `.exe` modes |
| `after()` loop | `_tick()` | Non-blocking animation timer — keeps UI responsive between frames |
| Daemon thread | `_setup_tray()` | pystray runs its own event loop; daemon flag ensures clean exit |
| Back-to-front draw | `_render_drawn()` | Canvas items drawn later appear on top — simulates 2.5D depth |
| Waypoint AI | `_ai_step()` | Random walk distance + probabilistic behaviour change = organic feel |
