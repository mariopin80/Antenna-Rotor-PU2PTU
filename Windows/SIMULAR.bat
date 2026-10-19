@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto instalar
".venv\Scripts\python.exe" -c "import serial; import PIL; import geographiclib" >nul 2>&1
if errorlevel 1 goto instalar
".venv\Scripts\python.exe" rotor_pc.py --simular
if errorlevel 1 pause
exit /b
:instalar
echo Execute INSTALAR.bat para instalar ou atualizar as dependencias.
pause
exit /b 1
