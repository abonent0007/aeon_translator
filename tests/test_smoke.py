"""Smoke: пакет импортируется, ключевые объекты доступны."""

import aeon


def test_package_imports():
    assert aeon.__version__


def test_key_objects_exported():
    from aeon import AeonTranslator, SemanticAtom, VerificationEngine

    assert SemanticAtom is not None
    assert AeonTranslator is not None
    assert VerificationEngine is not None
