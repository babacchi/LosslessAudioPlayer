#!/bin/bash
# Launch script for macOS & Linux

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

python3 main.py
