# NinjaNodeEditor — detailed user guide

NinjaNodeEditor lets you edit a complete PLC component as a node graph, simulate it locally and export LinuxCNC `.comp` source. The simulator is disconnected from live HAL and hardware. **Build .so** compiles the component; installation and loading are separate operations.

## Contents

1. Startup and language
2. Interface and editing
3. Projects and modules
4. Types and conversion
5. Nodes
6. Expressions and parameter references
7. Math templates
8. Simulation and debugging
9. Export, compilation and HAL integration
10. Practical examples
11. Troubleshooting
12. LinuxCNC 2.9 / 2.10 compatibility

## 1. Startup and language

On a Raspberry Pi, start from the application directory:

```sh
cd ~/NinjaNodeEditor
./run-eglfs.sh
```

Use `./run.sh --windowed` on a desktop. EGLFS requires matching Qt EGLFS/KMS support and access to the display and input devices; another graphical application may already own the display. On DietPi, `bash ./setup-dietpi.sh` installs matching system packages. The EGLFS launcher defaults to `/usr/bin/python3`. Select another interpreter explicitly when necessary:

```sh
PLC_PYTHON="$PWD/.venv/bin/python" ./run-eglfs.sh
```

| Option | Action |
| --- | --- |
| `--project path.json` | Open this project instead of the remembered file. |
| `--no-restore` / `--empty` | Start empty without reading the remembered project. |
| `--windowed` | Request windowed operation. |
| `--language en` | Select the startup language. |
| `--screenshot /tmp/preview.png` | Capture the window and exit. |

`--project` and `--no-restore` are mutually exclusive. **Language** offers English (`en`), Hungarian (`hu`), German (`de`), French (`fr`), Polish (`pl`), Serbian Latin (`sr`) and Spanish (`es`). Changes apply immediately and are remembered. `--language` or `PLC_LANGUAGE` overrides the startup selection; the default is English. **Manual** opens the guide in the selected language, falling back to English if its file is missing.

Language changes do not translate identifiers, formulas, module/template names or user-entered messages. Preferences are stored in `.state/`; `PLC_STATE_DIR` can select another directory.

## 2. Interface and editing

Project actions appear first, followed by settings, modules and node creation controls. The graph is on the left and the properties panel on the right.

The toolbar groups are **Project**, **Settings**, **Modules**, **Nodes**, in that order. Use the bottom-right **Fullscreen** button or **F11** to show only the Nodes toolbar above the graph. The same button or F11 restores the normal workspace; on EGLFS the physical fullscreen display remains fullscreen. When simulation is stopped, the properties panel appears only while a node is selected; click empty background to hide it and expand the canvas. During simulation the state monitor remains visible without selection. Changing the workspace view does not reset the graph or simulation history.

Project, Settings and Modules are compact rows with the label at the start of the row. Nodes retains its titled frame to save space on small screens.

| Action | How |
| --- | --- |
| Create/select/move a node | Use its `+` button; click or drag the node body. |
| Select several nodes | Ctrl-click the nodes. |
| Connect | Click the output socket, then the input; dragging also works. |
| Cancel a connection | Escape. |
| Pan / zoom | Drag empty background / use the mouse wheel. |
| Show the whole graph | **Fit**. |
| Delete / save | Delete / Ctrl+S, or the corresponding buttons. |

Yellow input sockets receive signals; blue output sockets provide them. An input has one source. Connecting a new source replaces the previous wire. **Disconnect inputs** removes incoming wires; **Disconnect all** removes both incoming and outgoing wires.

Text edits commit when focus leaves the field. In expression fields, Enter commits and Shift+Enter adds a newline. Numeric edits commit when entry is completed, rather than evaluating each partially typed value.

## 3. Projects and modules

Project JSON stores nodes, parameters, wires, positions and modules. Normal startup restores the last successfully opened or saved project; with no remembered project, a demo appears. Unsaved changes are not saved automatically. **New** opens an empty graph without erasing the remembered filename. A missing or invalid file produces an empty graph and a status message; use **Open** to recover.

Modules organize editing within one component. **New module** creates a group, **Rename** changes its name, and **Move selected** moves nodes. **Remove module** moves its nodes into the first remaining module and preserves connections; at least one module must remain. **All modules** shows the complete graph and lets you edit cross-module wires.

Hidden cross-module connections remain active; socket tooltips identify the other module and node. Simulation, constants and HAL names are global, and export includes every module. New nodes belong to the current module; in All modules they belong to the first module. Project format 4 preserves module names and membership. Formats 1–3 are readable and place older nodes in Main; older editors may not read format 4.

## 4. Types and conversion

| Type | Meaning |
| --- | --- |
| `bit` | 0 or 1; any nonzero numeric value converts to true. |
| `float` | Double-precision floating-point number. |
| `s32` | Signed integer, −2147483648…2147483647. |
| `u32` | Unsigned integer, 0…4294967295. |

Different types can be connected. Conversion happens at the receiving input and appears in red. Integer conversion truncates towards zero and clamps to the range: float `3.9` becomes s32 `3`; float `-2` becomes u32 `0`.

Debounce, ON/OFF delays, Display cooldown and PID D filtering use whole milliseconds in 1 ms increments. Zero disables the delay/filter. Actual resolution depends on the update period: local simulation uses 20 ms steps, so it cannot resolve individual 1 ms events.

## 5. Nodes

### Input

A named external HAL input. Names must be unique, start with a lowercase letter and can contain digits and hyphens, such as `pressure` or `door-closed`. **Simulated input** supplies the local raw value. Bit inputs can also be toggled by clicking the node's simulated-state text.

Bit processing applies inversion, then debounce, then trigger detection. Debounce requires the changed level to remain stable for the configured duration. Trigger modes are `level` (stable level), `rising`, `falling` and `both` (one-update pulses). An initially active input can produce a rising pulse. Export reads the actual HAL input pin; simulation settings do not replace hardware wiring.

### Output

An external HAL output with one `in` socket. Unconnected outputs use the initial value/state. Bit ON/OFF delays require the corresponding request to persist; a reversed request cancels the pending transition. Inversion is applied after the delay. Initial state sets the stored logical state at startup.

### Const

A named typed parameter with a default value and no sockets. Use `@gain` in an expression or select it in a numeric property's reference selector. Names start with a lowercase letter and can contain digits and underscores. `@speed_limit` exports as `<component>.speed-limit`.

Each Const becomes a HAL **input pin** with its default value, so it can be changed at runtime with `setp` or a connected signal. Its own default must be literal, not another constant reference. Delete references before deleting a Const that is still in use.

### Math and Condition

Expression variables create inputs automatically. Each variable has a type, source and default. **Input port** creates a socket; **Constant** uses the configured value without a socket. Variable defaults can themselves reference `@name`.

Math provides a `result` output with a configurable type. Condition provides complementary bit outputs `true` and `false`; these are signal values, not execution branches. Connected nodes lock structural changes to formulas, variable types/source modes and templates until **Disconnect all** is used.

### Invert

Logical NOT of a bit input. An unconnected input is 0, so its output is 1.

### FIFO

`now` holds the current input sample; `last` holds the preceding update's sample. On the first update, `last` is the configured initial value. The connected source determines the input/output types; an unconnected FIFO has a selectable fallback type.

Sampling happens once every update, even when the value is unchanged. This is two-sample history, not a push/pop queue. FIFO does not permit graph feedback cycles because `now` depends on the current input.

### Timer / timeout

Add **+ Timer** and connect `trigger` and `reset` (both bit); `out` is bit. **Duration ms** is a nonnegative integer in 1 ms steps, default 1000, and can reference a Const. A rising trigger edge starts the timer, including an initially high trigger on the first update. Dropping trigger does not cancel the timer; triggers while busy are ignored. The duration is sampled at the starting edge, so changing a referenced parameter only affects the next run. Counting starts at that edge; subsequent update periods advance the timer. Zero expires immediately.

**Output mode** `level` holds `out=1` after expiry until reset, ignoring further starts while latched. `pulse` gives `out=1` for one update at expiry, then returns to 0 and can start again on a new rising edge. Reset is level-sensitive and takes priority: while HIGH it cancels counting and clears the output. A trigger held HIGH through reset does not restart on reset release; trigger must fall and rise again. Reset on the expiry update suppresses the output. Unconnected inputs are 0. Simulation uses 20 ms steps; deployed timing follows the HAL update period. Invalid/nonpositive periods clear timer state.

For timeout detection, connect a start signal to trigger and successful completion to reset; use level output for a latched fault or pulse output for a single notification. [timeout.json](../examples/timeout.json) demonstrates a 1000 ms timer, a timeout HAL output and a Display message. Starting/stopping simulation clears history.

### PID

Inputs: `setpoint`, `feedback`, `enable`, `reset`. Float outputs: `out` and `error`. While active, `error = setpoint − feedback`.

Kp controls the proportional term, Ki the time-integrated term, and Kd the derivative. Derivative acts on changes in measured feedback, avoiding a setpoint derivative kick; **D filter ms** filters it. **Output min/max** limits the result, and anti-windup limits outward integral growth.

Optional feedforward adds `FF gain × setpoint`. Disabled or reset controllers output zero on both outputs and clear history. Unconnected setpoint, feedback and enable use property defaults; reset defaults to 0.

### Display

Inputs: `trigger`, `value`, `reset`. Entering the configured active trigger level prints one message. **Append value** adds the numeric value. Activations during cooldown are dropped, not queued; a held active trigger does not repeat.

A rising reset edge overrides cooldown and rearms the message; holding reset high does not repeatedly print. Simulation shows messages in the status line. Export uses an RTAPI error message and does not issue an NC abort command.

## 6. Expressions and parameter references

Supported operations:

```text
+  -  *  /  %  ^  **  <<  >>
==  !=  <  <=  >  >=
and  or  not
```

`^` and `**` mean exponentiation, not XOR. `%` follows the divisor's sign; division/modulo by a near-zero divisor returns zero. Built-in `pi` and `e` do not create ports.

`<<` and `>>` are logical 32-bit zero-fill shifts. `1 << 3` is 8; `128 >> 3` is 16. The left operand is truncated towards zero and reduced to its low 32 bits; negative values use their two's-complement bit pattern. Shifted-out bits are discarded and right shift does not extend the sign. Counts must be integers from 0 to 31; invalid counts or nonfinite operands return zero. Normal result-type conversion follows. Addition binds before shifts, so parenthesize shifted terms.

Functions: `abs`, `min`, `max`, `clamp`, `pow`, `sqrt`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `log`, `log10`, `exp`, `floor`, `ceil`. Angles use radians; min/max take two arguments and clamp takes three. Invalid function domains or nonfinite function results return zero. Arbitrary Python code is not executed.

```text
(n0 << 0) + (n1 << 1) + (n2 << 2) + (n3 << 3)
clamp(x * @gain, 0, @maximum)
abs(actual - requested) < tolerance
sin(angle * pi / 180)
```

`@name` requires an existing Const and creates no expression socket. Numeric parameters, initial values and PID default enable can use references. Values convert to the receiving type; time references round to whole milliseconds. Export samples initial-state references on the first update. Duplicate, reserved or unknown names are rejected.

## 7. Math templates

Save/load templates in the Math properties panel or choose one from the dropdown. A template stores the formula, result type, variable source/type/value and its name, without wires. Its name appears in the node heading.

The `templates/` directory includes AND2, OR2 and four/eight-bit U32 packing. Save custom templates there to populate the dropdown when the panel next rebuilds. Disconnect all incoming and outgoing connections before loading a template or changing a connected Math/Condition/FIFO node's structure. A template's referenced Const nodes must already exist in the destination project.

## 8. Simulation and debugging

**Simulate** resets history and starts 20 ms model steps; **Stop** stops and restores properties. The Qt timer is not a realtime scheduler. The monitor shows every module, with one row per input, constant, output or internal signal. Inputs and constants can be edited live; tooltips show full names, types and modules. A processed input differing from its raw value is shown separately. Edit the referenced Const when an input default is controlled by it.

Live input/constant changes preserve history. Structural and other configuration edits may reset it. Module and language changes only alter the view. Simulation never drives hardware.

## 9. Export, compilation and HAL integration

1. Save the JSON project.
2. Export `.comp` with a lowercase filename containing only letters, digits and underscores, starting with a letter, such as `machine_plc.comp`.
3. **Build .so** re-exports the current graph to the last export path and runs `halcompile --compile`.
4. The result is `.so`, with compiler output in `.build.txt`. LinuxCNC development tools are required for compilation.

Build for the target architecture: an x86 module cannot be loaded on an ARM64 Pi. The editor does not install/load the module or connect hardware. The component exports one `update` function containing all modules and Const input pins. Schedule it in the existing servo thread after hardware reads and before hardware writes.

For an already installed component and existing thread, for illustration:

```hal
loadrt machine_plc
addf machine-plc.update servo-thread
setp machine-plc.gain 2.5
```

Use your export's actual names and connect its pins appropriately. Input nodes read external HAL pins; Const pins start at their defaults and may be changed through `setp` or a signal.

## 10. Practical examples

### Four bits to U32

Create four bit Inputs, load the four-bit template into Math and connect n0…n3. For a custom formula, set each variable to bit and the result to u32:

```text
n0 + n1 * 2 + n2 * 4 + n3 * 8
```

With n0=1, n1=0, n2=1, n3=0, the result is 5.

### FIFO difference

Connect a float input to FIFO, then its `now` and `last` outputs to Math `now - last`. Divide by the actual sample period if you need a rate.

### Adjustable gain

Const `gain`, float, default 2; Input `reading`, float; Math `x * @gain`; Output `scaled`, float. Connect reading to x and Math to scaled. Reading=4 gives 8; changing gain to 3 gives 12 without rewiring.

### Organize machine logic

Create Inputs, Lubrication and Spindle modules; move nodes and wire across them in All modules. The monitor covers all modules and export remains one component. `examples/circular-direction.json` selects direction only; a complete toolchanger also needs sequencing, latching, sensors, delays and fault handling.

## 11. Troubleshooting

| Symptom | Check |
| --- | --- |
| No expression input socket | Source must be Input port; Constant and @references have no sockets. |
| Formula/type/template disabled | Disconnect all wires first. |
| Red type label | Check the automatic source-to-input conversion. |
| Missing node/wire | Select All modules, use Fit and inspect socket tooltips. |
| Const cannot be deleted / unknown reference | Remove uses first / check that the exact name exists. |
| Inaccurate simulation delay | Simulation steps are 20 ms; HAL uses its own update period. |
| Startup file fails | Use `--no-restore`, then open a valid project. |
| Build fails | Read `.build.txt`; check halcompile and file/pin names. |
| FIFO feedback rejected | Graph cycles are not supported. |
| Display does not stop NC | It emits an error message, not an abort command. |

OS/compiler diagnostics retain the external tool's language. Translation JSON files are in `locales/`; missing translations fall back to English.

## 12. LinuxCNC 2.9 / 2.10 compatibility

The current 2.10 development API writes outputs with `pin_set(value)` rather than `pin = value`. Export generates setters and conditional assignment fallbacks for older 2.9 halcompile versions. Current 2.10 accepts `bit`, `float`, `s32`, `u32` declarations but may warn about deprecated names.

After upgrading LinuxCNC, re-export and rebuild using that installation's halcompile. Reusing an old `.so` does not replace rebuilding. Checks cover installed 2.9 compilation and C checks with current 2.10 generator/HAL/RTAPI headers; they do not constitute an installed 2.10 runtime or hardware test.

## Logger: triggered history recording

Add **+ Logger**, choose 1–18 data inputs, and connect signals to `in1`, `in2`, etc. Each input automatically follows the source type (bit, float, s32 or u32). The connected module, symbol and output name are recorded too. Unconnected data inputs record zero as float. Connect a bit signal to `trigger`: its rising edge saves the current ringbuffer, oldest sample first. A held HIGH saves once; return LOW before triggering again. Saving does not clear the history.

Set **Sample interval ms** to a positive whole millisecond value and **Ringbuffer length** to 1–100000 samples. The interval can use an `@constant`. At most one sample is taken per update, so the actual update period limits the resolution (the editor uses 20 ms). A save between sample ticks records the existing history; before the first sample CSV/TSV contains only a header and JSONL is empty.

Choose CSV, TSV or JSONL. CSV/TSV headers contain input, symbol and type; JSONL includes them in each row. All formats include elapsed `time_ms`. **Number format** supports `.0g`–`.17g`, `.0f`–`.17f` and `.0e`–`.17e`; integer signals retain their exact value. **Output file** accepts `{timestamp}` (UTC), `{sequence}` and `{node}`, for example `logs/position-{timestamp}.csv`. A fixed filename replaces the previous file atomically. The chosen file format determines the contents independently of the extension.

In simulation, relative paths use the saved project directory, or the editor directory for an unsaved project. In LinuxCNC they use the export directory. Export creates `.comp`, `.logger.py`, `.logger.json` and `.hal`. Keep the generated files together, install the component normally with `halcompile`, then source the generated `.hal` after `servo-thread` exists. It automatically loads the component, starts the collector with the system Python/LinuxCNC `hal` module, and adds the update function. Replace the previous `loadrt`/`addf` lines for this component to avoid loading it twice. Re-export after relocating the bundle, because the setup contains absolute helper paths.

The realtime thread only sends bounded HAL stream records; the collector holds history and writes snapshots outside realtime. Keep the collector running while sampling. Transport overruns and a save requested while another save is pending are reported and may drop samples or save requests. Simulation reports completed writes and errors in the status line; LinuxCNC reports them on the collector’s stderr. Large buffers increase memory use and file size. `examples/logger-history.json` demonstrates a trigger and typed inputs.

Connections can be selected by clicking near their line, including when zoomed out. Selected wires turn yellow. Delete removes selected wires without deleting their nodes; Ctrl-click allows multiple selections.

## Global I/O, LinuxCNC bindings and Live HAL debugging

Use **Global I/O** to add/remove project-wide inputs and outputs. They appear in shared Input/Output blocks in every existing and new module, with one definition and one exported pin per signal. Move the blocks by their frame/header; positions are remembered separately for each module. Double-click an entry in the management window to edit its properties. Ordinary Input/Output nodes can also become global with **Global (all modules)**. Removal deletes the signal and its connections throughout the project. A global output accepts one graph driver: disconnect it before assigning another. Its source-module label and **Go to driver** jump to, select and center the source node.

Every Input/Output supports **Select HAL pin / signal**. In the separate chooser, **Refresh** reads `halcmd -s show pin` and `halcmd -s show sig` asynchronously. Search by pin/component name and filter by kind, type, direction or compatibility. The table shows the value, existing HAL signal and project driver; the details show other pins on that signal. **Load catalogue** / **Save catalogue** allow offline design; `examples/hal-catalogue.json` is a sample, not a real machine mapping. Selecting a target copies its type. **Clear HAL binding** keeps the node as a manually connectable component pin. Project output bindings must target an IN pin or a signal without an existing writer. Type and writer conflicts are rejected. Existing nets are reused; connected pins are never reassigned to a different signal by export.

Export writes `name.comp`, `name.hal`, `name.unload.hal`, `name.test.hal`, `name.test.unload.hal` and `name.hal.json`, plus Logger helpers when applicable. `name.hal` is the complete project setup: load component, wire I/O, apply constant defaults, start Logger and add update to `servo-thread`. Use it after hardware/GUI pins and the thread exist, including as a postgui file. It integrates with the machine HAL; it does not generate the motion/hardware configuration. The test file wires only inputs. Unload files are for successful matching loads; a manually failed partial load needs its actual state inspected. The editor's live worker automatically rolls back completed setup steps.

**Debug build** exports typed intermediate pins such as `name.debug-n12-result`, FIFO `last`/`now` and PID `out`/`error`. Node IDs keep names stable across module renames. The manifest stores the node-to-pin map and build fingerprint. Normal builds omit these pins. Changing the checkbox takes effect on the next Export/Build.

Choose **Live HAL test** beside Simulate and press Simulate. The editor always builds a debug component for this mode, installs it with `halcompile --install`, then loads an isolated `nne_live_<uid>` component. It requires running LinuxCNC/HAL, `servo-thread`, the Python `hal` module and the development toolchain. Installation needs write permission; the worker can use an already-authorized noninteractive `sudo -n` installation, and otherwise asks for the sudo password in a hidden input dialog. The password is not saved or logged. If permission fails, the status shows the installation error. Local simulation continues to work without LinuxCNC.

Only external inputs are wired in Live HAL test; project output destinations stay disconnected. The compiled component does the calculation in realtime. The editor reads debug pins via Python HAL at about 20 Hz, without running the Python simulation alongside it. Bound inputs are read-only; unbound numeric/bit inputs can be adjusted. Structural edits are locked until Stop. Current graph inputs and outputs, FIFO history and PID error come from the actual component. Short pulses can occur between display refreshes; the display is not a capture instrument. Logger remains the sample-history tool.

The status displays measured component execution time and maximum in µs, plus the original LinuxCNC `.update.time` value. Native `.time`/`.tmax` use backend-dependent clock units, so debug code also measures nanoseconds with `rtapi_get_time()`; the µs figure measures the instrumented update body, not the GUI period or the full servo thread. Stop/exit unloads the test component and rolls back its connections; pre-existing signals remain. A debug fingerprint check waits for a real RT update, catching a stopped/wrong thread. Only one Live HAL test per Unix user can run. The installed private test module is reused on subsequent tests; the temporary source bundle is removed. Live values do not overwrite saved simulated defaults. `examples/global-io.json` demonstrates the shared nodes and a sample binding.

Manual deployment remains available:

```bash
sudo halcompile --install name.comp
halcmd -f name.hal
```

For an input-only manual test use `name.test.hal` from a debug export instead. Stop the matching setup before reloading; installing a new file does not replace a loaded module. On RIP installations use the configured build environment and its installation permissions.

A direct Input → Output wire between two external HAL bindings of the same type is exported as HAL net wiring, without component pins for unused endpoints. Inversion, edge detection, debounce, delays, conversion, intermediate nodes or an unbound component endpoint retain component processing. An input also feeding internal logic retains its component pin. Distinct existing HAL signals are not merged; those connections retain component processing. A project consisting only of direct wires needs no loadrt/addf. Debug keeps observation pins; input-only Live testing never connects external output targets.

Live HAL writes timestamps, build/install output, HAL commands and errors to `.state/logs/live-hal.log` in the editor directory (or `PLC_STATE_DIR/logs/live-hal.log`). The status shows this path on failure. Rotation keeps the current file and three backups, up to 1 MiB each. Passwords and authorization replies are not logged. Builds run from the temporary source directory to avoid privileged access failures on SSHFS.

## Counter

Add it with **+ Counter**. Inputs `up`, `down`, `enable`, `reset` are `bit`; outputs are `count` (`s32`) and `reached` (`bit`). Each sampled rising edge on `up` adds 1; on `down` it subtracts 1. Simultaneous rising edges cancel. A HIGH input on the first update counts as an edge.

Set **Initial value**, **Threshold** and **Default enable** in Properties; numeric values can refer to named constants. Unconnected `up`, `down`, `reset` are LOW; unconnected `enable` uses Default enable (initially on). Reset HIGH restores the initial value every update, even while disabled. Disable holds the count. Both reset and disable consume incoming edges: a held HIGH does not count when they are released.

`count` saturates at −2147483648 / 2147483647; it never wraps. `reached = count >= threshold` is evaluated every update, including reset/disable, and is not latched. The initial value is read at startup and reset; the threshold is read every update. Restarting simulation or reloading the component clears its history.

Open [counter.json](../examples/counter.json), start local simulation, and toggle `pulse-up` off/on three times: `count-value` reaches 3 and `threshold-reached` turns on. A rising edge on `pulse-down` returns the count to 2 and clears the threshold output. `clear-count` resets to 0. The JSON project, simulator, `.comp` export and debug monitors support both output types. This node counts edges visible at the configured update period; fast physical pulses require a hardware counter/encoder.
