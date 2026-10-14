"""
Установщик Aeon Universal Translator
"""
import os
import sys
from pathlib import Path

def setup_aeon():
    """Настройка окружения для Aeon"""
    
    print("=" * 60)
    print("🌌 AEON UNIVERSAL TRANSLATOR - УСТАНОВКА")
    print("=" * 60)
    
    # Проверяем Python
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print("❌ Требуется Python 3.8 или выше!")
        print(f"   У вас: Python {python_version.major}.{python_version.minor}")
        sys.exit(1)
    
    print(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    # Создаём необходимые директории
    dirs = ["aeon", "logs", "examples"]
    for d in dirs:
        Path(d).mkdir(exist_ok=True)
        print(f"✅ Директория: {d}/")
    
    # Проверяем зависимости
    print("\n📦 Проверка зависимостей...")
    try:
        import numpy
        print(f"✅ numpy {numpy.__version__}")
    except ImportError:
        print("⚠️ numpy не установлен. Установите: pip install numpy")
    
    try:
        import colorama
        print(f"✅ colorama {colorama.__version__}")
    except ImportError:
        print("⚠️ colorama не установлен. Установите: pip install colorama")
    
    try:
        import rich
        print(f"✅ rich {rich.__version__}")
    except ImportError:
        print("⚠️ rich не установлен. Установите: pip install rich")
    
    print("\n" + "=" * 60)
    print("✅ УСТАНОВКА ЗАВЕРШЕНА")
    print("=" * 60)
    print("\nДля запуска:")
    print("  python demo.py       - демонстрация")
    print("  python -m aeon.cli   - интерактивный режим")
    print("  run_aeon.bat         - запуск одним кликом")

if __name__ == "__main__":
    setup_aeon()