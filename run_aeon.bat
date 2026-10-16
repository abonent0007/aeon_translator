@echo off
chcp 65001 >nul 2>&1
title LOGOS Semantic Analysis
setlocal

REM ════════════════════════════════════════════════════════════════
REM  LOGOS Semantic Analysis — launcher + non-interactive CLI
REM  БЕЗ аргументов  → интерактивное меню (для людей).
REM  С аргументами    → CLI-режим для агентов/скриптов (без pause,
REM                     exit code = exit code python-модуля).
REM    run_aeon.bat help
REM    run_aeon.bat demo --text FILE --language=grc [--verify=full] [--real]
REM    run_aeon.bat export --aeon FILE --format tei --out DIR
REM    run_aeon.bat crossrefs --a FILE --b FILE [--real]
REM    run_aeon.bat gold --dataset gold/annotations/ --mode mock
REM    run_aeon.bat test  [-k EXPR]
REM    run_aeon.bat web | cli
REM ════════════════════════════════════════════════════════════════

if not "%~1"=="" goto cli

REM ── Интерактивное меню (человек) ──
cls
echo.
echo ============================================================
echo           LOGOS Semantic Analysis
echo ============================================================
echo.
echo   "Meaning is one. Only the forms differ."
echo.
echo   Breaking barriers between:
echo   - Languages (ru, en, zh, ... 50+)
echo   - Forms (text, code, emotions, voice, images)
echo   - Minds (human, machine)
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.8+
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python found
echo.

REM Check/install dependencies
pip show colorama >nul 2>&1
if %errorlevel% neq 0 (
    echo [INSTALL] Installing dependencies...
    pip install -r requirements.txt
    echo.
)

echo Select mode:
echo   1. Demo (интерактивное меню)
echo   2. Interactive (CLI)
echo   3. Quick translate (EN-RU)
echo   4. Bridge minds
echo   5. Help / агент-CLI
echo.

set /p choice="Your choice (1-5): "

if "%choice%"=="1" (
    echo.
    echo Launching demo...
    python -m aeon.demo
) else if "%choice%"=="2" (
    echo.
    echo Launching interactive mode...
    python -m aeon.cli
) else if "%choice%"=="3" (
    echo.
    set /p text="Enter text to translate: "
    python -c "import sys; sys.path.insert(0,'.'); from aeon import AeonTranslator; t=AeonTranslator(); r=t.translate('%text%', source_language='auto', target_language='english'); print('->', r['target']['content'][:300])"
) else if "%choice%"=="4" (
    echo.
    set /p text_a="Thought A: "
    set /p text_b="Thought B: "
    python -c "import sys; sys.path.insert(0,'.'); from aeon import AeonTranslator; t=AeonTranslator(); r=t.bridge_minds({'content':'%text_a%','language':'auto'},{'content':'%text_b%','language':'auto'}); print('Sim:', r.get('similarity',0)); print('Connected:', r['minds_connected']); print(r['message'])"
) else if "%choice%"=="5" (
    call :help_text
) else (
    echo Invalid choice. Launching interactive mode...
    python -m aeon.cli
)

pause
exit /b 0

REM ══════════════════════ CLI MODE (agents) ══════════════════════
:cli
set "CMD=%~1"
shift
set "ARGS="
:collect
if "%~1"=="" goto dispatch
set "ARGS=%ARGS% %1"
shift
goto collect

:dispatch
if /i "%CMD%"=="demo"      goto cmd_demo
if /i "%CMD%"=="analyze"   goto cmd_demo
if /i "%CMD%"=="export"    goto cmd_export
if /i "%CMD%"=="crossrefs" goto cmd_crossrefs
if /i "%CMD%"=="gold"      goto cmd_gold
if /i "%CMD%"=="test"      goto cmd_test
if /i "%CMD%"=="web"       goto cmd_web
if /i "%CMD%"=="cli"       goto cmd_cli
if /i "%CMD%"=="help"      goto help_cli
if /i "%CMD%"=="-h"        goto help_cli
if /i "%CMD%"=="--help"    goto help_cli
echo [ERROR] Unknown command: "%CMD%" (see: run_aeon.bat help) 1>&2
exit /b 2

:cmd_demo
python -m aeon.demo %ARGS%
exit /b %errorlevel%

:cmd_export
python -m aeon.export %ARGS%
exit /b %errorlevel%

:cmd_crossrefs
python -m aeon.crossrefs.demo %ARGS%
exit /b %errorlevel%

:cmd_gold
python -m aeon.gold.report %ARGS%
exit /b %errorlevel%

:cmd_test
python -m pytest -q %ARGS%
exit /b %errorlevel%

:cmd_web
echo [CLI] Web server: http://localhost:8080  (blocking; Ctrl+C to stop) 1>&2
python -m aeon.web_server
exit /b %errorlevel%

:cmd_cli
python -m aeon.cli
exit /b %errorlevel%

:help_cli
call :help_text
exit /b 0

:help_text
echo LOGOS Semantic Analysis — CLI (агенты/скрипты).
echo Без аргументов — интерактивное меню для человека.
echo.
echo   run_aeon.bat help
echo   run_aeon.bat demo --text FILE --language=grc [--verify=full] [--real] [--save-aeon OUT]
echo   run_aeon.bat export --aeon FILE --format tei^|md^|jsonld^|bib --out DIR
echo   run_aeon.bat crossrefs --a FILE --b FILE [--real] [--json-out OUT]
echo   run_aeon.bat gold --dataset gold/annotations/ --mode mock
echo   run_aeon.bat test [-k EXPR]
echo   run_aeon.bat web          ^(блокирующий web-сервер^)
echo   run_aeon.bat cli          ^(интерактивный REPL^)
echo.
echo Требования: рабочая директория = корень репозитория; Python 3.11.
echo Реальный LLM: --real ^(нужен DEEPSEEK_API_KEY в .env^).
echo Exit codes: 0 = OK, 2 = unknown command, иначе — код python-модуля.
exit /b 0
