"""
AEON — Универсальный Транслятор Смысла v3.0
LaBSE 768D embeddings + verification + .aeon format + anti-hallucination.
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

__version__ = "3.0.0"
__author__ = "Aeon Collective Intelligence"

from .core import Axiom, Thought, Flow, Concept
from .semantic_atom import SemanticAtom, Entity, Relation
from .extractor import MeaningExtractor
from .generator import ExpressionGenerator
from .translator import AeonTranslator
from .llm_client import DeepSeekClient
from .voice import VoiceProcessor, WhisperSTT, MultiVoiceTTS
from .image_gen import FluxImageGenerator
from .verification import VerificationEngine
from .aeon_format import AeonFormat
from .embeddings import EmbeddingEngine, get_embedding_engine

_llm = DeepSeekClient()
_llm_status = "ONLINE" if _llm.available else "OFFLINE (rule-based)"

def _banner():
    try:
        W = 54  # ширина содержимого
        def line(text): return f"║ {text:<{W}}║"
        status = _llm_status
        print(f"""
╔══════════════════════════════════════════════════════╗
{line("🌌 AEON v3.0.0 ЗАГРУЖЕН".center(W))}
{line("")}
{line('"Смысл един. Различаются только формы."'.center(W))}
{line("")}
{line(f"LLM (DeepSeek): {status}")}
{line("Embeddings: MiniLM 384D (50+ яз.)")}
{line("")}
{line("Усилено:")}
{line("  * Явная семантическая структура")}
{line("  * Кросс-языковой мост (MiniLM)")}
{line("  * Защита от галлюцинаций")}
{line("  * .aeon бинарный формат")}
╚══════════════════════════════════════════════════════╝
""")
    except UnicodeEncodeError:
        print("=" * 56)
        print("  AEON v3.0.0 LOADED")
        print("  LaBSE 768D + verification + .aeon format")
        print("=" * 56)

_banner()
