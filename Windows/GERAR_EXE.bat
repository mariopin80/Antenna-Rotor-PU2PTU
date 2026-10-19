@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto instalar
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto falha
".venv\Scripts\python.exe" -m pip install "pyinstaller>=6,<7"
if errorlevel 1 goto falha
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name Rotor_PU2PTU --version-file "assets\version_info.txt" --icon "assets\rotor_icon.ico" --add-data "assets;assets" rotor_pc.py
if errorlevel 1 goto falha
echo Executavel criado em dist\Rotor_PU2PTU.exe
pause
exit /b 0
:instalar
echo Execute INSTALAR.bat primeiro.
pause
exit /b 1
:falha
echo Falha ao gerar o executavel. Confira o erro acima.
pause
exit /b 1
