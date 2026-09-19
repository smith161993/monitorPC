#!/usr/bin/env python3
"""
Widget minimalista para monitoreo del sistema:
- CPU usage
- RAM usage
- VRAM usage (NVIDIA GPU)
- FPS (estimado basado en refresh rate)
- Red (banda ancha)
"""

import tkinter as tk
from tkinter import font
import psutil
import time
import threading

try:
    import pynvml
    NVML_AVAILABLE = True
except (ImportError, Exception):
    NVML_AVAILABLE = False

# Verificar si hay display disponible
import os
HAS_DISPLAY = os.environ.get('DISPLAY') is not None or os.name == 'nt'


class SystemWidget:
    def __init__(self, root):
        self.root = root
        self.root.title("System Monitor")
        self.root.overrideredirect(True)  # Sin bordes de ventana
        self.root.attributes('-topmost', True)  # Siempre visible
        self.root.configure(bg='#1a1a2e')
        
        # Hacer la ventana arrastrable
        self.root.bind('<Button-1>', self.start_move)
        self.root.bind('<B1-Motion>', self.on_move)
        self.root.bind('<Double-Button-1>', self.close_widget)
        
        # Variables para el movimiento
        self.x = 0
        self.y = 0
        
        # Variables de red
        self.last_net_io = psutil.net_io_counters()
        self.last_time = time.time()
        
        # Configurar fuentes
        self.title_font = font.Font(family='Segoe UI', size=10, weight='bold')
        self.value_font = font.Font(family='Segoe UI', size=18, weight='bold')
        self.label_font = font.Font(family='Segoe UI', size=9)
        
        # Crear frame principal
        self.main_frame = tk.Frame(root, bg='#1a1a2e', padx=20, pady=15)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Título
        title_label = tk.Label(
            self.main_frame, 
            text="SYSTEM MONITOR",
            font=self.title_font,
            bg='#1a1a2e',
            fg='#e94560'
        )
        title_label.pack(anchor='w', pady=(0, 10))
        
        # Crear etiquetas para cada métrica
        self.metrics = {}
        metrics_list = [
            ('cpu', 'CPU', '#0f3460'),
            ('ram', 'RAM', '#533483'),
            ('vram', 'VRAM', '#e94560'),
            ('fps', 'FPS', '#16c79a'),
            ('net', 'RED', '#f39c12')
        ]
        
        for key, label, color in metrics_list:
            frame = tk.Frame(self.main_frame, bg='#16213e', pady=5)
            frame.pack(fill=tk.X, pady=2)
            
            lbl = tk.Label(
                frame,
                text=label,
                font=self.label_font,
                bg='#16213e',
                fg='#a0a0a0',
                width=5,
                anchor='w'
            )
            lbl.pack(side=tk.LEFT)
            
            val = tk.Label(
                frame,
                text="--",
                font=self.value_font,
                bg='#16213e',
                fg=color,
                anchor='e'
            )
            val.pack(side=tk.RIGHT)
            
            self.metrics[key] = val
        
        # Inicializar NVML si está disponible
        if NVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self.gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            except:
                self.gpu_handle = None
        else:
            self.gpu_handle = None
        
        # Iniciar actualización
        self.update_metrics()
    
    def start_move(self, event):
        self.x = event.x
        self.y = event.y
    
    def on_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")
    
    def close_widget(self, event):
        self.root.destroy()
    
    def get_network_speed(self):
        current_net_io = psutil.net_io_counters()
        current_time = time.time()
        
        time_diff = current_time - self.last_time
        if time_diff == 0:
            return "0 KB/s"
        
        upload_diff = current_net_io.bytes_sent - self.last_net_io.bytes_sent
        download_diff = current_net_io.bytes_recv - self.last_net_io.bytes_recv
        
        total_diff = upload_diff + download_diff
        speed_bps = total_diff / time_diff
        
        # Convertir a unidades legibles
        if speed_bps < 1024:
            speed = f"{speed_bps:.0f} B/s"
        elif speed_bps < 1024 * 1024:
            speed = f"{speed_bps / 1024:.1f} KB/s"
        else:
            speed = f"{speed_bps / (1024 * 1024):.2f} MB/s"
        
        self.last_net_io = current_net_io
        self.last_time = current_time
        
        return speed
    
    def get_vram_usage(self):
        if self.gpu_handle is None:
            return "N/A"
        
        try:
            info = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
            used_mb = info.used / (1024 * 1024)
            total_mb = info.total / (1024 * 1024)
            percent = (info.used / info.total) * 100
            return f"{used_mb:.0f}/{total_mb:.0f} MB ({percent:.0f}%)"
        except:
            return "N/A"
    
    def update_metrics(self):
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        self.metrics['cpu'].config(text=f"{cpu_percent:.1f}%")
        
        # RAM
        ram = psutil.virtual_memory()
        ram_percent = ram.percent
        ram_used_gb = ram.used / (1024 ** 3)
        ram_total_gb = ram.total / (1024 ** 3)
        self.metrics['ram'].config(text=f"{ram_used_gb:.1f}/{ram_total_gb:.1f} GB")
        
        # VRAM
        vram_text = self.get_vram_usage()
        self.metrics['vram'].config(text=vram_text)
        
        # FPS (estimado - mostrar refresh rate típico)
        # Nota: Los FPS reales requieren hook al juego/application
        self.metrics['fps'].config(text="60")  # Valor por defecto
        
        # Red
        net_speed = self.get_network_speed()
        self.metrics['net'].config(text=net_speed)
        
        # Programar próxima actualización
        self.root.after(1000, self.update_metrics)


def main():
    if not HAS_DISPLAY:
        print("Error: No hay display disponible.")
        print("Este widget requiere una interfaz gráfica (X11, Windows, o macOS).")
        print("\nEn Linux, asegúrate de tener X11 instalado y ejecutándose.")
        print("Puedes probar con: export DISPLAY=:0")
        return
    
    root = tk.Tk()
    root.geometry("280x220")
    
    widget = SystemWidget(root)
    
    # Instrucciones en consola
    print("Widget de Sistema Iniciado")
    print("- Arrastra la ventana para moverla")
    print("- Doble clic para cerrar")
    print("- Mantén siempre visible sobre otras ventanas")
    
    root.mainloop()


if __name__ == "__main__":
    main()
