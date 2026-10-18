@echo off
rem 打包成「單檔」exe（一個檔案，啟動時會先解壓到暫存區，約慢 2 秒）。
rem 暫存與輸出先放 %TEMP%，避免專案在 OneDrive 內被同步鎖檔，完成後再複製到 dist\。
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --onefile ^
  --workpath "%TEMP%\zbh-build" --distpath "%TEMP%\zbh-dist" ^
  --name AIXAI-zoom-breakout-helper ^
  --collect-submodules pyautogui --exclude-module numpy ^
  --icon assets\icon.ico --add-data "assets\icon.ico;assets" ^
  zoom_rooms.py
if not exist dist mkdir dist
copy /Y "%TEMP%\zbh-dist\AIXAI-zoom-breakout-helper.exe" "dist\" >nul
echo.
echo 完成：dist\AIXAI-zoom-breakout-helper.exe
pause
