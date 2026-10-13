#!/usr/bin/env bash
# Run ONCE while you still have internet. Downloads every Python package into ./wheels
# so you can install later with no connection.
set -e
mkdir -p wheels
pip download -r requirements-offline.txt -d wheels
echo "Done. Offline install:  pip install --no-index --find-links wheels -r requirements-offline.txt"
echo "Also run once online:   ollama pull llama3.2"
