# Validation — 2026-10-31

- All 130 Python tests passed on Linux amd64, with Qt offscreen.
- Includes processing nodes, counter, generated C/simulator equivalence,
  HAL exports, logger, session persistence and GUI tests.
- This publication did not perform a new physical Pi I/O or realtime test.

```sh
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -v
```

The editor itself requires Python and PySide6 (requirements.txt); it runs
without LinuxCNC. Compiling/loading generated HAL components additionally
requires a compatible HAL SDK/runtime.

The optional CPU-pinned launchers require the Automation HAL cpu_layout.py
helper and CPU configuration. Plain run.sh does not need those unless a CPU
configuration is selected or installed. The editor remains manual-start.

Original source hashes are in SOURCE-MANIFEST.json. A complete separate local
archive of the SD project, including artifacts, was verified before publication.
