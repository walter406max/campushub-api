@echo off
REM Run ONCE while you still have internet. Downloads every Python package into .\wheels
if not exist wheels mkdir wheels
pip download -r requirements-offline.txt -d wheels
echo.
echo Done. Offline install:  pip install --no-index --find-links wheels -r requirements-offline.txt
echo Also run once online:   ollama pull llama3.2
