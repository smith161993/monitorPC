#!/usr/bin/env python3
"""
Widget minimalista de monitoreo - con panel de configuración, bandeja,
modo bloqueado/desbloqueado y redimensionado.
"""

import tkinter as tk
from tkinter import font
import psutil
import time
import sys
import os
import json
import argparse
import threading
import ctypes

if os.name == 'nt':
    import winreg

try:
    import pynvml
    NVML_AVAILABLE = True
except Exception:
    NVML_AVAILABLE = False

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except Exception:
    TRAY_AVAILABLE = False

HAS_DISPLAY = os.environ.get('DISPLAY') is not None or os.name == 'nt'


# ---------------------------------------------------------------------------
# Colores minimalistas
# ---------------------------------------------------------------------------
COLOR_TEXT            = '#d0d0d0'
COLOR_LABEL           = '#808080'
COLOR_UNIT            = '#606060'
COLOR_MAGIC           = '#010203'
COLOR_BORDER_UNLOCKED = '#ff3b5c'   # borde rojo cuando está desbloqueado


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CONFIG_DIR  = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'SystemWidget')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')

DEFAULT_CONFIG = {
    'transparency':     1.0,
    'font_size':        10,
    'always_on_top':    True,
    'click_through':    False,
    'unlocked':         False,
    'show_cpu':         True,
    'show_ram':         True,
    'show_vram':        True,
    'show_net':         True,
    'show_fps':         True,
    'window_x':         40,
    'window_y':         40,
    'window_w':         0,     # 0 = automático
    'window_h':         0,
}


def load_config():
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        cfg = DEFAULT_CONFIG.copy()
        cfg.update(data)
        return cfg
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"No se pudo guardar config: {e}")


# ---------------------------------------------------------------------------
# Inicio automático Windows
# ---------------------------------------------------------------------------
def get_startup_key():
    if os.name != 'nt':
        return None
    try:
        return winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_ALL_ACCESS
        )
    except Exception:
        return None


def is_startup_enabled():
    if os.name != 'nt':
        return False
    key = get_startup_key()
    if key is None:
        return False
    try:
        winreg.QueryValueEx(key, "SystemWidget")
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        winreg.CloseKey(key)
        return False
    except Exception:
        return False


def enable_startup(script_path):
    if os.name != 'nt':
        return False
    key = get_startup_key()
    if key is None:
        return False
    try:
        exe_path = os.path.abspath(script_path)
        winreg.SetValueEx(key, "SystemWidget", 0, winreg.REG_SZ, f'"{exe_path}"')
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def disable_startup():
    if os.name != 'nt':
        return False
    key = get_startup_key()
    if key is None:
        return False
    try:
        winreg.DeleteValue(key, "SystemWidget")
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Click-through (Windows)
# ---------------------------------------------------------------------------
def set_click_through(window, enable: bool):
    if os.name != 'nt':
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        GWL_EXSTYLE       = -20
        WS_EX_LAYERED     = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_TOOLWINDOW  = 0x00000080

        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW
        if enable:
            style |= WS_EX_TRANSPARENT
        else:
            style &= ~WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    except Exception as e:
        print(f"click-through error: {e}")


# ---------------------------------------------------------------------------
# Widget principal
# ---------------------------------------------------------------------------
class SystemWidget:
    RESIZE_MARGIN = 6   # píxeles desde el borde para detectar redimensionado

    def __init__(self, root, config):
        self.root = root
        self.cfg = config

        self.root.title("System Monitor")
        self.root.overrideredirect(True)
        self.root.configure(bg=COLOR_MAGIC)
        try:
            self.root.wm_attributes('-transparentcolor', COLOR_MAGIC)
        except Exception:
            pass

        # Posición / tamaño inicial
        self.root.geometry(f"+{self.cfg['window_x']}+{self.cfg['window_y']}")
        if self.cfg.get('window_w', 0) and self.cfg.get('window_h', 0):
            self.root.geometry(f"{self.cfg['window_w']}x{self.cfg['window_h']}")

        self.root.attributes('-topmost', bool(self.cfg['always_on_top']))
        self._apply_alpha()

        # Binds de ratón
        self.root.bind('<Button-1>',        self.on_press)
        self.root.bind('<B1-Motion>',       self.on_drag)
        self.root.bind('<ButtonRelease-1>', self.on_release)
        self.root.bind('<Motion>',          self.on_hover)
        self.root.bind('<Button-3>',        self.on_right_click)

        # Estado del arrastre / resize
        self.drag_x = 0
        self.drag_y = 0
        self.resize_mode = None      # None | 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'
        self.resize_start_x = 0
        self.resize_start_y = 0
        self.resize_start_w = 0
        self.resize_start_h = 0
        self.moving = False

        # Red
        self.last_net_io = psutil.net_io_counters()
        self.last_time = time.time()

        # Fuente
        self.font_main = font.Font(family='Consolas',
                                   size=self.cfg['font_size'],
                                   weight='bold')

        # Contenedor con borde (visible cuando desbloqueado)
        self.outer = tk.Frame(root, bg=COLOR_MAGIC, bd=0)
        self.outer.pack(fill=tk.BOTH, expand=True)

        self.main_frame = tk.Frame(self.outer, bg=COLOR_MAGIC)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Métricas
        self.metrics = {}
        self.rows = {}
        metrics_list = [
            ('cpu',  'CPU',  'show_cpu'),
            ('ram',  'RAM',  'show_ram'),
            ('vram', 'VRAM', 'show_vram'),
            ('net',  'RED',  'show_net'),
            ('fps',  'FPS',  'show_fps'),
        ]

        for key, label, cfg_key in metrics_list:
            if not self.cfg.get(cfg_key, True):
                continue
            row = tk.Frame(self.main_frame, bg=COLOR_MAGIC)
            row.pack(fill=tk.X)

            tk.Label(row, text=label, font=self.font_main,
                     bg=COLOR_MAGIC, fg=COLOR_LABEL,
                     anchor='w').pack(side=tk.LEFT)

            unit_lbl = tk.Label(row, text="", font=self.font_main,
                                bg=COLOR_MAGIC, fg=COLOR_UNIT,
                                anchor='e')
            unit_lbl.pack(side=tk.RIGHT)

            val_lbl = tk.Label(row, text="--", font=self.font_main,
                               bg=COLOR_MAGIC, fg=COLOR_TEXT,
                               anchor='e')
            val_lbl.pack(side=tk.RIGHT)

            self.metrics[key] = {'value': val_lbl, 'unit': unit_lbl}
            self.rows[key] = row

        # NVML
        if NVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self.gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            except Exception:
                self.gpu_handle = None
        else:
            self.gpu_handle = None

        self.root.after(200, self._apply_modes)
        self.update_metrics()

    # ------------------------------------------------------------------
    def _apply_alpha(self):
        try:
            if self.cfg.get('unlocked', False):
                self.root.attributes('-alpha', 1.0)
            else:
                self.root.attributes('-alpha', float(self.cfg['transparency']))
        except Exception:
            pass

    def _apply_modes(self):
        unlocked = self.cfg.get('unlocked', False)
        set_click_through(self.root,
                          bool(self.cfg.get('click_through', False)) and not unlocked)
        if unlocked:
            self.outer.config(bg=COLOR_BORDER_UNLOCKED, bd=2)
        else:
            self.outer.config(bg=COLOR_MAGIC, bd=0)
        self._apply_alpha()

    # ------------------------------------------------------------------
    # Ratón: mover + redimensionar + menú
    # ------------------------------------------------------------------
    def _get_resize_mode(self, x, y):
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        m = self.RESIZE_MARGIN
        left   = x <= m
        right  = x >= w - m
        top    = y <= m
        bottom = y >= h - m

        if top and left:     return 'nw'
        if top and right:    return 'ne'
        if bottom and left:  return 'sw'
        if bottom and right: return 'se'
        if top:              return 'n'
        if bottom:           return 's'
        if left:             return 'w'
        if right:            return 'e'
        return None

    def on_hover(self, event):
        if not self.cfg.get('unlocked', False):
            return
        mode = self._get_resize_mode(event.x, event.y)
        cursors = {
            'n': 'size_n',  's': 'size_s',  'e': 'size_e',  'w': 'size_w',
            'ne': 'size_ne', 'nw': 'size_nw', 'se': 'size_se', 'sw': 'size_sw',
            None: 'arrow',
        }
        try:
            self.root.config(cursor=cursors.get(mode, 'arrow'))
        except Exception:
            pass

    def on_press(self, event):
        if not self.cfg.get('unlocked', False):
            return
        mode = self._get_resize_mode(event.x, event.y)
        if mode:
            self.resize_mode = mode
            self.resize_start_x = event.x_root
            self.resize_start_y = event.y_root
            self.resize_start_w = self.root.winfo_width()
            self.resize_start_h = self.root.winfo_height()
            self.resize_start_win_x = self.root.winfo_x()
            self.resize_start_win_y = self.root.winfo_y()
        else:
            self.moving = True
            self.drag_x = event.x
            self.drag_y = event.y

    def on_drag(self, event):
        if not self.cfg.get('unlocked', False):
            return

        # Redimensionar
        if self.resize_mode:
            dx = event.x_root - self.resize_start_x
            dy = event.y_root - self.resize_start_y

            new_x = self.resize_start_win_x
            new_y = self.resize_start_win_y
            new_w = self.resize_start_w
            new_h = self.resize_start_h

            if 'e' in self.resize_mode:
                new_w = max(80, self.resize_start_w + dx)
            if 'w' in self.resize_mode:
                new_w = max(80, self.resize_start_w - dx)
                new_x = self.resize_start_win_x + (self.resize_start_w - new_w)
            if 's' in self.resize_mode:
                new_h = max(40, self.resize_start_h + dy)
            if 'n' in self.resize_mode:
                new_h = max(40, self.resize_start_h - dy)
                new_y = self.resize_start_win_y + (self.resize_start_h - new_h)

            self.root.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")
            return

        # Mover
        if self.moving:
            dx = event.x - self.drag_x
            dy = event.y - self.drag_y
            new_x = self.root.winfo_x() + dx
            new_y = self.root.winfo_y() + dy
            self.root.geometry(f"+{new_x}+{new_y}")
            self.cfg['window_x'] = new_x
            self.cfg['window_y'] = new_y

    def on_release(self, event):
        self.resize_mode = None
        self.moving = False
        # Guardar tamaño/posición
        self.cfg['window_x'] = self.root.winfo_x()
        self.cfg['window_y'] = self.root.winfo_y()
        if self.cfg.get('unlocked', False):
            self.cfg['window_w'] = self.root.winfo_width()
            self.cfg['window_h'] = self.root.winfo_height()
        save_config(self.cfg)

    def on_right_click(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="⚙ Configuración", command=open_settings)
        menu.add_separator()
        if self.cfg.get('unlocked', False):
            menu.add_command(label="🔒 Bloquear", command=self.lock)
        else:
            menu.add_command(label="🔓 Desbloquear para mover/redimensionar",
                             command=self.unlock)
        menu.add_separator()
        menu.add_command(label="❌ Salir", command=quit_app)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def lock(self):
        self.cfg['unlocked'] = False
        self._apply_modes()
        save_config(self.cfg)

    def unlock(self):
        self.cfg['unlocked'] = True
        self._apply_modes()
        save_config(self.cfg)

    # ------------------------------------------------------------------
    def get_network_speed(self):
        cur = psutil.net_io_counters()
        now = time.time()
        dt = now - self.last_time
        if dt <= 0:
            return 0.0
        up   = cur.bytes_sent - self.last_net_io.bytes_sent
        down = cur.bytes_recv - self.last_net_io.bytes_recv
        bps = (up + down) / dt
        self.last_net_io = cur
        self.last_time = now
        return bps

    @staticmethod
    def format_speed(bps):
        if bps < 1024:
            return f"{bps:.0f}", "B"
        elif bps < 1024 ** 2:
            return f"{bps / 1024:.1f}", "K"
        elif bps < 1024 ** 3:
            return f"{bps / 1024 ** 2:.2f}", "M"
        else:
            return f"{bps / 1024 ** 3:.2f}", "G"

    def get_vram_usage(self):
        if self.gpu_handle is None:
            return None, None
        try:
            info = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
            used = info.used / 1024 ** 2
            total = info.total / 1024 ** 2
            return f"{used:.0f}/{total:.0f}", "MB"
        except Exception:
            return None, None

    def update_metrics(self):
        try:
            if 'cpu' in self.metrics:
                cpu = psutil.cpu_percent(interval=None)
                self.metrics['cpu']['value'].config(text=f"{cpu:.0f}")
                self.metrics['cpu']['unit'].config(text="%")

            if 'ram' in self.metrics:
                ram = psutil.virtual_memory()
                used = ram.used / 1024 ** 3
                total = ram.total / 1024 ** 3
                self.metrics['ram']['value'].config(text=f"{used:.1f}/{total:.1f}")
                self.metrics['ram']['unit'].config(text="G")

            if 'vram' in self.metrics:
                val, unit = self.get_vram_usage()
                if val is None:
                    self.metrics['vram']['value'].config(text="--")
                    self.metrics['vram']['unit'].config(text="")
                else:
                    self.metrics['vram']['value'].config(text=val)
                    self.metrics['vram']['unit'].config(text=unit)

            if 'net' in self.metrics:
                bps = self.get_network_speed()
                val, unit = self.format_speed(bps)
                self.metrics['net']['value'].config(text=val)
                self.metrics['net']['unit'].config(text=unit + "/s")

            if 'fps' in self.metrics:
                self.metrics['fps']['value'].config(text="60")
                self.metrics['fps']['unit'].config(text="")
        except tk.TclError:
            return

        self.root.after(1000, self.update_metrics)

    def apply_new_settings(self):
        try:
            self.root.attributes('-topmost', bool(self.cfg['always_on_top']))
        except Exception:
            pass
        self.cfg['window_x'] = self.root.winfo_x()
        self.cfg['window_y'] = self.root.winfo_y()
        save_config(self.cfg)
        self._apply_modes()


# ---------------------------------------------------------------------------
# Variables globales
# ---------------------------------------------------------------------------
widget = None
settings_window = None
tray_icon = None


# ---------------------------------------------------------------------------
# Ventana de configuración
# ---------------------------------------------------------------------------
def open_settings():
    global settings_window
    if settings_window is not None and settings_window.winfo_exists():
        settings_window.lift()
        return

    settings_window = tk.Toplevel()
    settings_window.title("Configuración - System Widget")
    settings_window.geometry("380x640")
    settings_window.configure(bg='#1e1e1e')
    settings_window.attributes('-topmost', True)

    fg_main = '#e0e0e0'

    # Contenedor scrollable por si la ventana es chica
    canvas = tk.Canvas(settings_window, bg='#1e1e1e', highlightthickness=0)
    scrollbar = tk.Scrollbar(settings_window, orient="vertical", command=canvas.yview)
    content = tk.Frame(canvas, bg='#1e1e1e')

    content.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.create_window((0, 0), window=content, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def section(text):
        tk.Label(content, text=text, font=('Segoe UI', 11, 'bold'),
                 bg='#1e1e1e', fg='#00bcd4', anchor='w').pack(fill=tk.X, padx=15, pady=(15, 5))

    def cb(text, var):
        tk.Checkbutton(content, text=text, variable=var,
                       bg='#1e1e1e', fg=fg_main, selectcolor='#2a2a2a',
                       activebackground='#1e1e1e', activeforeground=fg_main,
                       font=('Segoe UI', 10), anchor='w',
                       highlightthickness=0, bd=0).pack(fill=tk.X, padx=20)

    # --- Variables ---
    var_startup      = tk.BooleanVar(value=is_startup_enabled())
    var_topmost      = tk.BooleanVar(value=widget.cfg['always_on_top'])
    var_clickthrough = tk.BooleanVar(value=widget.cfg['click_through'])
    var_unlocked     = tk.BooleanVar(value=widget.cfg.get('unlocked', False))
    var_alpha        = tk.DoubleVar(value=widget.cfg['transparency'])
    var_font         = tk.IntVar(value=widget.cfg['font_size'])
    var_cpu          = tk.BooleanVar(value=widget.cfg['show_cpu'])
    var_ram          = tk.BooleanVar(value=widget.cfg['show_ram'])
    var_vram         = tk.BooleanVar(value=widget.cfg['show_vram'])
    var_net          = tk.BooleanVar(value=widget.cfg['show_net'])
    var_fps          = tk.BooleanVar(value=widget.cfg['show_fps'])

    section("Sistema")
    cb("Iniciar con Windows", var_startup)
    cb("Siempre visible (topmost)", var_topmost)
    cb("Click-through (ignorar clics)", var_clickthrough)
    cb("🔓 Desbloquear (mover/redimensionar)", var_unlocked)

    section("Transparencia")
    tk.Label(content, text="0.3 (muy transparente)  —  1.0 (opaco)",
             bg='#1e1e1e', fg='#888', font=('Segoe UI', 8)).pack(anchor='w', padx=20)
    tk.Scale(content, from_=0.3, to=1.0, resolution=0.05,
             orient=tk.HORIZONTAL, variable=var_alpha,
             bg='#1e1e1e', fg=fg_main, troughcolor='#2a2a2a',
             highlightthickness=0, bd=0, length=320).pack(padx=20, fill=tk.X)

    section("Tamaño de fuente")
    tk.Scale(content, from_=7, to=20, resolution=1,
             orient=tk.HORIZONTAL, variable=var_font,
             bg='#1e1e1e', fg=fg_main, troughcolor='#2a2a2a',
             highlightthickness=0, bd=0, length=320).pack(padx=20, fill=tk.X)

    section("Métricas visibles")
    cb("CPU",  var_cpu)
    cb("RAM",  var_ram)
    cb("VRAM", var_vram)
    cb("RED",  var_net)
    cb("FPS",  var_fps)

    # --- Botones ---
    btn_frame = tk.Frame(content, bg='#1e1e1e')
    btn_frame.pack(fill=tk.X, padx=15, pady=20)

    def on_apply(rebuild=False):
        # Detectar si hay que reconstruir (fuente o filas)
        need_rebuild = (
            rebuild or
            var_font.get() != widget.cfg['font_size'] or
            var_cpu.get() != widget.cfg['show_cpu'] or
            var_ram.get() != widget.cfg['show_ram'] or
            var_vram.get() != widget.cfg['show_vram'] or
            var_net.get() != widget.cfg['show_net'] or
            var_fps.get() != widget.cfg['show_fps']
        )

        # Guardar todo
        widget.cfg['always_on_top'] = var_topmost.get()
        widget.cfg['click_through'] = var_clickthrough.get()
        widget.cfg['unlocked']      = var_unlocked.get()
        widget.cfg['transparency']  = var_alpha.get()
        widget.cfg['font_size']     = var_font.get()
        widget.cfg['show_cpu']      = var_cpu.get()
        widget.cfg['show_ram']      = var_ram.get()
        widget.cfg['show_vram']     = var_vram.get()
        widget.cfg['show_net']      = var_net.get()
        widget.cfg['show_fps']      = var_fps.get()

        # Inicio automático
        want = var_startup.get()
        have = is_startup_enabled()
        if want and not have:
            enable_startup(sys.executable if getattr(sys, 'frozen', False)
                           else os.path.abspath(__file__))
        elif not want and have:
            disable_startup()

        widget.apply_new_settings()

        if need_rebuild:
            rebuild_widget()

    tk.Button(btn_frame, text="Aplicar", command=lambda: on_apply(False),
              bg='#00bcd4', fg='#000', font=('Segoe UI', 10, 'bold'),
              relief=tk.FLAT, padx=20, pady=6).pack(side=tk.RIGHT, padx=5)
    tk.Button(btn_frame, text="Cerrar", command=settings_window.destroy,
              bg='#333', fg='#e0e0e0', font=('Segoe UI', 10),
              relief=tk.FLAT, padx=20, pady=6).pack(side=tk.RIGHT, padx=5)

    settings_window.protocol("WM_DELETE_WINDOW", settings_window.destroy)


# ---------------------------------------------------------------------------
# Reconstruir widget (cambio de fuente/filas)
# ---------------------------------------------------------------------------
def rebuild_widget():
    global widget
    widget.cfg['window_x'] = widget.root.winfo_x()
    widget.cfg['window_y'] = widget.root.winfo_y()
    save_config(widget.cfg)

    root = widget.root
    for child in root.winfo_children():
        child.destroy()
    widget = SystemWidget(root, widget.cfg)
    widget._apply_modes()


# ---------------------------------------------------------------------------
# Bandeja del sistema
# ---------------------------------------------------------------------------
def make_tray_image():
    img = Image.new('RGB', (64, 64), color=(20, 20, 20))
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, 56, 56], outline=(0, 188, 212), width=3)
    d.text((20, 24), "S", fill=(0, 188, 212))
    return img


def run_tray():
    global tray_icon
    if not TRAY_AVAILABLE:
        return

    def on_settings(icon, item):
        widget.root.after(0, open_settings)

    def on_toggle_lock(icon, item):
        def toggle():
            if widget.cfg.get('unlocked', False):
                widget.lock()
            else:
                widget.unlock()
        widget.root.after(0, toggle)

    def on_toggle_widget(icon, item):
        def toggle():
            if widget.root.winfo_viewable():
                widget.root.withdraw()
            else:
                widget.root.deiconify()
        widget.root.after(0, toggle)

    def on_quit(icon, item):
        icon.stop()
        widget.root.after(0, quit_app)

    menu = pystray.Menu(
        pystray.MenuItem("⚙ Configuración", on_settings),
        pystray.MenuItem("🔓 Desbloquear / Bloquear", on_toggle_lock),
        pystray.MenuItem("👁 Mostrar / Ocultar widget", on_toggle_widget),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("❌ Salir", on_quit),
    )
    tray_icon = pystray.Icon("SystemWidget", make_tray_image(),
                             "System Widget", menu)
    tray_icon.run()


def quit_app():
    save_config(widget.cfg)
    try:
        if tray_icon:
            tray_icon.stop()
    except Exception:
        pass
    try:
        widget.root.quit()
        widget.root.destroy()
    except Exception:
        pass
    sys.exit(0)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    global widget

    parser = argparse.ArgumentParser()
    parser.add_argument('--install-startup',   action='store_true')
    parser.add_argument('--uninstall-startup', action='store_true')
    args = parser.parse_args()

    script_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)

    if args.install_startup:
        print("✓ Registrado" if enable_startup(script_path) else "✗ Error")
        return
    if args.uninstall_startup:
        print("✓ Eliminado" if disable_startup() else "✗ Error")
        return

    if not HAS_DISPLAY:
        print("Error: No hay display disponible.")
        return

    cfg = load_config()

    root = tk.Tk()
    widget = SystemWidget(root, cfg)

    if TRAY_AVAILABLE:
        threading.Thread(target=run_tray, daemon=True).start()

    print("System Widget iniciado.")
    print("- Clic derecho en el widget → menú")
    print("- Ícono en bandeja del sistema → opciones")

    root.mainloop()


if __name__ == "__main__":
    main()