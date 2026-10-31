# NinjaNodeEditor

[English](README.md) · [Magyar](README.hu.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Polski](README.pl.md) · [Srpski](README.sr.md) · [Español](README.es.md)

Editor visual de lógica PLC y generador de componentes HAL LinuxCNC, escrito en Python con PySide6. Cree grafos tipados, simúlelos localmente y exporte el proyecto completo como `.comp`. El editor funciona sin LinuxCNC, en escritorio o directamente en la pantalla de Raspberry Pi con Qt EGLFS/KMS. La interfaz está diseñada para 800 × 600.

[Manual detallado en español](docs/USER_GUIDE.es.md) · [Licencia MIT](LICENSE)

## Funciones

- Counter: Conteo ascendente/descendente por flanco, reset, habilitación, valor s32 y salida de umbral. [counter.json](examples/counter.json).
- Timer: inicio por flanco, reset, ms enteros y salida nivel/pulso; detalles en el manual.
- Tipos `bit`, `float`, `s32`, `u32`; conversión automática señalada en rojo.
- Entradas detectadas en expresiones, matemáticas, comparaciones, lógica y desplazamientos `<<`/`>>`.
- Antirrebote y flancos de entrada; retardos ON/OFF e inversión de salida.
- FIFO `last`/`now` con herencia automática del tipo.
- PID con límites, anti-windup, filtro D, feedforward opcional y salida error.
- Mensajes de error con trigger, intervalo mínimo y reset que lo evita.
- Parámetros `@name` exportados como entradas HAL ajustables.
- Plantillas Math, módulos de edición y monitor de simulación agrupado.
- Siete idiomas con manuales; restauración del último proyecto.
- Grupos Project, Settings, Modules, Nodes; pantalla completa abajo a la derecha y propiedades según selección.

## Instalación e inicio

Python 3 y PySide6 según [requirements.txt](requirements.txt). El entorno actual de desarrollo usa Python 3.13. LinuxCNC no es necesario para editar ni simular.

Después de descargar o clonar:

```sh
cd NinjaNodeEditor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./run.sh --windowed
```

Intérprete explícito: `PLC_PYTHON="$PWD/.venv/bin/python" ./run.sh --windowed`.

DietPi con paquetes Qt/PySide6 del sistema compatibles:

```sh
cd ~/NinjaNodeEditor
bash ./setup-dietpi.sh
./run-eglfs.sh
```

El script actualiza apt e instala paquetes con sudo. EGLFS usa `/usr/bin/python3` por defecto, independientemente de un venv activado. Inicie desde una consola local, con pantalla libre y permisos de dispositivos. `QT_QPA_EGLFS_KMS_CONFIG` selecciona un perfil propio; card1 depende del mapa DRM real.

## Uso

```sh
./run.sh --windowed --project examples/bit-to-u32.json
```

Añada nodos desde Nodes, configure sus propiedades y conecte los puertos. Durante Simulate el panel derecho muestra todos los módulos; entradas y parámetros son editables. Al parar, las propiedades solo aparecen para un nodo seleccionado. El botón inferior derecho o F11 activa pantalla completa, dejando solo Nodes sobre el grafo.

Ctrl+S guarda, Supr elimina; rueda para zoom, arrastre del fondo para desplazar. Cambie la estructura de Math/Condition conectados solo después de Disconnect all.

`--project path.json` elige proyecto, `--no-restore`/`--empty` inicia vacío, `--language es` elige idioma. Las opciones proyecto y vacío se excluyen. Preferencias en `.state/` o `PLC_STATE_DIR`. Los cambios sin guardar no se guardan automáticamente.

## Exportación y compatibilidad

Export crea `.comp`; Build .so, o:

```sh
halcompile --compile machine_plc.comp
```

Se requieren herramientas de desarrollo LinuxCNC y compilador C. No se instala/carga el módulo. Compile para la arquitectura destino y añada `update` al servo-thread HAL. Todos los módulos se exportan como un componente.

La exportación usa `pin_set(...)` de API 2.10 con soporte para halcompile 2.9 antiguo. Comprobado: compilación 2.9 instalada y generador/cabeceras 2.10 actuales; sin prueba de ejecución con 2.10 instalado. Tras cambiar versión, vuelva a exportar y compilar.

## Ejemplos y desarrollo

[examples](examples): bits→U32, conversiones, dirección circular, diferencia FIFO, PID/feedforward y mensajes. La dirección circular no es un cambiador completo. [templates](templates): plantillas Math; [locales](locales): catálogos UTF-8.

Pruebas con PySide6 y compilador `cc`:

```sh
QT_QPA_PLATFORM=offscreen python3 -m unittest test_model test_session test_ui test_i18n
```

La simulación no acciona hardware. Editor experimental de flujo finito: no admite ciclos del grafo, comandos de movimiento ni monitor HAL activo. Display no emite abort NC. El manual explica instalación, nodos y diagnóstico.

## Licencia

[MIT License](LICENSE), © 2026 NinjaNodeEditor contributors. Python, PySide6/Qt y LinuxCNC conservan sus propias licencias.

## Logger: guardar el historial mediante trigger

**+ Logger** ofrece 1–18 entradas `in1`, `in2`, etc. El tipo (bit, float, s32, u32) sigue automáticamente la fuente; se guardan módulo, símbolo y nombre de salida. Una entrada sin conectar vale float 0. El flanco ascendente de `trigger` guarda el búfer circular desde la muestra más antigua. HIGH guarda una sola vez; volver a LOW antes de otro disparo. Guardar conserva el historial.

## E/S globales y depuración Live HAL

**E/S globales** administra entradas/salidas compartidas en todos los módulos actuales y futuros. Una definición y un pin exportado por señal; posición del bloque guardada por módulo. Arrastrar marco/título; doble clic en la lista para editar. Input/Output ordinario puede hacerse global. Eliminar borra todas sus conexiones. La salida global tiene una fuente única: desconectar antes de cambiar. Su etiqueta o **Ir a la fuente** abre el módulo y selecciona el nodo.
