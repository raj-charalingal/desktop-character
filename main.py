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
WIN_W, WIN_H = 150, 220
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
HR           = 20          # drawn head radius in pixels
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
    Game-character style Modi:
      - Real face extracted from assets/modi.png and used as the head
      - Fully animated drawn body: arms and legs swing independently
      - Walking, running, waving, idle animations all work frame-by-frame
    """

    def __init__(self, canvas: tk.Canvas, cx: int, cy: int):
        self.c     = canvas
        self.cx    = cx
        self.cy    = cy
        self.state = State.IDLE
        self.frame = 0
        self._ids: list[int] = []
        self.img_w = 0
        self.img_h = 0

        # Real face image (right + left facing), kept alive to avoid GC
        self._face_r: 'ImageTk.PhotoImage | None' = None
        self._face_l: 'ImageTk.PhotoImage | None' = None
        self._face_w = 0
        self._face_h = 0

        self._load_face()

    # -- public API --

    def has_image(self) -> bool:
        return self._face_r is not None

    def advance(self):
        self.frame = (self.frame + 1) % NFRAMES
        self._render()

    def set_state(self, s: State):
        self.state = s

    # -- face extraction --

    def _load_face(self):
        """Load modi.png and crop out just the face/head to use on the drawn body."""
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

            face = self._extract_face(img)
            if face:
                self._face_w = face.width
                self._face_h = face.height
                self._face_r = ImageTk.PhotoImage(face)
                self._face_l = ImageTk.PhotoImage(ImageOps.mirror(face))
                print(f"Face loaded from {chosen}: {face.width}×{face.height} px")
            else:
                print(f"Could not isolate face in {chosen} — using drawn head")
        except Exception as exc:
            print(f"Warning — {exc}")

    def _extract_face(self, img: 'Image.Image') -> 'Image.Image | None':
        """
        Crop the head region from a full-body portrait with transparent background.
        Finds non-transparent pixels in the top 30% to locate the head precisely.
        """
        top_h = int(img.height * 0.30)
        bbox  = img.crop((0, 0, img.width, top_h)).getbbox()
        if not bbox:
            return None
        l, t, r, b = bbox
        pad  = 5
        face = img.crop((max(0, l - pad), max(0, t - pad),
                         min(img.width, r + pad), min(top_h, b + pad)))
        # Scale to fit the drawn head (HR*2 diameter)
        face.thumbnail((HR * 2 + 8, HR * 2 + 8), Image.LANCZOS)
        return face

    # -- render --

    def _clear(self):
        for i in self._ids:
            self.c.delete(i)
        self._ids = []

    def _put(self, item_id: int):
        self._ids.append(item_id)

    def _render(self):
        self._clear()
        self._render_body()

    def _render_body(self):
        """
        Draw the full animated character each frame.
        Uses swinging leg/arm math for walk/run/wave.
        Head is the real face image if available, drawn oval otherwise.
        """
        c     = self.c
        x, y  = self.cx, self.cy
        f     = self.frame
        s     = self.state

        phase      = (f / NFRAMES) * 2 * math.pi
        moving     = s in (State.WALKL, State.WALKR, State.RUNL, State.RUNR)
        running    = s in (State.RUNL,  State.RUNR)
        waving     = s == State.WAVE
        going_right = s in (State.WALKR, State.RUNR)
        going_left  = s in (State.WALKL, State.RUNL)

        swing     = 36 if running else (25 if moving else 0)
        bob_amp   =  6 if running else ( 3 if moving else 0)
        leg_swing = math.sin(phase) * swing
        body_bob  = (abs(math.sin(phase)) * bob_amp if moving
                     else math.sin(phase * 0.5) * 1.5)

        # Key Y positions measured up from feet
        hip_y      = y - 6
        waist_y    = y - 55
        shoulder_y = y - 95 - int(body_bob)
        head_cy    = y - 128 - int(body_bob)   # centre of head

        def leg_pts(hip_x: int, angle_deg: float):
            a  = math.radians(angle_deg)
            ul, ll = 28, 30                     # upper / lower leg lengths
            kx = hip_x + math.sin(a) * ul
            ky = hip_y + math.cos(a) * ul
            a2 = math.radians(angle_deg * 0.35)
            return int(kx), int(ky), int(kx + math.sin(a2)*ll), int(ky + math.cos(a2)*ll)

        def arm_pts(sh_x: int, angle_deg: float):
            a  = math.radians(angle_deg)
            ua, la = 20, 18
            ex = sh_x + math.sin(a) * ua
            ey = shoulder_y + math.cos(a) * ua
            a2 = math.radians(angle_deg * 0.5)
            return int(ex), int(ey), int(ex + math.sin(a2)*la), int(ey + math.cos(a2)*la)

        lkx,lky,lfx,lfy = leg_pts(x - 10,  leg_swing)
        rkx,rky,rfx,rfy = leg_pts(x + 10, -leg_swing)
        arm_sw = -leg_swing * 0.65
        lex,ley,lhx,lhy = arm_pts(x - 18,  arm_sw + 12)
        rex,rey,rhx,rhy = arm_pts(x + 18, -arm_sw - 12)

        def draw_leg(hx, kx, ky, fx, fy):
            self._put(c.create_line(hx, hip_y, kx, ky, fx, fy,
                fill=C_PANTS, width=11, smooth=True, joinstyle=tk.ROUND, capstyle=tk.ROUND))
            self._put(c.create_oval(fx-11, fy-6, fx+11, fy+5,
                fill=C_SHOE, outline='#111', width=1))

        def draw_arm(sh_x, ex, ey, hx, hy):
            self._put(c.create_line(sh_x, shoulder_y, ex, ey, hx, hy,
                fill=C_SKIN, width=9, smooth=True, joinstyle=tk.ROUND, capstyle=tk.ROUND))

        # === Draw order: back → front ===

        # Back leg
        if going_right: draw_leg(x+10, rkx, rky, rfx, rfy)
        else:           draw_leg(x-10, lkx, lky, lfx, lfy)

        # Kurta body
        self._put(c.create_polygon(
            x-24, shoulder_y,  x+24, shoulder_y,
            x+20, waist_y,     x+16, hip_y,
            x-16, hip_y,       x-20, waist_y,
            fill=C_KURTA, outline='#CCCCCC', width=1, smooth=True
        ))
        # Kurta centre seam
        self._put(c.create_line(x, shoulder_y+2, x, waist_y-2,
                                fill='#DDDDDD', width=1, dash=(3, 5)))

        # Front leg
        if going_right: draw_leg(x-10, lkx, lky, lfx, lfy)
        else:           draw_leg(x+10, rkx, rky, rfx, rfy)

        # Back arm
        if going_right: draw_arm(x+18, rex, rey, rhx, rhy)
        else:           draw_arm(x-18, lex, ley, lhx, lhy)

        # Saffron scarf
        self._put(c.create_line(
            x-20, shoulder_y+2,  x+2, shoulder_y+12,  x+24, shoulder_y-2,
            fill=C_SCARF, width=6, smooth=True))

        # Neck
        self._put(c.create_rectangle(x-7, head_cy + HR - 2, x+7, shoulder_y+2,
                                     fill=C_SKIN, outline=''))

        # ---- HEAD ----
        if self._face_r:
            # Real Modi face centred at head_cy
            face_img = self._face_l if going_left else self._face_r
            self._put(c.create_image(x, head_cy + self._face_h // 2,
                                     image=face_img, anchor='s'))
        else:
            # Drawn fallback head
            self._put(c.create_oval(x-HR, head_cy-HR, x+HR, head_cy+HR,
                                    fill=C_SKIN, outline='#D9A870', width=1))
            self._put(c.create_arc(x-HR, head_cy-HR, x+HR, head_cy+5,
                                   start=0, extent=180, fill=C_HAIR, outline='#CCCCCC'))
            for dx in (-7, 7):
                self._put(c.create_oval(x+dx-5, head_cy-7, x+dx+5, head_cy+3,
                                        fill='white', outline='#999', width=1))
                self._put(c.create_oval(x+dx-2, head_cy-4, x+dx+2, head_cy+1, fill=C_EYE_P))
            for side in (-1, 1):
                mx = x + side*7
                self._put(c.create_arc(mx-8, head_cy+3, mx+8, head_cy+14,
                                       start=180, extent=180, fill=C_BEARD, outline='#BBBBBB'))
            self._put(c.create_arc(x-14, head_cy, x+14, head_cy+HR+14,
                                   start=200, extent=140, fill=C_BEARD, outline='#CCCCCC'))

        # Front arm (or waving arm)
        if waving:
            wa = -65 + math.sin(phase * 2) * 40
            wex, wey, whx, why = arm_pts(x - 18, wa)
            draw_arm(x - 18, wex, wey, whx, why)
            draw_arm(x + 18, rex, rey, rhx, rhy)
        elif going_right: draw_arm(x - 18, lex, ley, lhx, lhy)
        else:             draw_arm(x + 18, rex, rey, rhx, rhy)


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

        self.sprite  = Sprite(self.canvas, WIN_W // 2, WIN_H - 12)
        self._win_w  = WIN_W
        self._win_h  = WIN_H

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
