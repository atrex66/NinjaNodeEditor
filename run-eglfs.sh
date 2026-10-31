#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export PLC_PYTHON="${PLC_PYTHON:-/usr/bin/python3}"
if ! "$PLC_PYTHON" - <<'PY'
import ctypes
import sys
from pathlib import Path

try:
    from PySide6.QtCore import QLibraryInfo
    from PySide6 import QtWidgets
    plugins = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
    ctypes.CDLL(str(plugins / 'egldeviceintegrations' / 'libqeglfs-kms-integration.so'))
except (ImportError, OSError) as error:
    print(f'EGLFS/KMS dependency check failed: {error}', file=sys.stderr)
    sys.exit(1)
PY
then
    echo 'Run bash ./setup-dietpi.sh on the Pi to install matching system Qt/PySide6 packages.' >&2
    exit 1
fi
export QT_QPA_PLATFORM=eglfs
export QT_QPA_EGLFS_INTEGRATION="${QT_QPA_EGLFS_INTEGRATION:-eglfs_kms}"
if [[ -z "${QT_QPA_EGLFS_KMS_CONFIG:-}" ]]; then
    if [[ -d /sys/class/drm/card1-HDMI-A-1 ]]; then
        export QT_QPA_EGLFS_KMS_CONFIG="$PWD/eglfs-kms-card1.json"
    else
        export QT_QPA_EGLFS_KMS_CONFIG="$PWD/eglfs-kms.json"
    fi
fi
export QT_SCALE_FACTOR=1
exec ./run.sh --eglfs "$@"
