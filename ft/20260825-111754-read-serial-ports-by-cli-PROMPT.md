
# prompt 20260825-112327

Actúa como un desarrollador Senior en Python y especialista en interfaces de usuario en terminal (TUI).

Necesito desarrollar una herramienta CLI/TUI en Python para monitorear, filtrar y registrar de forma simultánea múltiples puertos serie provenientes de dispositivos basados en ESP32-S3 (específicamente tableros de desarrollo ESP32-S3-DevKitC-1, que pueden utilizar tanto puertos UART físicos como la interfaz USB/JTAG nativa del chip).

### Restricción Tecnológica Obligatoria:
- El desarrollo debe realizarse utilizando el framework **Textual** para construir la interfaz TUI.

### Requisitos Técnicos y Funcionales:

1. Entrada por línea de comandos (CLI):
   - Debe aceptar múltiples dispositivos serie como argumentos (ejemplo: `python serial_monitor.py /dev/ttyACM0 /dev/ttyACM1 /dev/ttyACM2`).
    - Permitir configurar parámetros de comunicación habituales (por defecto baudrate=115200, 8N1, timeout, etc.) mediante flags opcionales.

2. Lectura y Concurrencia:
    - Lectura no bloqueante y simultánea de todos los puertos especificados (usando `asyncio` + `pyserial-asyncio`, o `threading`) para evitar cuellos de botella.

3. Registro en Archivo (Logging):
   - Cada puerto debe guardar su tráfico en un archivo individual independiente.
   - Formato de nombre de archivo: `log_<puerto>_<YYYYMMDD_HHMMSS>.log`.
   - Cada línea registrada debe incluir un timestamp de alta precisión (ISO 8601 con milisegundos).

4. Interfaz de Usuario TUI (Terminal Side-by-Side):
    - Diseñar la interfaz dividida en columnas dinámicas (side-by-side) según la cantidad de puertos pasados como argumento, utilizando las capacidades de Textual.
    - Control de ejecución: Teclas atajo para pausar/reanudar la visualización en pantalla de los logs de forma individual o global (el streaming en segundo plano hacia los archivos debe continuar o gestionarse correctamente).

5. Sistema de Filtrado y Resaltado (Específico para depuración de microcontroladores):
   - Capacidad de aplicar filtros de texto/regex en tiempo real.
   - Filtros globales (se aplican a todas las ventanas) y filtros específicos para cada dispositivo/puerto.
    - Resaltado visual (colores) para trazas de firmware, identificando automáticamente eventos clave como transmisiones (`TX`), recepciones (`RX`) y reconocimientos (`ACK` / `NACK` o estados de paquetes entre los nodos).

### Entregables requeridos:
- Código completo, bien estructurado, modularizado y comentado, utilizando Textual.
- Dependencias declaradas en `pyproject.toml` y gestionadas con `uv`.
- Ejemplo claro de ejecución y guía rápida de atajos de teclado para la interfaz TUI.
