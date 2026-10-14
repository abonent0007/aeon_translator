@echo off
chcp 65001 >nul 2>&1
title AEON v3.0 - Universal Translator
cls

echo.
echo ============================================================
echo           AEON v3.0 - Universal Meaning Translator
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
echo   1. Demo (demo.py)
echo   2. Interactive (CLI)
echo   3. Quick translate (EN-RU)
echo   4. Bridge minds
echo   5. Help
echo.

set /p choice="Your choice (1-5): "

if "%choice%"=="1" (
    echo.
    echo Launching demo...
    python aeon/demo.py
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
    echo.
    echo AEON v3.0 - Universal Meaning Translator
    echo.
    echo PYTHON API:
    echo   from aeon import AeonTranslator
    echo   t = AeonTranslator()
    echo   t.translate("text", source_language="russian", target_language="english")
    echo   t.bridge_minds({"content": "A"}, {"content": "B"})
    echo   t.text_to_image("prompt")
    echo   t.speak_translation("text", target_language="english")
    echo.
    echo CLI:
    echo   python -m aeon.cli
    echo.
    echo DEMO:
    echo   python aeon/demo.py
    echo.
) else (
    echo Invalid choice. Launching interactive mode...
    python -m aeon.cli
)

pause
