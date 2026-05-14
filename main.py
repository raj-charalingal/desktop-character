#!/usr/bin/env python3
"""
Modi Desktop Character
Transparent, always-on-top animated desktop companion.
Run: python main.py
"""

import tkinter as tk
import math
import random
import threading
from enum import Enum

try:
    from PIL import Image, ImageDraw, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pystray
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
WIN_W, WIN_H = 120, 165          # Overlay window dimensions (px)
CX = WIN_W // 2                   # Character center X on canvas
CY = WIN_H - 12                   # Character feet Y on canvas

CHROMA = '#00FF00'                # Window pixels of this color → transparent

FPS = 16
ANIM_MS = 1000 // FPS
WALK_SPEED = 2                    # px per frame

# Character palette (none should equal CHROMA)
C_SKIN  = '#F4C68F'
C_HAIR  = '#F0F0F0'               # Modi's white hair
C_KURTA = '#FFFFFF'               # White kurta
C_PANTS = '#F0F0F8'
C_SCARF = '#FF8800'               # Saffron
C_SHOE  = '#1A1A1A'
C_BEARD = '#EFEFEF'
C_EYE_P = '#111111'

NFRAMES = 8                       # Animation frames per cycle


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
# Sprite — draws Modi on a Canvas using geometric shapes
# ---------------------------------------------------------------------------
class Sprite:
    """
    Renders a cartoon Modi character frame-by-frame onto a tkinter Canvas.
    Character feet are anchored at (CX, CY).
    Replace _render() with sprite-sheet logic when real PNGs are available.
    """

    def __init__(self, canvas: tk.Canvas):
        self.c = canvas
        self.state = State.IDLE
        self.frame = 0
        self._ids: list[int] = []

    def advance(self):
        self.frame = (self.frame + 1) % NFRAMES
        self._render()

    def set_state(self, s: State):
        self.state = s

    # -- internals --

    def _clear(self):
        for i in self._ids:
            self.c.delete(i)
        self._ids = []

    def _put(self, item_id: int):
        self._ids.append(item_id)

    def _render(self):
        self._clear()
        c = self.c
        x, y = CX, CY
        f = self.frame
        s = self.state

        phase    = (f / NFRAMES) * 2 * math.pi
        moving   = s in (State.WALKL, State.WALKR, State.RUNL, State.RUNR)
        running  = s in (State.RUNL, State.RUNR)
        waving   = s == State.WAVE

        swing    = 32 if running else (22 if moving else 0)
        bob_amp  =  4 if running else ( 2 if moving else 0)

        leg_swing = math.sin(phase) * swing
        body_bob  = abs(math.sin(phase)) * bob_amp if moving else math.sin(phase * 0.5) * 1.2

        # Key Y positions (measured upward from feet)
        hip_y      = y - 4
        waist_y    = y - 42
        shoulder_y = y - 72 - int(body_bob)
        head_y     = y - 96 - int(body_bob)
        HR         = 16                          # head radius

        going_right = s in (State.WALKR, State.RUNR)

        def leg_pts(hip_x: int, angle_deg: float):
            a  = math.radians(angle_deg)
            ul, ll = 22, 22
            kx = hip_x + math.sin(a) * ul
            ky = hip_y + math.cos(a) * ul
            a2 = math.radians(angle_deg * 0.3)
            fx = kx + math.sin(a2) * ll
            fy = ky + math.cos(a2) * ll
            return int(kx), int(ky), int(fx), int(fy)

        def arm_pts(sh_x: int, angle_deg: float):
            a  = math.radians(angle_deg)
            ua, la = 16, 14
            ex = sh_x + math.sin(a) * ua
            ey = shoulder_y + math.cos(a) * ua
            a2 = math.radians(angle_deg * 0.5)
            hx = ex + math.sin(a2) * la
            hy = ey + math.cos(a2) * la
            return int(ex), int(ey), int(hx), int(hy)

        lkx, lky, lfx, lfy = leg_pts(x - 8,  leg_swing)
        rkx, rky, rfx, rfy = leg_pts(x + 8, -leg_swing)

        arm_swing = -leg_swing * 0.65
        lex, ley, lhx, lhy = arm_pts(x - 14,  arm_swing + 10)
        rex, rey, rhx, rhy = arm_pts(x + 14, -arm_swing - 10)

        def draw_leg(hx, kx, ky, fx, fy):
            self._put(c.create_line(hx, hip_y, kx, ky, fx, fy,
                                    fill=C_PANTS, width=8, smooth=True,
                                    joinstyle=tk.ROUND, capstyle=tk.ROUND))
            self._put(c.create_oval(fx - 9, fy - 5, fx + 9, fy + 4,
                                    fill=C_SHOE, outline=''))

        def draw_arm(sh_x, ex, ey, hx, hy):
            self._put(c.create_line(sh_x, shoulder_y, ex, ey, hx, hy,
                                    fill=C_SKIN, width=6, smooth=True,
                                    joinstyle=tk.ROUND, capstyle=tk.ROUND))

        # === Draw order: back-to-front ===

        # Back leg
        if going_right:
            draw_leg(x + 8, rkx, rky, rfx, rfy)
        else:
            draw_leg(x - 8, lkx, lky, lfx, lfy)

        # Kurta body
        self._put(c.create_polygon(
            x - 18, shoulder_y,  x + 18, shoulder_y,
            x + 16, waist_y,     x + 12, hip_y,
            x - 12, hip_y,       x - 16, waist_y,
            fill=C_KURTA, outline='#DDDDDD', width=1, smooth=True
        ))

        # Front leg
        if going_right:
            draw_leg(x - 8, lkx, lky, lfx, lfy)
        else:
            draw_leg(x + 8, rkx, rky, rfx, rfy)

        # Back arm
        if going_right:
            draw_arm(x + 14, rex, rey, rhx, rhy)
        else:
            draw_arm(x - 14, lex, ley, lhx, lhy)

        # Saffron scarf drape
        self._put(c.create_line(
            x - 14, shoulder_y + 2,
            x +  4, shoulder_y + 8,
            x + 18, shoulder_y - 2,
            fill=C_SCARF, width=4, smooth=True
        ))

        # Neck
        self._put(c.create_rectangle(x - 5, head_y + HR - 2, x + 5, shoulder_y + 2,
                                     fill=C_SKIN, outline=''))

        # Head
        self._put(c.create_oval(x - HR, head_y - HR, x + HR, head_y + HR,
                                fill=C_SKIN, outline='#D9A870', width=1))

        # White hair
        self._put(c.create_arc(x - HR, head_y - HR, x + HR, head_y + 4,
                               start=0, extent=180,
                               fill=C_HAIR, outline='#CCCCCC', width=1))

        # Eyes
        for dx in (-6, 6):
            self._put(c.create_oval(x + dx - 4, head_y - 5, x + dx + 4, head_y + 3,
                                    fill='white', outline='#999', width=1))
            self._put(c.create_oval(x + dx - 2, head_y - 3, x + dx + 2, head_y + 1,
                                    fill=C_EYE_P))

        # Mustache (two arcs)
        for side in (-1, 1):
            mx = x + side * 6
            self._put(c.create_arc(mx - 7, head_y + 3, mx + 7, head_y + 12,
                                   start=180, extent=180,
                                   fill=C_BEARD, outline='#BBBBBB', width=1))

        # Beard
        self._put(c.create_arc(x - 13, head_y - 1, x + 13, head_y + HR + 10,
                               start=200, extent=140,
                               fill=C_BEARD, outline='#CCCCCC', width=1))

        # Front arm (or waving arm)
        if waving:
            wave_angle = -55 + math.sin(phase * 2) * 30
            wex, wey, whx, why = arm_pts(x - 14, wave_angle)
            draw_arm(x - 14, wex, wey, whx, why)
            draw_arm(x + 14, rex, rey, rhx, rhy)
        elif going_right:
            draw_arm(x - 14, lex, ley, lhx, lhy)
        else:
            draw_arm(x + 14, rex, rey, rhx, rhy)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------
class ModiApp:
    def __init__(self):
        self.root = tk.Tk()
        self._init_window()

        self.canvas = tk.Canvas(self.root, width=WIN_W, height=WIN_H,
                                bg=CHROMA, highlightthickness=0, bd=0)
        self.canvas.pack()

        self.sprite = Sprite(self.canvas)

        # Window screen position
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self._wx = sw - WIN_W - 60
        self._wy = sh - WIN_H - 80
        self._clamp_pos(sw, sh)
        self._apply_pos()

        # Drag state
        self._drag_ox = 0
        self._drag_oy = 0
        self._dragging = False

        # AI state
        self._ai_paused = False
        self.visible = True
        self._ai_dir = random.choice([State.WALKL, State.WALKR])
        self._ai_steps = 0
        self._ai_target = random.randint(60, 200)

        self.tray = None
        self._bind_events()
        self._setup_tray()

    # -- window setup --

    def _init_window(self):
        r = self.root
        r.overrideredirect(True)            # borderless
        r.attributes('-topmost', True)      # always on top
        r.attributes('-transparentcolor', CHROMA)
        r.config(bg=CHROMA)
        r.title('Modi Character')

    def _apply_pos(self):
        self.root.geometry(f'+{self._wx}+{self._wy}')

    def _clamp_pos(self, sw=None, sh=None):
        if sw is None:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
        self._wx = max(0, min(sw - WIN_W, self._wx))
        self._wy = max(0, min(sh - WIN_H, self._wy))

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
        if dx < 0:
            self.sprite.set_state(State.WALKL)
        elif dx > 0:
            self.sprite.set_state(State.WALKR)
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

    # -- AI autonomous movement --

    def _ai_step(self):
        if self._ai_paused or not self.visible:
            return

        sw = self.root.winfo_screenwidth()
        margin = 30

        # Bounce off screen edges
        if self._wx <= margin:
            self._ai_dir = State.WALKR
        elif self._wx >= sw - WIN_W - margin:
            self._ai_dir = State.WALKL

        # Decide new behavior at waypoint
        self._ai_steps += 1
        if self._ai_steps >= self._ai_target:
            self._ai_steps = 0
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
                self._ai_dir = State.WALKL if self._ai_dir == State.WALKR else State.WALKR

        # Move one step
        if self._ai_dir == State.WALKR:
            self._wx += WALK_SPEED
        else:
            self._wx -= WALK_SPEED
        self._clamp_pos()
        self._apply_pos()
        self.sprite.set_state(self._ai_dir)

    # -- system tray --

    def _setup_tray(self):
        if not (HAS_PYSTRAY and HAS_PIL):
            return

        img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([9, 2, 23, 16],  fill='#F4C68F', outline='#D4A870')  # head
        d.rectangle([7, 16, 25, 28], fill='white')                      # body
        d.rectangle([7, 16, 18, 28], fill='#FF8800')                    # scarf hint
        d.line([11, 28,  9, 32], fill='#F4C68F', width=3)               # left leg
        d.line([21, 28, 23, 32], fill='#F4C68F', width=3)               # right leg

        def toggle(_icon, _item):
            if self.visible:
                self.root.after(0, self.root.withdraw)
                self.visible = False
            else:
                self.root.after(0, self.root.deiconify)
                self.visible = True

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
            try:
                self.tray.stop()
            except Exception:
                pass
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
    print("Controls:")
    print("  Arrow keys       — manual movement")
    print("  Space            — wave")
    print("  Double-click     — wave")
    print("  Right-click      — context menu")
    print("  Click + drag     — reposition")
    print("  Escape / Q       — quit")
    if not HAS_PIL:
        print()
        print("Optional: pip install pillow pystray   (enables system tray icon)")

    ModiApp().run()


if __name__ == '__main__':
    main()
