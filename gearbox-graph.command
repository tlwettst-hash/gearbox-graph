#!/bin/bash
# gearbox-graph launcher (Mac): rebuild the graph from your vault and open it in your browser.
# The first run asks for your vault folder and remembers it in .vault-path next to this file.
# To point it at a different vault, delete .vault-path or run:  ./gearbox-graph.command /path/to/vault
cd "$(dirname "$0")" || exit 1

fail() { echo "$1"; read -n 1 -s -r -p "Press any key to close."; echo; exit 1; }

PY=$(command -v python3) || fail "Python 3 not found. Install it from python.org, then run this again."
"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null \
  || fail "Python 3.9 or newer is needed ($("$PY" --version 2>&1)). Install it from python.org."

if [ -n "$1" ]; then
  VAULT="$1"
elif [ -f .vault-path ]; then
  VAULT=$(head -n 1 .vault-path)
else
  echo "Which Obsidian vault? Drag its folder into this window, then press Return."
  read -r -p "> " VAULT
  VAULT="${VAULT%"${VAULT##*[![:space:]]}"}"   # trim trailing spaces left by drag-and-drop
  VAULT="${VAULT//\\ / }"                      # Terminal escapes spaces in dropped paths
  VAULT="${VAULT#\'}"; VAULT="${VAULT%\'}"     # ...or wraps them in quotes
fi
[ -d "$VAULT" ] || fail "Not a folder: $VAULT"
printf '%s\n' "$VAULT" > .vault-path

"$PY" gearbox_graph.py --vault "$VAULT" --out gearbox-graph.html || fail "Rebuild failed; not opening a stale graph."
open gearbox-graph.html
