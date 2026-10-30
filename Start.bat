@echo off
chcp 65001 >nul
title CardioPath AI
cd /d "%~dp0"

set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%USERPROFILE%\.venvs\cardiopath-ai\Scripts\python.exe" set "PY=%USERPROFILE%\.venvs\cardiopath-ai\Scripts\python.exe"

if not defined PY (
  echo.
  echo  Python muhiti topilmadi / Python environment not found / Среда Python не найдена.
  echo.
  echo  Bir marta o'rnating / Install once / Установите один раз:
  echo    python -m venv "%USERPROFILE%\.venvs\cardiopath-ai"
  echo    "%USERPROFILE%\.venvs\cardiopath-ai\Scripts\pip" install -r requirements.txt
  echo.
  pause
  exit /b 1
)

if not exist "%~dp0data" mkdir "%~dp0data"
set "CARDIOPATH_DB=%~dp0data\cardiopath.db"
set "CARDIOPATH_RECORDINGS=%~dp0data\recordings"
if not defined CARDIOPATH_PORT set "CARDIOPATH_PORT=8010"
rem Kirish (login) o'chiq. Yoqish: CARDIOPATH_AUTH=on (avval: python -m core.auth_cli create-user --role admin ...)
if not defined CARDIOPATH_AUTH set "CARDIOPATH_AUTH=off"

if not exist "%~dp0weights\pcg\model_card.json" (
  echo  Eslatma: AI modeli topilmadi, faqat klinik qoidalar ishlaydi.
  echo  Note: AI model not found, only clinical rules will run.
  echo.
)

echo  CardioPath AI ishga tushmoqda... / Starting... / Запуск...
echo  Brauzer o'zi ochiladi. Bu oynani yopmang; to'xtatish uchun Ctrl+C.
echo  The browser opens by itself. Keep this window open; press Ctrl+C to stop.
echo.
start "" /b cmd /c "ping -n 4 127.0.0.1 >nul & start "" http://localhost:%CARDIOPATH_PORT%"
"%PY%" -m uvicorn api.main:default_app --factory --host 127.0.0.1 --port %CARDIOPATH_PORT%
echo.
echo  Dastur to'xtadi. / Stopped. / Остановлено.
pause
