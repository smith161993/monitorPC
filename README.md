# System Widget - Monitor de Recursos

Widget minimalista para monitorear en tiempo real: CPU, RAM, VRAM, FPS y uso de Red.

## 📥 Descarga

El archivo ejecutable está disponible en la carpeta `dist/`:
- **Linux**: `dist/system_widget`
- **Windows**: Ejecuta el comando de construcción (ver abajo)

## ✨ Características

- **CPU**: Porcentaje de uso en tiempo real
- **RAM**: GB usados / totales
- **VRAM**: Memoria de GPU NVIDIA (usada/total)
- **FPS**: Valor estimado (60 FPS por defecto)
- **RED**: Ancho de banda en B/s, KB/s o MB/s

### Diseño Minimalista
- Tema oscuro moderno
- Sin bordes de ventana
- Arrastrable (clic y mueve)
- Siempre visible sobre otras ventanas
- Doble clic para cerrar

## 🚀 Instalación y Uso

### Opción 1: Usando Python (Recomendado)

```bash
# Instalar dependencias
pip install psutil pynvml

# Ejecutar widget
python system_widget.py
```

### Opción 2: Usando el ejecutable (.exe para Windows)

#### Construir el .exe en Windows:

```bash
# Instalar PyInstaller
pip install pyinstaller

# Crear el ejecutable
pyinstaller --onefile --windowed --name "system_widget" system_widget.py

# El ejecutable estará en: dist/system_widget.exe
```

#### Usar el ejecutable:

```bash
# Ejecutar widget
system_widget.exe

# Registrar para inicio automático con Windows
system_widget.exe --install-startup

# Eliminar del inicio automático
system_widget.exe --uninstall-startup
```

## 🎮 Controles

| Acción | Resultado |
|--------|-----------|
| Clic y arrastrar | Mover el widget |
| Doble clic | Cerrar el widget |

## 📋 Requisitos

- **Python**: 3.7+
- **Librerías**: 
  - `psutil` (monitoreo del sistema)
  - `pynvml` (monitoreo de GPU NVIDIA - opcional)
  - `tkinter` (interfaz gráfica - incluido con Python)

## 🔧 Notas Importantes

1. **VRAM**: Solo funciona con GPUs NVIDIA. Si tienes AMD o Intel, mostrará "N/A".

2. **FPS**: El valor mostrado es una estimación (60 FPS). Para FPS reales de juegos, se requiere integración específica con cada juego.

3. **Inicio Automático**: La función `--install-startup` solo funciona en Windows. En otros sistemas operativos, debes agregar manualmente el ejecutable a las aplicaciones de inicio.

4. **Entorno Gráfico**: Requiere un display (X11 en Linux, Windows GUI, o macOS). No funciona en servidores headless.

## 🛠️ Comandos Disponibles

```bash
# Mostrar ayuda
system_widget.exe --help

# Iniciar widget normalmente
system_widget.exe

# Registrar para inicio con Windows
system_widget.exe --install-startup

# Eliminar del inicio
system_widget.exe --uninstall-startup
```

## 📁 Estructura del Proyecto

```
/workspace/
├── system_widget.py      # Código fuente
├── README.md             # Documentación
├── dist/
│   └── system_widget     # Ejecutable compilado
└── build/                # Archivos temporales de compilación
```

## ⚠️ Solución de Problemas

**Error: "No hay display disponible"**
- Asegúrate de tener un entorno gráfico activo
- En Linux: `export DISPLAY=:0`

**VRAM muestra "N/A"**
- Verifica que tengas una GPU NVIDIA
- Instala los drivers de NVIDIA
- Ejecuta: `pip install pynvml`

**El widget no inicia con Windows**
- Ejecuta como administrador: `system_widget.exe --install-startup`
- Verifica que tu antivirus no bloquee el registro

---

**Hecho con ❤️ para monitoreo minimalista del sistema**
