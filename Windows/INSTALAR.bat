@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 goto sem_python
py -3 -m venv .venv
if errorlevel 1 goto falha
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto falha
echo Instalacao concluida. Abra INICIAR.bat.
pause
exit /b 0
:sem_python
echo Instale o Python 3.11 ou superior de https://www.python.org/downloads/windows/
echo Habilite o Python Launcher e mantenha Tcl/Tk na instalacao.
pause
exit /b 1
:falha
echo A instalacao falhou. Confira o erro acima e a conexao com a internet.
pause
exit /b 1
