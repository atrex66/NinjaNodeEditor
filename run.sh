#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ -n "${AUTOMATION_CPU_CONFIG:-}" || -f /etc/automation-hal/cpu-layout.json ]]; then
    source ./cpu-layout.sh
    exec "${PLC_PYTHON:-python3}" "$cpu_helper" --role ui \
        --config "${AUTOMATION_CPU_CONFIG:-/etc/automation-hal/cpu-layout.json}" \
        -- "${PLC_PYTHON:-python3}" app.py "$@"
fi
exec "${PLC_PYTHON:-python3}" app.py "$@"
