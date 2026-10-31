#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [[ -z "${AUTOMATION_CPU_CONFIG:-}" ]]; then
    if [[ -f /etc/automation-hal/cpu-layout.json ]]; then
        export AUTOMATION_CPU_CONFIG=/etc/automation-hal/cpu-layout.json
    elif [[ -f /opt/automation-hal/share/automation-hal/cpu-layout.json ]]; then
        export AUTOMATION_CPU_CONFIG=/opt/automation-hal/share/automation-hal/cpu-layout.json
    else
        export AUTOMATION_CPU_CONFIG="$PWD/../automation-hal/packaging/cpu-layout.json"
    fi
fi
if [[ "${1:-}" == --eglfs ]]; then
    shift
    exec ./run-eglfs.sh "$@"
fi
exec ./run.sh "$@"
