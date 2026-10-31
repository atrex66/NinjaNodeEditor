#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
sudo apt-get update
sudo apt-get -o DPkg::Lock::Timeout=120 install -y python3-pyside6.qtwidgets libqt6opengl6
/usr/bin/python3 - <<'PY'
import ctypes
from pathlib import Path
from PySide6.QtCore import QLibraryInfo, qVersion
from PySide6 import QtWidgets

plugins = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
ctypes.CDLL(str(plugins / 'egldeviceintegrations' / 'libqeglfs-kms-integration.so'))
print(f'System Qt {qVersion()}: PySide6 Widgets and EGLFS/KMS dependencies OK.')
PY
echo 'From the local Pi console, start with ./run-eglfs.sh'
