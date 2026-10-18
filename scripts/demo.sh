#!/usr/bin/env bash

set -euo pipefail

SPEED="${DEMO_SPEED:-1}"
SCAN_DIR="${DEMO_SCAN_DIR:-.}"

export COLUMNS=90

pause() { [ "$SPEED" = "0" ] || sleep "$(echo "$1 * $SPEED" | bc -l)"; }

type_out() {
  local cmd="$1"
  printf '\033[1;32m$\033[0m '
  if [ "$SPEED" = "0" ]; then
    printf '%s\n' "$cmd"
  else
    local i
    for ((i = 0; i < ${#cmd}; i++)); do
      printf '%s' "${cmd:$i:1}"
      sleep 0.025
    done
    printf '\n'
  fi
  eval "$cmd"
}

clear

type_out "signalpost plan --path $SCAN_DIR"
pause 6

printf '\n'
type_out "signalpost dashboards --preview host-basics"
pause 4

printf '\n'
type_out "signalpost deploy --dry-run --path $SCAN_DIR"
pause 5

printf '\n\033[1;36m  pip install signalpost\033[0m\n'
printf '\033[2m  github.com/KebanFiru/signalpost\033[0m\n\n'
pause 3
