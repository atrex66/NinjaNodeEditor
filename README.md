# NinjaNodeEditor

[English](README.md) · [Magyar](README.hu.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Polski](README.pl.md) · [Srpski](README.sr.md) · [Español](README.es.md)

A visual PLC logic editor and LinuxCNC HAL component generator, built with Python and PySide6.

Create typed node graphs, test them with the built-in simulator, and export the complete project as a LinuxCNC `.comp` source file. The editor runs independently of LinuxCNC, on a desktop or directly on a Raspberry Pi display through Qt EGLFS/KMS. The interface is designed around an 800 × 600 workspace.

[Detailed user guides in all seven languages](docs/README.md) · [MIT license](LICENSE)

[Publication validation](VALIDATION.md) · [Watchdog, ramps, filters, sequencer and feedback memory](PROCESSING.hu.md)

## Features

- Counter: A rising-edge up/down counter with reset, enable, an s32 count and a threshold output. [counter.json](examples/counter.json).
- Timer: rising-edge trigger, reset, whole-millisecond duration and level/pulse output; see the detailed guide.
- Typed signals: `bit`, `float`, `s32` and `u32`, with automatic conversions and visible conversion annotations.
- Math expressions with automatically detected input ports, comparisons, logical operators and mathematical functions.
- Digital input debounce and edge detection; digital output ON/OFF delays and inversion.
- Two-sample FIFO history with automatic type inheritance.
- PID controllers with output limits, integral anti-windup, derivative filtering, optional setpoint feedforward and an error output.
- Triggered error messages with cooldown and an optional reset override.
- Named parameters referenced as `@name`, exported as configurable HAL input pins.
- Reusable Math templates, including four-bit and eight-bit to U32 conversion.
- Multiple editor modules in one project, preserving connections and exporting as one component.
- Local simulation with a grouped monitor and editable inputs and parameters.
- JSON project files, remembered last project, and an empty-start recovery option.
- English, Hungarian, German, French, Polish, Serbian (Latin) and Spanish interfaces.

## Requirements

For editing and simulation:

- Python 3 with a compatible PySide6 installation. Current development environments use Python 3.13; see [requirements.txt](requirements.txt) for the supported PySide6 version range.
- A desktop display environment, or Qt EGLFS/KMS support for direct display operation on Linux.

For compiling exported components, install the LinuxCNC development tools providing `halcompile` and a C compiler on the target system. LinuxCNC is not required for editing, simulation or source export. The exporter supports the legacy LinuxCNC 2.9 pin access style and the setter-based API used by current 2.10 development sources. Compile with the toolchain matching your target installation and architecture.

## Quick start: desktop

Download or clone the repository, then enter its directory:

```sh
cd NinjaNodeEditor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./run.sh --windowed
```

`run.sh` uses `python3` from your environment. To select an interpreter explicitly:

```sh
PLC_PYTHON="$PWD/.venv/bin/python" ./run.sh --windowed
```

Try an included project:

```sh
./run.sh --windowed --project examples/bit-to-u32.json
```

## Raspberry Pi / DietPi: direct display

The supplied DietPi setup uses Debian's matching system PySide6 and Qt packages. Run it on the Pi:

```sh
cd ~/NinjaNodeEditor
bash ./setup-dietpi.sh
./run-eglfs.sh
```

The setup script runs `sudo apt-get update`, installs `python3-pyside6.qtwidgets` and `libqt6opengl6`, and checks the EGLFS/KMS dependency. Package availability depends on your distribution. The EGLFS launcher defaults to `/usr/bin/python3`, independently of an activated virtual environment.

Launch from a local console with access to the display and input devices. EGLFS uses DRM/KMS directly, so the display must be available to the application.

Two display profiles are included:

| Profile | Configuration |
| --- | --- |
| `eglfs-kms.json` | HDMI1 at 800 × 600. |
| `eglfs-kms-card1.json` | `/dev/dri/card1`, HDMI1 at its preferred mode. |

The launcher selects the card1 profile when `/sys/class/drm/card1-HDMI-A-1` exists. Connector names and DRM device numbers depend on the machine. Override the profile when needed:

```sh
QT_QPA_EGLFS_KMS_CONFIG=/path/to/display.json ./run-eglfs.sh
```

`PLC_PYTHON` also overrides the EGLFS interpreter, but that Python's Qt installation must supply a working EGLFS/KMS plugin and its matching libraries.

## Basic workflow

1. Add Input and Output nodes and give the exported pins unique names.
2. Add processing nodes, then edit their properties in the right panel.
3. Connect an output socket to an input socket by clicking them in sequence or dragging between them.
4. Start **Simulate**. The property panel becomes a grouped monitor for inputs, constants, outputs and internal signals. Toggle bit inputs with a checkbox or by clicking their node's simulated-state text; edit numeric inputs in the monitor.
5. Stop simulation to return to node properties, and save the project as JSON.
6. Use **Export** to generate a `.comp` file, then **Build .so** or `halcompile --compile` to compile it.

The toolbar groups are **Project**, **Settings**, **Modules**, **Nodes**, in that order. Use the bottom-right **Fullscreen** button or **F11** to show only the Nodes toolbar above the graph. The same button or F11 restores the normal workspace; on EGLFS the physical fullscreen display remains fullscreen. When simulation is stopped, the properties panel appears only while a node is selected; click empty background to hide it and expand the canvas. During simulation the state monitor remains visible without selection. Changing the workspace view does not reset the graph or simulation history.

Use the mouse wheel to zoom, drag the empty background to pan, and **Fit** to show the graph. **Ctrl+S** saves; **Delete** removes selected nodes. In expression fields, **Enter** commits the edit and **Shift+Enter** inserts a newline.

Connected Math and Condition nodes lock their formula and variable structure. Disconnect all their inputs and outputs before changing expressions, types, source modes or loading a different template. This keeps existing connections consistent.

## Nodes

| Node | Purpose |
| --- | --- |
| Input | Typed HAL input; bit inversion, debounce and level/rising/falling/both-edge processing. |
| Output | Typed HAL output; bit inversion, ON/OFF delays and initial state. |
| Const | Named parameter with a type and default value; no wire sockets. References use `@name`. |
| Math | Formula with detected variables, individually configured as input ports or local constants; typed `result` output. |
| Condition | Formula producing complementary `true` and `false` bit outputs. |
| Invert | Logical NOT of a bit signal. |
| Logger | Typed signal history with configurable sampling, ringbuffer, CSV/TSV/JSONL and a save trigger. |
| Timer | Triggered timeout with reset and selectable latched level or one-update pulse. |
| FIFO | Current sample `now` and preceding sample `last`; inherits the connected input's type. |
| PID | Setpoint/feedback controller with enable/reset inputs and `out`/`error` outputs. |
| Display | Error message on trigger activation, with cooldown, reset override and optional numeric value. |

FIFO samples once per update; on the first update, `last` uses the configured initial value. It is a two-sample history node, without push/pop operations.

PID feedforward adds `FF gain × setpoint` to the controller output. The derivative acts on feedback, and the combined result is limited by the configured output bounds.

Display exports `rtapi_print_msg(RTAPI_MSG_ERR, ...)` calls. A held active trigger prints once; activations during cooldown are dropped. A rising reset edge rearms the message and overrides cooldown. Error messages do not themselves issue an NC program abort.

## Expressions and types

Example formulas:

```text
n0 * 1 + n1 * 2 + n2 * 4 + n3 * 8
clamp(pressure * @gain, 0, 100)
pressure >= minimum and door_closed
sqrt(x^2 + y^2)
now - last
```

Supported operators are `+`, `-`, `*`, `/`, `%`, `^`, `**`, `<<`, `>>`, comparisons, `and`, `or`, `not` and parentheses. Both `^` and `**` mean exponentiation. `%` uses Python-style modulo, so `-1 % 12` is `11`.

`<<` and `>>` are logical 32-bit shifts with zero-fill. For example, `1 << 3` is `8`, and `128 >> 3` is `16`. The left operand is truncated towards zero and reduced to its low 32 bits, including two's-complement bits for negative values. Bits shifted out are discarded; right shifts do not extend the sign bit. The shift count must be an integer from 0 to 31; invalid counts or nonfinite operands return zero. The result then follows the usual node result-type conversion. Addition binds more tightly than shifts, so use parentheses when combining shifted fields: `(n0 << 0) + (n1 << 1) + (n2 << 2) + (n3 << 3)`.

Functions: `abs`, `min`, `max`, `clamp`, `pow`, `sqrt`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `log`, `log10`, `exp`, `floor` and `ceil`. Trigonometric arguments use radians. Built-in constants `pi` and `e` do not create input ports. Expressions use a validated subset of syntax; arbitrary Python code is not executed.

| Type | Range / behavior |
| --- | --- |
| `bit` | Logical 0 or 1; nonzero numeric values convert to true. |
| `float` | Double-precision numeric calculations. |
| `s32` | −2,147,483,648 to 2,147,483,647. |
| `u32` | 0 to 4,294,967,295. |

Conversions happen automatically at receiving inputs and appear in red when signal types differ. Integer conversions truncate towards zero and clamp to the type's range instead of wrapping. Named Const nodes export HAL input pins with default values, so their values can also be changed in HAL at runtime. For example, `@speed_limit` becomes `<component>.speed-limit`.

Time fields use whole milliseconds in 1 ms increments. Actual timing follows the update period: the local simulator uses 20 ms steps, while a generated component uses its HAL thread period. Use a 1 ms servo thread for 1 ms update resolution.

## Projects, modules and templates

Project JSON stores nodes, connections, properties, positions and module organization. The current format is version 5; versions 1–4 remain readable.

Modules organize the editor view. All modules share one graph, simulation and exported component. Use **All modules** to edit cross-module connections. Removing a module moves its nodes to the first remaining module and preserves their connections.

Math templates store one Math operation's formula, variable configuration, result type and name. Save templates under [templates](templates) to make them appear in the dropdown, or use **Load template** to open another file. The template name appears as the node heading. A node must have no connections before a template can be loaded.

The last successfully opened or saved project is restored at startup. Unsaved edits are not automatically saved. If the remembered file is unavailable or invalid, the editor starts empty and reports the problem. Language and last-project preferences live in `.state/`; `PLC_STATE_DIR` can select another directory.

| Option | Purpose |
| --- | --- |
| `--project path.json` | Open a specific project and remember it after a successful load. |
| `--no-restore` / `--empty` | Start empty without reading the remembered project. |
| `--windowed` | Request a window instead of fullscreen display. |
| `--eglfs` | Select direct EGLFS display operation. |
| `--language en\|hu\|de\|fr\|pl\|sr\|es` | Override the startup UI language. |
| `--screenshot path.png` | Capture the application window, then exit. |

`--project` and `--no-restore` are mutually exclusive. `PLC_LANGUAGE` can also set the startup language. The UI language selector applies immediately and remembers the choice. Translation catalogs are UTF-8 JSON files in [locales](locales); preserve their keys and `{placeholders}` when editing them. The **Manual** button opens the detailed guide in the selected UI language, with English as a fallback. All seven guides are available in [docs](docs/README.md).

## LinuxCNC export and build

Export a component, for example `my_plc.comp`, then compile on the target system. Projects containing a Logger also generate an automatic collector and `.hal` setup; follow the Logger section below for loading those projects:

```sh
halcompile --compile my_plc.comp
```

The GUI's **Build .so** performs the same compilation asynchronously and saves compiler output beside the source as `my_plc.build.txt`. Export and build do not install or load the module.

LinuxCNC 2.10 changes output writes from `pin = value` to `pin_set(value)`. Generated sources use setters with a fallback for older 2.9 versions of `halcompile`. The legacy `bit`, `float`, `s32` and `u32` declarations are still accepted by the current 2.10 generator, with deprecation warnings. Re-export and rebuild when upgrading LinuxCNC; compiled `.so` files are not a cross-version compatibility format.

Compatibility checks cover compilation with the installed 2.9 toolchain and preprocessing/C syntax checks with current upstream 2.10 generator and HAL/RTAPI headers. These checks do not constitute an installed 2.10 runtime or machine-hardware test.

Once you have installed the compiled component in your LinuxCNC module directory, add it to your HAL configuration. For the pressure/pump demo:

```hal
loadrt my_plc
addf my-plc.update servo-thread

# Replace the hardware pin placeholders with your machine's actual pins.
net pressure-feedback <pressure-source-pin> => my-plc.pressure
net pump-command my-plc.pump => <pump-relay-pin>
```

The generated component is a singleton with an `update` function. LinuxCNC converts underscores in its component name to hyphens in the HAL prefix. Graph evaluation uses a topological order, with each node executing once per update. Simulated input values do not replace actual HAL input pins in deployment. A module compiled on another architecture must be rebuilt for the target.

## Examples

| Project | Demonstrates |
| --- | --- |
| [demo.json](examples/demo.json) | Pressure scaling, a condition and delayed pump output. |
| [bit-to-u32.json](examples/bit-to-u32.json) | Packing four bit inputs into an unsigned integer. |
| [math-conversions.json](examples/math-conversions.json) | Mathematical functions and automatic type conversion. |
| [circular-direction.json](examples/circular-direction.json) | Shortest direction between circular positions. |
| [fifo-difference.json](examples/fifo-difference.json) | Difference between the current and previous sample. |
| [pid-controller.json](examples/pid-controller.json) | PID output and error monitoring. |
| [pid-feedforward.json](examples/pid-feedforward.json) | Optional setpoint feedforward. |
| [pid-display.json](examples/pid-display.json) | A triggered message for excessive tracking error. |

The circular-direction example only selects direction. A complete toolchanger requires additional sequencing, feedback, delays and fault handling.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'PySide6'`:** install the dependency into the interpreter used by the launcher. On DietPi, `run-eglfs.sh` defaults to system Python; use `PLC_PYTHON` to choose another environment.
- **`No space left on device` during pip installation:** a small `/tmp` filesystem can fill even with free disk space elsewhere. Put pip's temporary files on a filesystem with enough space:

  ```sh
  mkdir -p "$HOME/.cache/ninjanodeeditor-tmp"
  TMPDIR="$HOME/.cache/ninjanodeeditor-tmp" python -m pip install --no-cache-dir -r requirements.txt
  ```

- **EGLFS/KMS dependency check fails:** run the DietPi setup script and use matching Qt/PySide6 packages. Check the DRM card, connector and device permissions. Mixing system Qt libraries with a different pip Qt version can fail.
- **An expression variable has no socket:** check its source mode. Local Constant variables have no input socket.
- **Template or formula controls are disabled:** disconnect the Math/Condition node before changing its structure.
- **A project prevents normal startup:** launch with `--no-restore`, then open another project.
- **Build fails or cannot start:** check that `halcompile` and the target development tools are installed, and inspect the generated `.build.txt` file.

## Development and verification

The model and exporter live in [model.py](model.py), the Qt interface in [app.py](app.py), startup restoration in [session.py](session.py), and translation support in [i18n.py](i18n.py). Examples, templates and catalogs are ordinary JSON files.

Run the test suite with PySide6 and a C compiler available as `cc`:

```sh
QT_QPA_PLATFORM=offscreen python3 -m unittest test_model test_session test_logger test_hal test_ui test_i18n
```

Tests cover model behavior, project compatibility, UI editing, localization and generated-C/simulation parity. Compile exported `.comp` files separately with the target's `halcompile` for toolchain verification.

For a headless UI preview:

```sh
QT_QPA_PLATFORM=offscreen ./run.sh --windowed --no-restore --screenshot /tmp/ninjanodeeditor.png
```

## Current scope

NinjaNodeEditor is an experimental finite-dataflow editor and code generator. It supports state inside FIFO, timers and PID nodes, but rejects graph feedback cycles. Blocking sequences, motion/G-code execution and live HAL monitoring are not implemented. Local simulation is disconnected from hardware; generated behavior still needs validation in the target machine configuration.

## License

NinjaNodeEditor is distributed under the [MIT License](LICENSE), copyright © 2026 NinjaNodeEditor contributors. Third-party dependencies, including Python, PySide6/Qt and LinuxCNC, retain their respective licenses.

## Logger: triggered history recording

Add **+ Logger**, choose 1–18 data inputs, and connect signals to `in1`, `in2`, etc. Each input automatically follows the source type (bit, float, s32 or u32). The connected module, symbol and output name are recorded too. Unconnected data inputs record zero as float. Connect a bit signal to `trigger`: its rising edge saves the current ringbuffer, oldest sample first. A held HIGH saves once; return LOW before triggering again. Saving does not clear the history.

## Global I/O, LinuxCNC bindings and Live HAL debugging

Use **Global I/O** to add/remove project-wide inputs and outputs. They appear in shared Input/Output blocks in every existing and new module, with one definition and one exported pin per signal. Move the blocks by their frame/header; positions are remembered separately for each module. Double-click an entry in the management window to edit its properties. Ordinary Input/Output nodes can also become global with **Global (all modules)**. Removal deletes the signal and its connections throughout the project. A global output accepts one graph driver: disconnect it before assigning another. Its source-module label and **Go to driver** jump to, select and center the source node.
