@echo off
rem 打包成 exe（資料夾版，誤報率較低、啟動較快）。輸出在 dist\AIXAI-zoom-breakout-helper\
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --onedir ^
  --name AIXAI-zoom-breakout-helper ^
  --collect-submodules pyautogui ^
  zoom_rooms.py
echo.
echo 完成：dist\AIXAI-zoom-breakout-helper\AIXAI-zoom-breakout-helper.exe
pause
