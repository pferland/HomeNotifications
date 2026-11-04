#!/usr/bin/env bash
# Convenience runner script for HomeNotifications
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ -f "$DIR/.venv/bin/python" ]; then
    exec "$DIR/.venv/bin/python" "$DIR/main.py" "$@"
else
    exec python3 "$DIR/main.py" "$@"
fi
