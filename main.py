#!/usr/bin/env python3
"""
Modi Desktop Character
Transparent, always-on-top animated desktop companion.

To use a real image: drop any PNG with transparent background into assets/
  Preferred filename: assets/modi.png  (facing RIGHT in the image)
  The app auto-detects any .png in that folder as a fallback.

Run: python main.py
"""

import os
import sys
import tkinter as tk
import math
import random
import threading
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

# ---------------------------------------------------------------------------
# Config — drawn-fallback defaults (overridden dynamically when image loads)
# ---------------------------------------------------------------------------
WIN_W, WIN_H = 120, 165
CHROMA       = '#00FF00'   # pixels of this exact colour → transparent on Windows
FPS          = 16
ANIM_MS      = 1000 // FPS
WALK_SPEED   = 2           # px per frame

# Drawn-character palette (none may equal CHROMA)
C_SKIN  = '#F4C68F'
C_HAIR  = '#F0F0F0'
C_KURTA = '#FFFFFF'
C_PANTS = '#F0F0F8'
C_SCARF = '#FF8800'
C_SHOE  = '#1A1A1A'
C_BEARD = '#EFEFEF'
C_EYE_P = '#111111'

NFRAMES      = 8
# When frozen by PyInstaller, files live under sys._MEIPASS
_BASE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(_BASE, 'assets')
IMG_MAX_W    = 180         # max image width when resizing
IMG_MAX_H    = 260         # max image height when resizing


# ---------------------------------------------------------------------------
# Animation states
# ---------------------------------------------------------------------------
class State(Enum):
    IDLE  = 'idle'
    WALKL = 'walkl'
    WALKR = 'walkr'
    RUNL  = 'runl'
    RUNR  = 'runr'
    WAVE  = 'wave'


# ---------------------------------------------------------------------------
# Sprite
# ---------------------------------------------------------------------------
class Sprite:
    """
    Renders Modi on a tkinter Canvas.

    Image mode  — loads assets/modi.png (or first .png found), resizes it,
                  mirrors for left-facing, adds a walk-bob effect.
    Drawn mode  — fallback geometric character when no PNG is present.

    To switch to real sprites later: drop PNG(s) into assets/ and restart.
    Character should face RIGHT in the source image.
    """

    def __init__(self, canvas: tk.Canvas, cx: int, cy: int):
        self.c     = canvas
        self.cx    = cx
        self.cy    = cy
        self.state = State.IDLE
        self.frame = 0
        self._ids: list[int] = []

        # Per-state animation frames (kept alive to prevent GC)
        self._frames: dict[State, list[ImageTk.PhotoImage]] = {}
        self.img_w = 0
        self.img_h = 0

        self._load_sprite_image()

    # -- public API --

    def has_image(self) -> bool:
        return bool(self._frames)

    def advance(self):
        self.frame = (self.frame + 1) % NFRAMES
        self._render()

    def set_state(self, s: State):
        self.state = s

    # -- image loading & frame generation --

    def _load_sprite_image(self):
        if not HAS_PIL:
            return
        try:
            candidates = [f for f in os.listdir(ASSETS_DIR)
                          if f.lower().endswith('.png') and not f.startswith('.')]
        except OSError:
            return
        if not candidates:
            return

        preferred = ['modi.png', 'character.png', 'sprite.png']
        chosen = next((f for f in preferred if f in candidates), candidates[0])
        path   = os.path.join(ASSETS_DIR, chosen)

        try:
            img = Image.open(path).convert('RGBA')
            img.thumbnail((IMG_MAX_W, IMG_MAX_H), Image.LANCZOS)
            self.img_w = img.width
            self.img_h = img.height
            mir = ImageOps.mirror(img)

            print(f"Sprite loaded: {chosen}  ({img.width} × {img.height} px)")
            print("Generating animation frames…")

            self._frames = {
                State.IDLE:  self._tilt_frames(img, n=6, amp=0.8),   # gentle idle sway
                State.WALKR: self._tilt_frames(img, n=8, amp=3.5),
                State.WALKL: self._tilt_frames(mir, n=8, amp=3.5),
                State.RUNR:  self._tilt_frames(img, n=8, amp=7.0),
                State.RUNL:  self._tilt_frames(mir, n=8, amp=7.0),
                State.WAVE:  self._wave_frames(img),
            }
            print("Frames ready.")
        except Exception as exc:
            print(f"Warning — could not load sprite image: {exc}")

    def _tilt_frames(self, img: 'Image.Image', n: int, amp: float) -> list:
        """Generate n frames by rocking the image ±amp degrees (sine wave)."""
        frames = []
        for i in range(n):
            phase = i / n * 2 * math.pi
            angle = math.sin(phase) * amp
            rotated = img.rotate(angle, resample=Image.BICUBIC, expand=False)
            frames.append(ImageTk.PhotoImage(rotated))
        return frames

    def _wave_frames(self, img: 'Image.Image') -> list:
        """8 frames: rock side-to-side with increasing then decreasing amplitude."""
        frames = []
        for i in range(8):
            phase = i / 8 * 2 * math.pi
            angle = math.sin(phase) * 8          # ±8° rock for wave
            lean  = math.sin(phase * 2) * 3      # extra shimmy
            rotated = img.rotate(angle + lean, resample=Image.BICUBIC, expand=False)
            frames.append(ImageTk.PhotoImage(rotated))
        return frames

    # -- rendering --

    def _clear(self):
        for i in self._ids:
            self.c.delete(i)
        self._ids = []

    def _put(self, item_id: int):
        self._ids.append(item_id)

    def _render(self):
        self._clear()
        if self.has_image():
            self._render_image()
        else:
            self._render_drawn()

    # -- image-based render --

    def _render_image(self):
        c    = self.c
        x, y = self.cx, self.cy
        s    = self.state

        frames = self._frames.get(s, self._frames.get(State.IDLE, []))
        if not frames:
            return

        img_ref   = frames[self.frame % len(frames)]
        phase     = (self.frame / NFRAMES) * 2 * math.pi
        moving    = s in (State.WALKL, State.WALKR, State.RUNL, State.RUNR)
        running   = s in (State.RUNL,  State.RUNR)
        waving    = s == State.WAVE

        # Vertical bob: moves character up/down to simulate footsteps
        if running:
            bob = int(abs(math.sin(phase)) * 8)
        elif moving:
            bob = int(abs(math.sin(phase)) * 4)
        elif waving:
            bob = int(abs(math.sin(phase * 2)) * 3)
        else:
            bob = int(abs(math.sin(phase * 0.5)) * 1)   # barely-there idle breath

        self._put(c.create_image(x, y - bob, image=img_ref, anchor='s'))

    # -- drawn-fallback render --

    def _render_drawn(self):
        c     = self.c
        x, y  = self.cx, self.cy
        f     = self.frame
        s     = self.state

        phase    = (f / NFRAMES) * 2 * math.pi
        moving   = s in (State.WALKL, State.WALKR, State.RUNL, State.RUNR)
        running  = s in (State.RUNL, State.RUNR)
        waving   = s == State.WAVE

        swing      = 32 if running else (22 if moving else 0)
        bob_amp    =  4 if running else ( 2 if moving else 0)
        leg_swing  = math.sin(phase) * swing
        body_bob   = (abs(math.sin(phase)) * bob_amp if moving
                      else math.sin(phase * 0.5) * 1.2)

        hip_y       = y - 4
        waist_y     = y - 42
        shoulder_y  = y - 72 - int(body_bob)
        head_y      = y - 96 - int(body_bob)
        HR          = 16

        going_right = s in (State.WALKR, State.RUNR)

        def leg_pts(hip_x: int, angle_deg: float):
            a  = math.radians(angle_deg)
            kx = hip_x + math.sin(a) * 22
            ky = hip_y + math.cos(a) * 22
            a2 = math.radians(angle_deg * 0.3)
            return int(kx), int(ky), int(kx + math.sin(a2)*22), int(ky + math.cos(a2)*22)

        def arm_pts(sh_x: int, angle_deg: float):
            a  = math.radians(angle_deg)
            ex = sh_x + math.sin(a) * 16
            ey = shoulder_y + math.cos(a) * 16
            a2 = math.radians(angle_deg * 0.5)
            return int(ex), int(ey), int(ex + math.sin(a2)*14), int(ey + math.cos(a2)*14)

        lkx,lky,lfx,lfy = leg_pts(x-8,  leg_swing)
        rkx,rky,rfx,rfy = leg_pts(x+8, -leg_swing)
        arm_sw = -leg_swing * 0.65
        lex,ley,lhx,lhy = arm_pts(x-14,  arm_sw + 10)
        rex,rey,rhx,rhy = arm_pts(x+14, -arm_sw - 10)

        def draw_leg(hx, kx, ky, fx, fy):
            self._put(c.create_line(hx,hip_y,kx,ky,fx,fy,
                fill=C_PANTS,width=8,smooth=True,joinstyle=tk.ROUND,capstyle=tk.ROUND))
            self._put(c.create_oval(fx-9,fy-5,fx+9,fy+4,fill=C_SHOE,outline=''))

        def draw_arm(sh_x, ex, ey, hx, hy):
            self._put(c.create_line(sh_x,shoulder_y,ex,ey,hx,hy,
                fill=C_SKIN,width=6,smooth=True,joinstyle=tk.ROUND,capstyle=tk.ROUND))

        # Back leg
        if going_right: draw_leg(x+8,rkx,rky,rfx,rfy)
        else:           draw_leg(x-8,lkx,lky,lfx,lfy)

        # Body
        self._put(c.create_polygon(
            x-18,shoulder_y, x+18,shoulder_y,
            x+16,waist_y,    x+12,hip_y,
            x-12,hip_y,      x-16,waist_y,
            fill=C_KURTA, outline='#DDDDDD', width=1, smooth=True
        ))

        # Front leg
        if going_right: draw_leg(x-8,lkx,lky,lfx,lfy)
        else:           draw_leg(x+8,rkx,rky,rfx,rfy)

        # Back arm
        if going_right: draw_arm(x+14,rex,rey,rhx,rhy)
        else:           draw_arm(x-14,lex,ley,lhx,lhy)

        # Scarf
        self._put(c.create_line(x-14,shoulder_y+2,x+4,shoulder_y+8,x+18,shoulder_y-2,
                                fill=C_SCARF,width=4,smooth=True))

        # Neck
        self._put(c.create_rectangle(x-5,head_y+HR-2,x+5,shoulder_y+2,
                                     fill=C_SKIN,outline=''))
        # Head
        self._put(c.create_oval(x-HR,head_y-HR,x+HR,head_y+HR,
                                fill=C_SKIN,outline='#D9A870',width=1))
        # Hair
        self._put(c.create_arc(x-HR,head_y-HR,x+HR,head_y+4,
                               start=0,extent=180,fill=C_HAIR,outline='#CCCCCC',width=1))
        # Eyes
        for dx in (-6, 6):
            self._put(c.create_oval(x+dx-4,head_y-5,x+dx+4,head_y+3,
                                    fill='white',outline='#999',width=1))
            self._put(c.create_oval(x+dx-2,head_y-3,x+dx+2,head_y+1,fill=C_EYE_P))
        # Mustache
        for side in (-1, 1):
            mx = x + side*6
            self._put(c.create_arc(mx-7,head_y+3,mx+7,head_y+12,
                                   start=180,extent=180,fill=C_BEARD,outline='#BBBBBB',width=1))
        # Beard
        self._put(c.create_arc(x-13,head_y-1,x+13,head_y+HR+10,
                               start=200,extent=140,fill=C_BEARD,outline='#CCCCCC',width=1))

        # Front arm / wave
        if waving:
            wa = -55 + math.sin(phase*2)*30
            wex,wey,whx,why = arm_pts(x-14,wa)
            draw_arm(x-14,wex,wey,whx,why)
            draw_arm(x+14,rex,rey,rhx,rhy)
        elif going_right: draw_arm(x-14,lex,ley,lhx,lhy)
        else:             draw_arm(x+14,rex,rey,rhx,rhy)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------
class ModiApp:
    def __init__(self):
        self.root = tk.Tk()
        self._init_window()

        # Build canvas at drawn-character size first
        self.canvas = tk.Canvas(self.root, width=WIN_W, height=WIN_H,
                                bg=CHROMA, highlightthickness=0, bd=0)
        self.canvas.pack()

        # Create sprite — it may load an image and report its size
        self.sprite = Sprite(self.canvas, WIN_W // 2, WIN_H - 12)

        # Resize window / canvas to match loaded image (if any)
        self._win_w = WIN_W
        self._win_h = WIN_H
        if self.sprite.has_image():
            iw = self.sprite.img_w
            ih = self.sprite.img_h + 12          # 12 px padding at bottom
            self._win_w = iw
            self._win_h = ih
            self.sprite.cx = iw // 2
            self.sprite.cy = ih - 6
            self.canvas.config(width=iw, height=ih)
            self.root.geometry(f'{iw}x{ih}')

        # Screen position — bottom-right quadrant
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self._wx = sw - self._win_w - 60
        self._wy = sh - self._win_h - 80
        self._clamp_pos(sw, sh)
        self._apply_pos()

        # Drag state
        self._drag_ox = 0
        self._drag_oy = 0
        self._dragging = False

        # AI state
        self._ai_paused  = False
        self.visible     = True
        self._ai_dir     = random.choice([State.WALKL, State.WALKR])
        self._ai_steps   = 0
        self._ai_target  = random.randint(60, 200)

        self.tray = None
        self._bind_events()
        self._setup_tray()

    # -- window --

    def _init_window(self):
        r = self.root
        r.overrideredirect(True)
        r.attributes('-topmost', True)
        r.attributes('-transparentcolor', CHROMA)
        r.config(bg=CHROMA)
        r.title('Modi Character')

    def _apply_pos(self):
        self.root.geometry(f'+{self._wx}+{self._wy}')

    def _clamp_pos(self, sw=None, sh=None):
        if sw is None:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
        self._wx = max(0, min(sw - self._win_w, self._wx))
        self._wy = max(0, min(sh - self._win_h, self._wy))

    # -- event bindings --

    def _bind_events(self):
        r = self.root
        r.bind('<ButtonPress-1>',   self._drag_start)
        r.bind('<B1-Motion>',       self._drag_move)
        r.bind('<ButtonRelease-1>', self._drag_end)
        r.bind('<Double-Button-1>', lambda e: self._do_wave())
        r.bind('<Button-3>',        self._context_menu)
        r.bind('<Left>',   lambda e: self._kbd_move(-1,  0))
        r.bind('<Right>',  lambda e: self._kbd_move( 1,  0))
        r.bind('<Up>',     lambda e: self._kbd_move( 0, -1))
        r.bind('<Down>',   lambda e: self._kbd_move( 0,  1))
        r.bind('<space>',  lambda e: self._do_wave())
        r.bind('<Escape>', lambda e: self.quit())
        r.bind('<q>',      lambda e: self.quit())

    def _drag_start(self, e):
        self._drag_ox = e.x_root - self._wx
        self._drag_oy = e.y_root - self._wy
        self._dragging = True
        self._ai_paused = True
        self.sprite.set_state(State.IDLE)

    def _drag_move(self, e):
        if self._dragging:
            self._wx = e.x_root - self._drag_ox
            self._wy = e.y_root - self._drag_oy
            self._clamp_pos()
            self._apply_pos()

    def _drag_end(self, _e):
        self._dragging = False
        self.root.after(800, lambda: setattr(self, '_ai_paused', False))

    def _kbd_move(self, dx: int, dy: int):
        self._wx += dx * 25
        self._wy += dy * 25
        self._clamp_pos()
        self._apply_pos()
        if dx < 0:   self.sprite.set_state(State.WALKL)
        elif dx > 0: self.sprite.set_state(State.WALKR)
        self._ai_paused = True
        self.root.after(600, lambda: setattr(self, '_ai_paused', False))

    def _context_menu(self, e):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label='Wave',      command=self._do_wave)
        menu.add_separator()
        menu.add_command(label='Quit Modi', command=self.quit)
        try:
            menu.tk_popup(e.x_root, e.y_root)
        finally:
            menu.grab_release()

    # -- actions --

    def _do_wave(self):
        self.sprite.set_state(State.WAVE)
        self._ai_paused = True
        self.root.after(3000, self._resume_ai)

    def _resume_ai(self):
        self._ai_paused = False
        self.sprite.set_state(State.IDLE)

    # -- AI movement --

    def _ai_step(self):
        if self._ai_paused or not self.visible:
            return
        sw     = self.root.winfo_screenwidth()
        margin = 30
        if self._wx <= margin:
            self._ai_dir = State.WALKR
        elif self._wx >= sw - self._win_w - margin:
            self._ai_dir = State.WALKL

        self._ai_steps += 1
        if self._ai_steps >= self._ai_target:
            self._ai_steps  = 0
            self._ai_target = random.randint(60, 220)
            r = random.random()
            if r < 0.25:
                self.sprite.set_state(State.IDLE)
                self._ai_paused = True
                self.root.after(random.randint(800, 3000),
                                lambda: setattr(self, '_ai_paused', False))
                return
            if r < 0.35:
                self._do_wave()
                return
            if r < 0.55:
                self._ai_dir = (State.WALKL if self._ai_dir == State.WALKR
                                else State.WALKR)

        self._wx += WALK_SPEED if self._ai_dir == State.WALKR else -WALK_SPEED
        self._clamp_pos()
        self._apply_pos()
        self.sprite.set_state(self._ai_dir)

    # -- system tray --

    def _setup_tray(self):
        if not (HAS_PYSTRAY and HAS_PIL):
            return
        img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
        d   = ImageDraw.Draw(img)
        d.ellipse([9, 2, 23, 16],    fill='#F4C68F', outline='#D4A870')
        d.rectangle([7, 16, 25, 28], fill='white')
        d.rectangle([7, 16, 18, 28], fill='#FF8800')
        d.line([11, 28,  9, 32], fill='#F4C68F', width=3)
        d.line([21, 28, 23, 32], fill='#F4C68F', width=3)

        def toggle(_icon, _item):
            if self.visible:
                self.root.after(0, self.root.withdraw);  self.visible = False
            else:
                self.root.after(0, self.root.deiconify); self.visible = True

        def do_quit(_icon, _item):
            _icon.stop()
            self.root.after(0, self.quit)

        menu = pystray.Menu(
            pystray.MenuItem('Show / Hide', toggle, default=True),
            pystray.MenuItem('Quit', do_quit),
        )
        icon = pystray.Icon('Modi', img, 'Modi Character', menu)
        threading.Thread(target=icon.run, daemon=True).start()
        self.tray = icon

    # -- lifecycle --

    def quit(self):
        if self.tray:
            try: self.tray.stop()
            except Exception: pass
        self.root.destroy()

    def _tick(self):
        self._ai_step()
        self.sprite.advance()
        self.root.after(ANIM_MS, self._tick)

    def run(self):
        self.root.after(50, self._tick)
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    print("Modi Desktop Character — hai to mumkin hai!")
    print()

    # Check for image
    try:
        pngs = [f for f in os.listdir(ASSETS_DIR)
                if f.lower().endswith('.png') and not f.startswith('.')]
    except OSError:
        pngs = []

    if pngs:
        print(f"Found sprite image(s) in assets/: {', '.join(pngs)}")
        if not HAS_PIL:
            print("  → Install Pillow to use them:  pip install pillow")
    else:
        print("No image found in assets/ — using drawn character.")
        print("  To use a real photo/render: drop a PNG (transparent bg) into assets/")
        print("  Preferred name: assets/modi.png  (character should face RIGHT)")

    print()
    print("Controls:")
    print("  Arrow keys       — manual movement")
    print("  Space            — wave")
    print("  Double-click     — wave")
    print("  Right-click      — context menu")
    print("  Click + drag     — reposition")
    print("  Escape / Q       — quit")

    if not HAS_PIL:
        print()
        print("Optional: pip install pillow pystray   (image support + system tray)")

    ModiApp().run()


if __name__ == '__main__':
    main()
