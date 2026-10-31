#!/usr/bin/env bash
# Sourced by launchers. One implementation is shared with Automation HAL.
cpu_helper="${AUTOMATION_CPU_HELPER:-/opt/automation-hal/libexec/cpu_layout.py}"
if [[ ! -f "$cpu_helper" && -z "${AUTOMATION_CPU_HELPER:-}" ]]; then
    cpu_helper="$PWD/../automation-hal/tools/cpu_layout.py"
fi
if [[ ! -f "$cpu_helper" ]]; then
    echo 'Automation HAL CPU helper is missing; set AUTOMATION_CPU_HELPER.' >&2
    exit 1
fi
