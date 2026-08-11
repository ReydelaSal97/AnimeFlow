@echo off
rem ===========================================================================
rem  AnimeFlow - Actualizacion diaria de "Capitulos de hoy"
rem
rem  Pensado para el Programador de tareas de Windows:
rem    Crear tarea basica > Diariamente > 06:00 > Iniciar un programa
rem    Programa: la ruta completa a este .bat
rem
rem  Escribe el resultado en backend\sync.log
rem ===========================================================================
setlocal
chcp 65001 >nul 2>&1
title AnimeFlow - Sincronizacion diaria
cd /d "%~dp0"

set "BACK=%CD%\backend"
set "PYEXE="

for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%i"
if not defined PYEXE (
    for /f "delims=" %%i in ('python -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%i"
)

if not defined PYEXE (
    echo [ERROR] Python no encontrado. Instalalo desde python.org
    exit /b 1
)

if not exist "%BACK%\.env" (
    echo [ERROR] Falta backend\.env
    echo         Ejecuta INICIAR-ANIMEFLOW.bat y usa la opcion 4.
    exit /b 1
)

echo.
echo  Sincronizando emisiones del dia...
echo.

pushd "%BACK%"
"%PYEXE%" sync_anime_supabase.py sync-today
set "CODIGO=%ERRORLEVEL%"
popd

echo.
if "%CODIGO%"=="0" (
    echo  [OK] Sincronizacion completada.
) else (
    echo  [ERROR] La sincronizacion fallo con codigo %CODIGO%.
    echo          Revisa backend\sync.log
)

rem Si se ejecuta desde el Programador de tareas no hay nadie mirando:
rem la pausa solo aparece si lo lanzas tu con doble clic.
if "%1"=="" timeout /t 8 >nul 2>&1

endlocal & exit /b %CODIGO%
