# NinjaNodeEditor — manual de uso detallado

NinjaNodeEditor permite editar la lógica de un componente PLC completo como un grafo de nodos, simularla localmente y exportar código fuente LinuxCNC `.comp`. El simulador no se conecta al HAL activo ni al hardware. **Build .so** solo compila; la instalación y la carga son operaciones separadas.

## Contenido

1. Inicio e idioma
2. Interfaz y edición
3. Proyectos y módulos
4. Tipos y conversión
5. Nodos
6. Expresiones y referencias
7. Plantillas Math
8. Simulación y diagnóstico
9. Exportación, compilación e integración HAL
10. Ejemplos prácticos
11. Solución de problemas
12. LinuxCNC 2.9 / 2.10

## 1. Inicio e idioma

En Raspberry Pi, desde el directorio de la aplicación:

```sh
cd ~/NinjaNodeEditor
./run-eglfs.sh
```

En un escritorio gráfico use `./run.sh --windowed`. EGLFS requiere bibliotecas Qt EGLFS/KMS compatibles y acceso a la pantalla y a los dispositivos de entrada. Otra aplicación puede estar usando la pantalla. En DietPi, `bash ./setup-dietpi.sh` instala los paquetes del sistema correspondientes. El lanzador EGLFS usa `/usr/bin/python3` por defecto. Para seleccionar otro intérprete:

```sh
PLC_PYTHON="$PWD/.venv/bin/python" ./run-eglfs.sh
```

| Opción | Acción |
| --- | --- |
| `--project path.json` | Abre ese proyecto en lugar del último archivo recordado. |
| `--no-restore` / `--empty` | Inicia vacío sin leer el proyecto recordado. |
| `--windowed` | Solicita el modo de ventana. |
| `--language es` | Selecciona el idioma inicial. |
| `--screenshot /tmp/preview.png` | Guarda una captura y termina. |

`--project` y `--no-restore` se excluyen mutuamente. Idiomas: inglés (`en`), húngaro (`hu`), alemán (`de`), francés (`fr`), polaco (`pl`), serbio en alfabeto latino (`sr`) y español (`es`). Los cambios se aplican inmediatamente y se recuerdan. `--language` o `PLC_LANGUAGE` reemplaza la selección inicial; sin preferencia se usa inglés. **Manual** abre la guía del idioma seleccionado, o la inglesa si falta el archivo.

No se traducen identificadores, fórmulas, nombres de módulos/plantillas ni mensajes del usuario. Las preferencias están en `.state/`; `PLC_STATE_DIR` permite elegir otro directorio.

## 2. Interfaz y edición

Los grupos superiores son Proyecto, Ajustes, Módulos y Nodos, en ese orden. Contienen operaciones de proyecto, idioma/manual/simulación, organización de módulos y creación de nodos. El grafo está a la izquierda y las propiedades a la derecha.

Los grupos son **Proyecto**, **Ajustes**, **Módulos**, **Nodos**, en ese orden. **Pantalla completa** abajo a la derecha o **F11** deja únicamente Nodos sobre el grafo. El mismo botón o F11 restaura la vista normal; en EGLFS la pantalla física sigue a pantalla completa. Con la simulación parada, las propiedades aparecen solo con un nodo seleccionado; haga clic en el fondo vacío para ocultarlas y ampliar el grafo. Durante la simulación el monitor sigue visible sin selección. Cambiar de vista conserva el grafo y el historial.

Proyecto, Ajustes y Módulos son filas compactas con la etiqueta al principio. Nodos conserva su marco con título, dejando más espacio en pantallas pequeñas.

| Acción | Uso |
| --- | --- |
| Crear/seleccionar/mover un nodo | Botón `+` correspondiente; clic o arrastre sobre el cuerpo. |
| Selección múltiple | Ctrl y clic. |
| Conectar | Clic en una salida y después una entrada, o arrastrar. |
| Cancelar conexión | Escape. |
| Desplazar vista / zoom | Arrastrar el fondo vacío / rueda del ratón. |
| Mostrar todo el grafo | **Fit**. |
| Eliminar / guardar | Supr / Ctrl+S o los botones correspondientes. |

Las entradas amarillas reciben señales y las salidas azules las proporcionan. Cada entrada tiene una fuente; conectar otra reemplaza el cable anterior. **Disconnect inputs** elimina conexiones entrantes; **Disconnect all** elimina todas las conexiones del nodo.

El texto se confirma al perder el foco. En una expresión, Enter confirma y Mayús+Enter añade una línea. Los números se confirman al terminar la entrada, sin ejecutar cada valor parcial.

## 3. Proyectos y módulos

El JSON conserva nodos, parámetros, cables, posiciones y módulos. El inicio normal restaura el último proyecto abierto o guardado correctamente; sin archivo recordado se muestra una demostración. Los cambios sin guardar no se guardan automáticamente. **New** crea un grafo vacío sin olvidar la última ruta. Un archivo ausente o inválido produce un inicio vacío con diagnóstico; use **Open** para recuperarse.

Los módulos organizan la edición de un único componente. **New module** crea un grupo, **Rename** lo renombra y **Move selected** mueve nodos. **Remove module** mueve sus nodos al primer módulo restante y conserva los cables; debe quedar al menos un módulo. **All modules** muestra el grafo completo y permite editar conexiones entre módulos.

Las conexiones ocultas siguen activas. La ayuda del puerto identifica el otro módulo y nodo. Simulación, constantes y nombres HAL son globales; la exportación incluye todos los módulos. Los nodos nuevos pertenecen al módulo seleccionado, o al primero en la vista global. El formato 4 conserva la organización; los formatos 1–3 siguen siendo legibles y sitúan los nodos antiguos en Main. Un editor antiguo puede no leer formato 4.

## 4. Tipos y conversión

| Tipo | Significado |
| --- | --- |
| `bit` | 0 o 1; cualquier número distinto de cero se convierte en verdadero. |
| `float` | Número de coma flotante de doble precisión. |
| `s32` | Entero con signo, −2147483648…2147483647. |
| `u32` | Entero sin signo, 0…4294967295. |

Se pueden conectar tipos distintos. La entrada receptora convierte automáticamente y lo indica en rojo. La conversión entera trunca hacia cero y limita al rango: `3.9` → s32 `3`, `-2` → u32 `0`.

Antirrebote, retardos ON/OFF, intervalo entre mensajes y filtro D del PID usan milisegundos enteros con pasos de 1 ms. Cero desactiva el retardo/filtro. La resolución real depende del periodo de actualización; los pasos de simulación de 20 ms no distinguen eventos individuales de 1 ms.

## 5. Nodos

### Input

Entrada HAL externa con nombre único, comenzando por minúscula; admite cifras y guiones, como `pressure` o `door-closed`. **Simulated input** proporciona el valor bruto local. Un bit también se puede cambiar haciendo clic en su texto de estado simulado.

Procesamiento de bits: inversión, antirrebote y detección de activación. El nuevo nivel debe mantenerse estable durante el tiempo configurado. `level` proporciona el nivel estable; `rising`, `falling`, `both` producen un pulso de una actualización. Una entrada inicialmente activa puede producir un pulso ascendente. La exportación lee el pin HAL real; el valor simulado no sustituye el cableado del hardware.

### Output

Salida HAL con una entrada `in`. Sin conexión utiliza el valor/estado inicial. Los retardos ON/OFF exigen mantener la solicitud; su reversión cancela la transición pendiente. La inversión ocurre después del retardo. El estado inicial establece el estado lógico almacenado al arrancar.

### Const

Parámetro con nombre, tipo y valor predeterminado, sin puertos. Use `@gain` en fórmulas o el selector de referencia en propiedades numéricas. Los nombres comienzan por minúscula y admiten cifras y guiones bajos. `@speed_limit` se exporta como `<component>.speed-limit`.

Cada Const se convierte en un **pin de entrada HAL** con valor predeterminado, modificable mediante `setp` o una señal. Su propio valor debe ser literal, sin referencia a otra constante. Elimine todas sus referencias antes de borrar una Const en uso.

### Math y Condition

Las variables de la expresión crean entradas automáticamente; cada una tiene tipo, fuente y valor predeterminado. **Input port** crea un puerto; **Constant** utiliza el valor configurado sin puerto. Los valores pueden referenciar `@name`.

Math proporciona `result` de tipo configurable. Condition proporciona bits complementarios `true` y `false`, no ramas de ejecución. En nodos conectados se bloquean los cambios estructurales de fórmulas, tipos, fuentes y plantillas hasta usar **Disconnect all**.

### Invert

NO lógico de un bit. La entrada desconectada vale 0, por lo que su salida vale 1.

### FIFO

`now` contiene la muestra actual; `last`, la de la actualización anterior. En la primera actualización `last` usa el valor inicial. La fuente conectada determina los tipos de todos los puertos; sin conexión se selecciona un tipo de respaldo.

Se toma una muestra por actualización, incluso sin cambios. Es un historial de dos muestras, no una cola push/pop. No permite ciclos de realimentación del grafo, porque `now` depende de la entrada actual.

### Timer / tiempo de espera

**+ Temporizador** tiene entradas bit `trigger`, `reset` y salida bit `out`. **Duración ms** es un entero no negativo, paso 1 ms, defecto 1000; admite Const. El flanco ascendente inicia, incluso con trigger inicialmente alto en la primera actualización. La caída del trigger no cancela; los flancos durante el conteo se ignoran. La duración se lee al iniciar y queda fija para ese ciclo. El contador empieza en 0 y las actualizaciones siguientes añaden su periodo. Cero vence inmediatamente.

`level`: tras vencer, `out=1` hasta reset, sin nuevos inicios. `pulse`: 1 durante una actualización al vencer, después 0; un nuevo flanco ascendente puede reiniciar. Reset es sensible a nivel y prioritario: HIGH cancela y borra la salida. Un trigger mantenido alto durante reset no reinicia al soltarlo; debe bajar y subir. Reset en el ciclo de vencimiento suprime la salida. Entradas desconectadas: 0. Simulación: pasos de 20 ms; HAL: periodo del thread. Periodos inválidos/no positivos borran el estado.

Para timeout, inicio de operación a trigger y finalización correcta a reset. Nivel para fallo retenido, pulso para una notificación. [timeout.json](../examples/timeout.json) muestra 1000 ms, salida HAL timeout y Display. Iniciar/parar la simulación borra el historial.

### PID

Entradas: `setpoint`, `feedback`, `enable`, `reset`. Salidas float: `out`, `error`. Cuando está activo, `error = setpoint − feedback`.

Kp es proporcional, Ki integra en el tiempo y Kd deriva la medida, evitando un pico por un salto de consigna. **D filter ms** filtra la derivada. **Output min/max** limita el resultado; el anti-windup limita el crecimiento de la integral hacia fuera del rango permitido.

El feedforward opcional añade `FF gain × setpoint`. Desactivar o resetear el controlador pone ambas salidas a cero y borra el historial. Las entradas no conectadas setpoint, feedback y enable usan las propiedades; reset vale 0 por defecto.

### Display

Entradas: `trigger`, `value`, `reset`. Entrar en el nivel activo configurado emite un mensaje. **Append value** añade el valor numérico. Las activaciones durante el intervalo de bloqueo se descartan, no se encolan; mantener el trigger activo no repite mensajes.

El flanco ascendente de reset evita el bloqueo y rearma la emisión; mantener reset alto no repite. En simulación el texto aparece en la barra de estado. La exportación emite un error RTAPI, sin orden de abortar el programa NC.

## 6. Expresiones y referencias

Operaciones admitidas:

```text
+  -  *  /  %  ^  **  <<  >>
==  !=  <  <=  >  >=
and  or  not
```

`^` y `**` significan potencia, no XOR. El resto `%` sigue el signo del divisor; división/modulo por un divisor casi nulo devuelve cero. `pi` y `e` no crean puertos.

`<<` y `>>` son desplazamientos lógicos de 32 bits con relleno de ceros: `1 << 3` da 8 y `128 >> 3` da 16. El operando izquierdo se trunca hacia cero y se reduce a sus 32 bits inferiores; los negativos usan complemento a dos. Los bits expulsados se pierden; el desplazamiento derecho no extiende el signo. La cantidad debe ser entera de 0 a 31; cantidades inválidas u operandos no finitos dan cero. Después se aplica la conversión habitual del resultado. La suma tiene prioridad sobre los desplazamientos: use paréntesis.

Funciones: `abs`, `min`, `max`, `clamp`, `pow`, `sqrt`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `log`, `log10`, `exp`, `floor`, `ceil`. Ángulos en radianes; min/max toman dos argumentos y clamp tres. Dominios inválidos o resultados no finitos dan cero. No se ejecuta código Python arbitrario.

```text
(n0 << 0) + (n1 << 1) + (n2 << 2) + (n3 << 3)
clamp(x * @gain, 0, @maximum)
abs(actual - requested) < tolerance
sin(angle * pi / 180)
```

`@name` requiere una Const existente y no crea puerto. Las referencias funcionan en parámetros numéricos, valores iniciales y enable predeterminado del PID. La conversión sigue el tipo receptor; los tiempos se redondean a milisegundos enteros. Las referencias de estado inicial se leen en la primera actualización. Se rechazan nombres desconocidos, reservados o duplicados.

## 7. Plantillas Math

Guarde/cargue plantillas en las propiedades Math o selecciónelas de la lista. Incluyen fórmula, tipo del resultado, fuentes/tipos/valores de variables y nombre, sin cables. El nombre aparece como título del nodo.

`templates/` contiene AND2, OR2 y empaquetado de cuatro/ocho bits en U32. Las plantillas propias aparecen al reconstruir el panel. Desconecte todas las entradas y salidas antes de cargar una plantilla o cambiar la estructura de Math/Condition/FIFO conectados. Las Const referenciadas deben existir ya en el proyecto destino.

## 8. Simulación y diagnóstico

**Simulate** reinicia el historial y ejecuta pasos de 20 ms; **Stop** restaura las propiedades. El temporizador Qt no es un planificador de tiempo real. El monitor muestra todos los módulos, una fila por entrada, constante, salida o señal interna. Entradas y constantes son editables; la ayuda indica nombre completo, tipo y módulo. Si una entrada procesada difiere del valor bruto, se muestra por separado. Cambie la Const si controla el valor de una entrada simulada.

Los cambios en vivo de entradas/constantes conservan el historial. Los cambios estructurales o de configuración pueden reiniciarlo. Idioma y módulo solo alteran la vista. La simulación no acciona el hardware.

## 9. Exportación, compilación e integración HAL

1. Guarde el proyecto JSON.
2. Exporte `.comp`: nombre iniciado por minúscula y formado solo por minúsculas, cifras y guiones bajos, por ejemplo `machine_plc.comp`.
3. **Build .so** vuelve a exportar el grafo en la última ruta y ejecuta `halcompile --compile`.
4. Resultado `.so`, registro `.build.txt`. Se necesitan herramientas de desarrollo LinuxCNC.

Compile para la arquitectura destino: un módulo x86 no se carga en Raspberry Pi ARM64. El editor no instala/carga el módulo ni conecta hardware. Una función `update` contiene todos los módulos y entradas Const. Colóquela en el servo-thread existente después de leer y antes de escribir el hardware.

Ejemplo ilustrativo con componente ya instalado y thread existente:

```hal
loadrt machine_plc
addf machine-plc.update servo-thread
setp machine-plc.gain 2.5
```

Use los nombres reales de su exportación y conecte los pins. Input lee un pin externo; Const inicia con su valor predeterminado y puede cambiar mediante `setp` o una señal.

## 10. Ejemplos prácticos

### Cuatro bits a U32

Cuatro Inputs bit a n0…n3 de la plantilla de cuatro bits. En una fórmula propia, variables bit y resultado u32:

```text
n0 + n1 * 2 + n2 * 4 + n3 * 8
```

n0=1, n1=0, n2=1, n3=0 da 5.

### Diferencia FIFO

Entrada float a FIFO; `now`/`last` a Math `now - last`. Para obtener una tasa, divida también entre el periodo real de muestreo.

### Ganancia ajustable

Const `gain`, float, 2; Input `reading`, float; Math `x * @gain`; Output `scaled`, float. Reading a x. Reading=4 da 8; gain=3 da 12 sin recablear.

### Organizar la máquina

Cree módulos Entradas, Lubricación y Husillo, mueva los nodos y conéctelos en All modules. El monitor cubre todo y la exportación sigue siendo un componente. `examples/circular-direction.json` solo elige dirección; un cambiador de herramientas completo requiere secuencias, retención de estado, sensores, retardos y gestión de errores.

## 11. Solución de problemas

| Síntoma | Comprobación |
| --- | --- |
| Falta puerto de expresión | Fuente Input port; Constant y @referencias no crean puertos. |
| Fórmula/tipo/plantilla bloqueada | Primero Disconnect all. |
| Tipo rojo | Revisar la conversión automática. |
| Nodo/cable invisible | All modules, Fit y ayuda del puerto. |
| Const no se borra / referencia desconocida | Eliminar usos / comprobar nombre exacto. |
| Retardo simulado impreciso | Pasos de 20 ms; HAL tiene su propio periodo. |
| Proyecto inicial inválido | `--no-restore`, después un archivo válido. |
| Falla la compilación | `.build.txt`, halcompile, nombres de archivos/pins. |
| FIFO rechaza realimentación | No se admiten ciclos del grafo. |
| Display no detiene NC | Un mensaje de error no es una orden abort. |

Los diagnósticos del sistema/compilador conservan su idioma. Los catálogos están en `locales/`; las traducciones ausentes usan inglés.

## 12. LinuxCNC 2.9 / 2.10

La API actual de desarrollo 2.10 escribe salidas con `pin_set(value)` en lugar de `pin = value`. El exportador genera setters y macros condicionales de asignación para halcompile 2.9 antiguo. `bit`, `float`, `s32`, `u32` siguen aceptados, con posibles avisos de obsolescencia.

Tras actualizar LinuxCNC, vuelva a exportar y compilar con su halcompile. Una `.so` antigua no sustituye la recompilación. Se comprobó la compilación con 2.9 instalado y el código C con generador/cabeceras HAL/RTAPI 2.10 actuales; no constituye una prueba de ejecución con 2.10 instalado ni una prueba de hardware.

## Logger: guardar el historial mediante trigger

**+ Logger** ofrece 1–18 entradas `in1`, `in2`, etc. El tipo (bit, float, s32, u32) sigue automáticamente la fuente; se guardan módulo, símbolo y nombre de salida. Una entrada sin conectar vale float 0. El flanco ascendente de `trigger` guarda el búfer circular desde la muestra más antigua. HIGH guarda una sola vez; volver a LOW antes de otro disparo. Guardar conserva el historial.

Intervalo: milisegundos enteros positivos, también `@constant`; búfer: 1–100000 muestras. Como máximo una muestra por actualización; simulación a 20 ms. Un trigger entre muestras guarda el historial existente. Sin muestras, CSV/TSV contiene solo encabezados y JSONL queda vacío. CSV/TSV incluye nombres y tipos en el encabezado, JSONL en cada línea; `time_ms` es el tiempo transcurrido. Formato numérico: `.0g`–`.17g`, `.0f`–`.17f`, `.0e`–`.17e`; los enteros conservan su valor exacto. Nombre: `{timestamp}` (UTC), `{sequence}`, `{node}`. Un nombre fijo sustituye atómicamente el archivo anterior. El formato seleccionado determina el contenido independientemente de la extensión.

Las rutas relativas usan el directorio del proyecto guardado, o el del editor sin proyecto guardado; en LinuxCNC, el directorio de exportación. Se generan `.comp`, `.logger.py`, `.logger.json`, `.hal`. Instalar el componente con `halcompile` y cargar `.hal` después de crear `servo-thread`. Carga el componente, inicia el colector Python con el módulo LinuxCNC `hal` y añade update. Sustituir las líneas anteriores `loadrt`/`addf`. Mantener los archivos juntos; volver a exportar tras moverlos porque las rutas auxiliares son absolutas.

El hilo de tiempo real transmite registros HAL limitados; el colector guarda el historial y escribe fuera de realtime. Debe funcionar durante el muestreo. Un desbordamiento puede perder muestras/triggers. Una nueva petición mientras se guarda el mismo Logger se informa y omite. Resultados/errores aparecen en la barra de estado o en stderr del colector. Los búferes grandes requieren más memoria. Ejemplo: `examples/logger-history.json`.

Pulsar cerca de una conexión permite seleccionarla incluso con zoom reducido. Se muestra amarilla; Delete elimina conexiones conservando sus nodos. Ctrl-clic permite selección múltiple.

## E/S globales y depuración Live HAL

**E/S globales** administra entradas/salidas compartidas en todos los módulos actuales y futuros. Una definición y un pin exportado por señal; posición del bloque guardada por módulo. Arrastrar marco/título; doble clic en la lista para editar. Input/Output ordinario puede hacerse global. Eliminar borra todas sus conexiones. La salida global tiene una fuente única: desconectar antes de cambiar. Su etiqueta o **Ir a la fuente** abre el módulo y selecciona el nodo.

**Seleccionar pin / señal HAL** ofrece búsqueda y filtros de tipo, dirección y compatibilidad. **Actualizar** consulta asíncronamente `halcmd -s show pin` y `halcmd -s show sig`. Muestra valor, señal HAL, fuente del proyecto y otros pines de la señal. Cargar/guardar catálogo permite trabajar sin conexión. Se copia el tipo; borrar la conexión deja un pin manual. La salida requiere IN o una señal sin fuente existente. Se reutilizan nets existentes; no se trasladan pines ya conectados. Se rechazan conflictos.

Se generan `.comp`, `.hal`, `.unload.hal`, `.test.hal`, `.test.unload.hal`, `.hal.json` y auxiliares Logger. `.hal` carga el proyecto, conecta E/S, establece constantes, inicia Logger y añade update a `servo-thread`. Cargar después de crear pines hardware/GUI y el hilo, también postgui. Motion/hardware queda en la configuración de máquina. `.test.hal` conecta solo entradas. Los archivos unload corresponden a cargas correctas; revisar una carga manual parcialmente fallida. El inicio live revierte los pasos completados ante un error.

**Debug** exporta pines intermedios como `name.debug-n12-result`, FIFO `last`/`now`, PID `out`/`error`. ID estable y manifest mantienen el mapa; el export normal los omite. **Test Live HAL** y Simulate construyen/instalan automáticamente debug mediante `halcompile --install` como `nne_live_<uid>`. Requiere HAL activo, `servo-thread`, Python `hal` y herramientas de desarrollo. La instalación necesita permisos; puede usar `sudo -n` ya autorizado, en caso contrario pide la contraseña sudo en un campo oculto, sin guardarla ni registrarla. Los errores aparecen en el estado.

Solo se conectan entradas externas. El componente calcula realtime; Python HAL lee a unos 20 Hz sin simulación Python paralela. Entradas asignadas de solo lectura; libres ajustables. Stop antes de editar estructura. Pulsos cortos pueden no verse; usar Logger para historial. Se muestra duración y máximo en µs y `.update.time` original. Las unidades HAL dependen del backend; debug mide nanosegundos con `rtapi_get_time()`. Mide el cuerpo update instrumentado, no todo el servo-thread. Stop/salir retira el test y sus conexiones conservando señales existentes. La huella espera un ciclo RT real. Un test por usuario Unix; módulo instalado reutilizado, fuentes temporales eliminadas. Los valores live no sobrescriben valores de simulación guardados.

Manualmente: `sudo halcompile --install name.comp`, luego `halcmd -f name.hal`; para solo entradas, export debug y `name.test.hal`. Descargar antes de recargar: instalar no sustituye un módulo activo. RIP usa su entorno de compilación. Ejemplos: `examples/global-io.json`, `examples/hal-catalogue.json` (catálogo ficticio).

Una conexión directa Input → Output entre enlaces HAL externos del mismo tipo se exporta como una red HAL. Se omiten los pines del componente usados únicamente para esa conexión. El procesamiento, la conversión, los pines internos o las señales HAL existentes distintas mantienen el paso por el componente. Se conservan las entradas que también alimentan lógica interna. Un proyecto de conexiones directas únicamente no necesita loadrt/addf. Debug conserva pines de observación; la prueba Live de entradas no conecta destinos de salida externos.

Live HAL registra fechas, salidas de compilación e instalación, comandos HAL y errores en `.state/logs/live-hal.log` (o `PLC_STATE_DIR/logs/live-hal.log`). La ruta aparece al producirse un error. Rotación: 1 MiB por archivo y tres copias. No se registran contraseñas. La compilación usa el directorio temporal de fuentes en lugar del directorio SSHFS.

## Counter – contador

**+ Contador**: entradas `up`, `down`, `enable`, `reset` (`bit`); salidas `count` (`s32`), `reached` (`bit`). Los flancos ascendentes suman/restan 1; los simultáneos se cancelan. HIGH en el primer ciclo cuenta como flanco. Valor inicial, umbral y habilitación predeterminada son configurables, incluso mediante referencias a constantes.

Entradas desconectadas: LOW, salvo `enable` (habilitación predeterminada, inicialmente activa). Reset HIGH restaura el valor inicial en cada ciclo, incluso deshabilitado. Deshabilitar conserva el valor. Los flancos durante reset/deshabilitación se descartan; un HIGH mantenido no cuenta al habilitar de nuevo. Saturación: −2147483648 a 2147483647. `reached = count >= umbral` se evalúa en cada ciclo, incluso durante reset/deshabilitación, sin enclavamiento. Valor inicial leído al arrancar/resetear; umbral leído cada ciclo. Reiniciar borra el historial.

Ejemplo: [counter.json](../examples/counter.json). En simulación, conmutar `pulse-up` tres veces LOW/HIGH: valor 3 y umbral activo. `pulse-down` reduce a 2; `clear-count` restablece a 0. JSON, simulación, exportación `.comp` y monitores admiten ambos tipos de salida. Los pulsos físicos rápidos requieren contador/encoder de hardware.
