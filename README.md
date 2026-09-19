# Widget de Monitoreo del Sistema

Widget minimalista para PC que muestra en tiempo real:
- **CPU**: Porcentaje de uso
- **RAM**: GB usados / totales
- **VRAM**: Uso de memoria de GPU (NVIDIA)
- **FPS**: Cuadros por segundo (estimado)
- **RED**: Ancho de banda de red (subida + bajada)

## Requisitos

```bash
pip install psutil pynvml
```

**Nota:** Requiere Python con soporte para Tkinter (interfaz gráfica).

## Uso

```bash
python system_widget.py
```

## Características

- **Minimalista**: Diseño limpio y moderno con tema oscuro
- **Arrastrable**: Haz clic y arrastra para mover la ventana
- **Siempre visible**: Se mantiene sobre otras ventanas
- **Cerrar**: Doble clic para cerrar el widget

## Funcionamiento

- **CPU**: Mide el porcentaje de uso actual del procesador
- **RAM**: Muestra memoria usada y total en GB
- **VRAM**: Detecta GPUs NVIDIA y muestra memoria usada/total
- **FPS**: Valor estimado (60 FPS por defecto)
- **RED**: Calcula el ancho de banda en tiempo real (B/s, KB/s o MB/s)

## Notas

- El widget requiere un entorno gráfico (Windows, macOS o Linux con X11)
- VRAM solo funciona con GPUs NVIDIA
- Los FPS reales requieren integración específica con cada juego/aplicación
