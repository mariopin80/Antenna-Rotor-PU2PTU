@echo off
setlocal
cd /d "%~dp0"
where makensis >nul 2>nul
if errorlevel 1 (
  if exist "%ProgramFiles(x86)%\NSIS\makensis.exe" set "PATH=%ProgramFiles(x86)%\NSIS;%PATH%"
  if exist "%ProgramFiles%\NSIS\makensis.exe" set "PATH=%ProgramFiles%\NSIS;%PATH%"
)
where makensis >nul 2>nul
if errorlevel 1 (
  echo Instale NSIS 3.09 ou superior em https://nsis.sourceforge.io/Download
  pause
  exit /b 1
)
py -3 -m venv .venv-build
if errorlevel 1 goto erro
".venv-build\Scripts\python.exe" -m pip install "pynsist==2.8" "lief==0.17.6"
if errorlevel 1 goto erro
".venv-build\Scripts\python.exe" "Instalador\build_installer.py"
if errorlevel 1 goto erro
echo.
echo Instalador gerado na pasta acima de Rotor_PU2PTU_1.2.
pause
exit /b 0
:erro
echo.
echo Falha ao gerar o instalador. Confira a mensagem acima.
pause
exit /b 1
