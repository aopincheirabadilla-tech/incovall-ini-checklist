@echo off
chcp 65001 > nul
title INCOVALL - Inspección Preventiva INI
color 1F

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   INCOVALL - Inspección Preventiva INI   ║
echo  ║          Formulario INCO-INI-VH-001      ║
echo  ╚══════════════════════════════════════════╝
echo.

:: Verificar Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python no está instalado o no está en el PATH.
    echo.
    echo  Por favor descargue e instale Python desde:
    echo  https://www.python.org/downloads/
    echo.
    echo  Asegúrese de marcar "Add Python to PATH" durante la instalación.
    echo.
    pause
    exit /b 1
)

echo  [1/2] Instalando dependencias...
pip install -r "%~dp0requirements.txt" --quiet --no-warn-script-location 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] No se pudieron instalar las dependencias.
    echo  Intente ejecutar manualmente: pip install flask reportlab
    pause
    exit /b 1
)

echo  [2/2] Iniciando servidor...
echo.
echo  ► Acceda desde su navegador en: http://localhost:5000
echo  ► Presione Ctrl+C en esta ventana para detener el servidor.
echo.

:: Abrir navegador tras 1.5 segundos
start "" cmd /c "timeout /t 2 /nobreak > nul && start http://localhost:5000"

:: Ejecutar la aplicación
python "%~dp0app.py"

echo.
echo  El servidor se ha detenido.
pause
