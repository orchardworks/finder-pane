#!/bin/bash
# finder-pane: Finder-like file browser for cmux
DIR="$(cd "$(dirname "$0")" && pwd)"
if [ $# -eq 0 ]; then
  exec python3 "$DIR/cli.py" start
else
  exec python3 "$DIR/cli.py" "$@"
fi
