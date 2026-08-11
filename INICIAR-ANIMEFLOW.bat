@echo off
rem ===========================================================================
rem  AnimeFlow - Lanzador para Windows
rem
rem  Doble clic y listo: comprueba Python, genera los datos, levanta el
rem  servidor local y abre la web en el navegador.
rem
rem  Los textos van sin acentos a proposito, para que se vean bien en
rem  cualquier consola de Windows sea cual sea su pagina de codigos.
rem ===========================================================================
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title AnimeFlow - Lanzador
color 0D
cd /d "%~dp0"

set "RAIZ=%CD%"
set "WEB=%RAIZ%\frontend"
set "BACK=%RAIZ%\backend"
set "PUERTO="
set "PYEXE="
set "PYVER=?"
set "TITULO_SRV=AnimeFlow-Servidor"

cls
echo.
echo   ###########################################################
echo   #                                                         #
echo   #        A N I M E F L O W   -   L A N Z A D O R          #
echo   #                                                         #
echo   ###########################################################
echo.

rem ---------------------------------------------------------------------------
rem  1. Comprobar la estructura del proyecto
rem ---------------------------------------------------------------------------
echo   [1/4] Comprobando archivos del proyecto...

if not exist "%WEB%\index.html" (
    echo.
    echo   [ERROR] No se encuentra  frontend\index.html
    echo.
    echo   Este archivo .bat debe estar DENTRO de la carpeta animeflow,
    echo   al lado de las carpetas  frontend,  backend  y  db.
    echo.
    echo   Carpeta actual: %RAIZ%
    echo.
    pause
    exit /b 1
)
echo         OK - frontend\index.html encontrado

rem ---------------------------------------------------------------------------
rem  2. Detectar Python
rem ---------------------------------------------------------------------------
echo   [2/4] Buscando Python...

for /f "delims=" %%i in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%i"
if not defined PYEXE (
    for /f "delims=" %%i in ('python -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%i"
)
if not defined PYEXE (
    for /f "delims=" %%i in ('python3 -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%i"
)

if not defined PYEXE (
    echo.
    echo   [ERROR] No se ha encontrado Python en este equipo.
    echo.
    echo   AnimeFlow lo necesita para levantar el servidor local
    echo   y para el pipeline de sincronizacion.
    echo.
    echo   Descargalo en:  https://www.python.org/downloads/
    echo   IMPORTANTE: marca "Add Python to PATH" durante la instalacion.
    echo.
    set "ABRIR="
    set /p "ABRIR=  Abrir la pagina de descarga ahora? (S/N): "
    if /i "!ABRIR!"=="S" start "" "https://www.python.org/downloads/"
    echo.
    pause
    exit /b 1
)

for /f "usebackq delims=" %%v in (`"%PYEXE%" -c "import sys;print(sys.version.split()[0])"`) do set "PYVER=%%v"
echo         OK - Python %PYVER%

rem ---------------------------------------------------------------------------
rem  3. Datos de demostracion
rem ---------------------------------------------------------------------------
echo   [3/4] Comprobando datos...

if exist "%WEB%\mock-data.json" (
    echo         OK - mock-data.json listo
) else (
    if exist "%BACK%\generar_mock.py" (
        echo         Generando mock-data.json por primera vez...
        pushd "%BACK%"
        "%PYEXE%" generar_mock.py
        popd
    ) else (
        echo         [AVISO] Falta mock-data.json y tambien generar_mock.py
        echo                 La web abrira vacia hasta que conectes Supabase.
    )
)

rem ---------------------------------------------------------------------------
rem  4. Puerto libre + arranque del servidor
rem ---------------------------------------------------------------------------
echo   [4/4] Arrancando el servidor local...

call :BUSCAR_PUERTO
call :ARRANCAR_SERVIDOR
call :ESPERAR_SERVIDOR

start "" "http://localhost:%PUERTO%/index.html"

echo         OK - Servidor activo en http://localhost:%PUERTO%
echo.
echo   ===========================================================
echo     La web se ha abierto en tu navegador.
echo     Deja ESTA ventana abierta mientras la uses.
echo   ===========================================================
echo.
timeout /t 3 >nul 2>&1

rem ===========================================================================
rem  MENU PRINCIPAL
rem ===========================================================================
:MENU
call :ESTADO_SUPABASE
cls
echo.
echo   ###########################################################
echo   #                  A N I M E F L O W                      #
echo   ###########################################################
echo.
echo     Servidor : http://localhost:%PUERTO%/index.html   [ACTIVO]
echo     Datos    : %AFESTADO%
echo     Carpeta  : %RAIZ%
echo.
echo   -----------------------------------------------------------
echo     WEB
echo        1.  Abrir la web en el navegador
echo        2.  Reiniciar el servidor local
echo.
echo     SUPABASE  (para usar datos reales)
echo        3.  Instalar dependencias de Python  (pip install)
echo        4.  Configurar credenciales del backend  (.env)
echo        5.  Conectar el frontend  (URL + clave anon)
echo        6.  Carga inicial de datos desde Jikan  (init)
echo        7.  Actualizar "Capitulos de hoy"  (sync-today)
echo        8.  Anadir un anime buscando por titulo
echo.
echo     UTILIDADES
echo        9.  Regenerar datos de demostracion
echo       10.  Volver al modo demostracion
echo       11.  Abrir la carpeta del proyecto
echo.
echo        0.  Detener el servidor y salir
echo   -----------------------------------------------------------
echo.
set "OP="
set /p "OP=  Elige una opcion y pulsa Enter: "

if "%OP%"=="1"  goto OP_ABRIR
if "%OP%"=="2"  goto OP_REINICIAR
if "%OP%"=="3"  goto OP_PIP
if "%OP%"=="4"  goto OP_ENV
if "%OP%"=="5"  goto OP_CONECTAR
if "%OP%"=="6"  goto OP_INIT
if "%OP%"=="7"  goto OP_HOY
if "%OP%"=="8"  goto OP_BUSCAR
if "%OP%"=="9"  goto OP_MOCK
if "%OP%"=="10" goto OP_DEMO
if "%OP%"=="11" goto OP_CARPETA
if "%OP%"=="0"  goto SALIR
goto MENU


:OP_ABRIR
start "" "http://localhost:%PUERTO%/index.html"
goto MENU


:OP_REINICIAR
cls
echo.
echo   Reiniciando el servidor...
call :PARAR_SERVIDOR
call :BUSCAR_PUERTO
call :ARRANCAR_SERVIDOR
call :ESPERAR_SERVIDOR
echo   Servidor activo en http://localhost:%PUERTO%
timeout /t 3 >nul 2>&1
goto MENU


:OP_PIP
cls
echo.
echo   ===  Instalando dependencias de Python  ===
echo.
if not exist "%BACK%\requirements.txt" (
    echo   [ERROR] No se encuentra  backend\requirements.txt
    echo.
    pause
    goto MENU
)
pushd "%BACK%"
"%PYEXE%" -m pip install --upgrade pip
"%PYEXE%" -m pip install -r requirements.txt
popd
echo.
echo   Listo. Ya puedes usar las opciones 6, 7 y 8.
echo.
pause
goto MENU


:OP_ENV
cls
echo.
echo   ===  Credenciales del backend  (.env)  ===
echo.
if not exist "%BACK%\.env" (
    if exist "%BACK%\.env.example" (
        copy /y "%BACK%\.env.example" "%BACK%\.env" >nul
        echo   Creado  backend\.env  a partir de la plantilla.
        echo.
    ) else (
        echo   [ERROR] No se encuentra  backend\.env.example
        echo.
        pause
        goto MENU
    )
)
echo   Se abrira el archivo en el Bloc de notas. Rellena estas dos lineas
echo   con los datos de tu proyecto  (Supabase ^> Project Settings ^> API):
echo.
echo       SUPABASE_URL=https://TU-PROYECTO.supabase.co
echo       SUPABASE_SERVICE_KEY=eyJhbGciOi...
echo.
echo   Aqui SI va la clave service_role: es el backend, no el navegador.
echo   Guarda con Ctrl+S y cierra el Bloc de notas para volver al menu.
echo.
pause
notepad "%BACK%\.env"
goto MENU


:OP_CONECTAR
cls
echo.
echo   ===  Conectar el frontend con Supabase  ===
echo.
echo   Necesitas dos datos de:  Supabase ^> Project Settings ^> API
echo.
echo     1^) Project URL       ejemplo: https://abcdefgh.supabase.co
echo     2^) Clave anon public empieza por eyJ...   ^(NO la service_role^)
echo.
set "SB_URL="
set "SB_KEY="
set /p "SB_URL=  Project URL       : "
set /p "SB_KEY=  Clave anon public : "
echo.
if "%SB_URL%"=="" (
    echo   Cancelado: no se ha introducido ninguna URL.
    echo.
    pause
    goto MENU
)
pushd "%BACK%"
"%PYEXE%" configurar_frontend.py "%SB_URL%" "%SB_KEY%"
popd
echo.
echo   Recarga la web con Ctrl+F5 para ver el cambio.
echo.
pause
goto MENU


:OP_INIT
cls
echo.
echo   ===  Carga inicial desde Jikan API v4  ===
echo.
echo   Descarga la temporada actual, el top en emision y la agenda de
echo   hoy, y lo guarda en tu proyecto de Supabase.
echo.
echo   Tarda entre 2 y 4 minutos por el limite de peticiones de Jikan.
echo   Requisitos: haber hecho antes las opciones 3 y 4.
echo.
set "SEGUIR="
set /p "SEGUIR=  Continuar? (S/N): "
if /i not "%SEGUIR%"=="S" goto MENU
echo.
pushd "%BACK%"
"%PYEXE%" sync_anime_supabase.py init
popd
echo.
pause
goto MENU


:OP_HOY
cls
echo.
echo   ===  Actualizando "Capitulos de hoy"  ===
echo.
pushd "%BACK%"
"%PYEXE%" sync_anime_supabase.py sync-today
popd
echo.
pause
goto MENU


:OP_BUSCAR
cls
echo.
echo   ===  Anadir un anime buscando por titulo  ===
echo.
set "TIT="
set /p "TIT=  Titulo a buscar: "
if "%TIT%"=="" goto MENU
echo.
pushd "%BACK%"
"%PYEXE%" sync_anime_supabase.py sync-title "%TIT%" --limite 3 --episodios
popd
echo.
pause
goto MENU


:OP_MOCK
cls
echo.
echo   ===  Regenerando datos de demostracion  ===
echo.
pushd "%BACK%"
"%PYEXE%" generar_mock.py
popd
echo.
pause
goto MENU


:OP_DEMO
cls
echo.
echo   ===  Volver al modo demostracion  ===
echo.
echo   Se borraran las credenciales de Supabase del index.html y la web
echo   volvera a leer mock-data.json. Se guarda una copia de seguridad.
echo.
set "SEGUIR="
set /p "SEGUIR=  Continuar? (S/N): "
if /i not "%SEGUIR%"=="S" goto MENU
pushd "%BACK%"
"%PYEXE%" configurar_frontend.py --limpiar
popd
echo.
pause
goto MENU


:OP_CARPETA
start "" explorer "%RAIZ%"
goto MENU


rem ===========================================================================
rem  SUBRUTINAS
rem ===========================================================================

rem --- Busca el primer puerto libre entre 8000 y 8020 ------------------------
rem     Se comprueba con findstr literal (no con el estado LISTENING) para no
rem     depender del idioma de Windows: en espanol netstat dice "ESCUCHANDO".
:BUSCAR_PUERTO
set "PUERTO="
for /L %%p in (8000,1,8020) do if not defined PUERTO call :PROBAR_PUERTO %%p
if not defined PUERTO set "PUERTO=8000"
exit /b 0

:PROBAR_PUERTO
netstat -an | findstr /C:":%1 " >nul 2>&1
if errorlevel 1 set "PUERTO=%1"
exit /b 0

rem --- Arranca el servidor estatico en una ventana minimizada ----------------
:ARRANCAR_SERVIDOR
start "%TITULO_SRV%" /min "%PYEXE%" -m http.server %PUERTO% --directory "%WEB%"
exit /b 0

rem --- Espera a que el puerto responda (max. ~10 s) --------------------------
:ESPERAR_SERVIDOR
for /L %%t in (1,1,10) do (
    timeout /t 1 >nul 2>&1
    netstat -an | findstr /C:":%PUERTO% " >nul 2>&1
    if not errorlevel 1 exit /b 0
)
exit /b 0

rem --- Detiene el servidor: por titulo de ventana y, si no, por puerto -------
:PARAR_SERVIDOR
taskkill /FI "WINDOWTITLE eq %TITULO_SRV%*" /T /F >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-NetTCPConnection -LocalPort %PUERTO% -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1
exit /b 0

rem --- Lee de Python si el frontend apunta a Supabase o al modo demo ---------
:ESTADO_SUPABASE
set "AFESTADO=Modo demostracion (mock-data.json)"
if not exist "%BACK%\configurar_frontend.py" exit /b 0
"%PYEXE%" "%BACK%\configurar_frontend.py" --estado > "%TEMP%\af_estado.txt" 2>nul
if exist "%TEMP%\af_estado.txt" (
    set /p AFESTADO=<"%TEMP%\af_estado.txt"
    del "%TEMP%\af_estado.txt" >nul 2>&1
)
exit /b 0

rem ===========================================================================
:SALIR
cls
echo.
echo   Deteniendo el servidor...
call :PARAR_SERVIDOR
echo.
echo   Servidor detenido. Hasta la proxima.
echo.
timeout /t 2 >nul 2>&1
endlocal
exit /b 0
