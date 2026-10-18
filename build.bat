@echo off
rem 打包成 exe（資料夾版，誤報率較低、啟動較快）。
rem 暫存與輸出先放 %TEMP%，避免專案在 OneDrive 內被同步鎖檔，完成後再複製到 dist\。
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --onedir ^
  --workpath "%TEMP%\zbh-build" --distpath "%TEMP%\zbh-dist" ^
  --name AIXAI-zoom-breakout-helper ^
  --collect-submodules pyautogui --exclude-module numpy ^
  --icon assets\icon.ico --add-data "assets\icon.ico;assets" ^
  zoom_rooms.py
xcopy /E /I /Y "%TEMP%\zbh-dist\AIXAI-zoom-breakout-helper" "dist\AIXAI-zoom-breakout-helper\" >nul
echo.
echo 完成：dist\AIXAI-zoom-breakout-helper\AIXAI-zoom-breakout-helper.exe
pause
