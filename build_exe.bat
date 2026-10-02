@echo off
rem Windows에서 실행: 단일 exe 빌드 → dist\sc2coop_timer.exe
uv sync --extra win || exit /b 1
uv run pyinstaller --noconfirm --noconsole --onefile --name sc2coop_timer ^
  --add-data "sc2coop_timer\builds;sc2coop_timer\builds" ^
  --hidden-import win32com.client --hidden-import pythoncom ^
  run.py
