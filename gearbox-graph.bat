@echo off
setlocal EnableDelayedExpansion
rem gearbox-graph launcher (Windows): rebuild the graph from your vault and open it in your browser.
rem The first run asks for your vault folder and remembers it in .vault-path next to this file.
rem To point it at a different vault, delete .vault-path, or drag the vault folder onto this file.
cd /d "%~dp0"

rem Find Python 3.9+: the py launcher first, then python on PATH.
rem (The Microsoft Store "python" stub fails this check, which is what we want.)
py -3 -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1
if not errorlevel 1 (set "PY=py -3" & goto havepy)
python -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1
if not errorlevel 1 (set "PY=python" & goto havepy)
echo Python 3.9 or newer not found. Install it from python.org, then run this again.
pause
exit /b 1

:havepy
set "VAULT="
if not "%~1"=="" (
  set "VAULT=%~1"
) else if exist ".vault-path" (
  set /p VAULT=<".vault-path"
) else (
  echo Which Obsidian vault? Paste its folder path, for example C:\Users\you\Documents\MyVault
  set /p "VAULT=> "
)
if defined VAULT set "VAULT=!VAULT:"=!"
if not defined VAULT (
  echo No folder given.
  pause
  exit /b 1
)
if not exist "!VAULT!\" (
  echo Not a folder: !VAULT!
  pause
  exit /b 1
)
>".vault-path" echo(!VAULT!

%PY% gearbox_graph.py --vault "!VAULT!" --out gearbox-graph.html
if errorlevel 1 (
  echo Rebuild failed; not opening a stale graph.
  pause
  exit /b 1
)
start "" "%~dp0gearbox-graph.html"
