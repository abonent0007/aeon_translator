"""
AEON v3.0 Web Interface — FastAPI backend + SPA frontend.
Запуск: python -m aeon.web_server
"""

import sys, os, json, time, asyncio
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Query, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import tempfile

from aeon.translator import AeonTranslator

app = FastAPI(title="AEON v3.0 API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

translator: Optional[AeonTranslator] = None
log_entries: list = []
MAX_LOGS = 200


def get_translator() -> AeonTranslator:
    global translator
    if translator is None:
        translator = AeonTranslator()
    return translator


def add_log(operation: str, data: dict):
    global log_entries
    log_entries.append({
        "time": time.strftime("%H:%M:%S"),
        "op": operation,
        **{k: v for k, v in data.items() if k != "semantic_atom"}
    })
    if len(log_entries) > MAX_LOGS:
        log_entries = log_entries[-MAX_LOGS:]


# ═══════════════════════════════════════════════════════════════
# API Endpoints
# ═══════════════════════════════════════════════════════════════

class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "auto"
    target_lang: str = "english"

class CodeRequest(BaseModel):
    text: str
    language: str = "python"

class BridgeRequest(BaseModel):
    text_a: str
    text_b: str
    lang_a: str = "auto"
    lang_b: str = "auto"

class SearchRequest(BaseModel):
    query: str
    candidates: list[str]

class VerifyRequest(BaseModel):
    text: str
    source_lang: str = "auto"


@app.post("/api/translate")
async def api_translate(req: TranslateRequest):
    t = get_translator()
    r = t.translate(req.text, source_language=req.source_lang, target_language=req.target_lang)
    add_log("translate", {"from": req.source_lang, "to": req.target_lang,
              "text": req.text[:50], "result": r['target']['content'][:100]})
    return {"result": r['target']['content'], "llm": r.get('llm_powered', False),
            "embedding": r.get('embedding_powered', False),
            "confidence": r.get('meaning_preserved', 0)}


@app.post("/api/code")
async def api_code(req: CodeRequest):
    t = get_translator()
    r = t.translate(req.text, source_form="text", target_form="code", target_language=req.language)
    add_log("code", {"lang": req.language, "text": req.text[:50]})
    return {"result": r['target']['content'], "llm": r.get('llm_powered', False)}


@app.post("/api/bridge")
async def api_bridge(req: BridgeRequest):
    t = get_translator()
    r = t.bridge_minds({"content": req.text_a, "language": req.lang_a},
                        {"content": req.text_b, "language": req.lang_b})
    m = r.get("methods", {})
    labs = m.get("labse", {}).get("similarity", 0) if "labse" in m else 0
    llm_s = m.get("llm", {}).get("similarity", 0) if "llm" in m else 0
    add_log("bridge", {"sim": r.get('similarity', 0), "connected": r['minds_connected']})
    return {"connected": r['minds_connected'], "similarity": r.get('similarity', 0),
            "labse_sim": labs, "llm_sim": llm_s,
            "message": r.get('message', ''), "explanation": r.get('explanation', ''),
            "methods": list(m.keys()), "level": r.get('understanding_level', '')}


@app.post("/api/explain")
async def api_explain(req: TranslateRequest):
    t = get_translator()
    atom = t.extractor.extract_from_text(req.text, req.source_lang)
    d = atom.to_dict()
    add_log("explain", {"intent": atom.intent, "domain": atom.domain, "entities": len(atom.entities)})
    return {"intent": atom.intent, "domain": atom.domain,
            "entities": [{"name": e.name, "type": e.type, "role": e.role} for e in atom.entities],
            "roles": atom.semantic_roles, "explanation": atom.explanation_chain,
            "evidence": atom.evidence, "confidence": atom.confidence_breakdown,
            "complexity": atom.complexity, "embedding_dim": len(atom.embedding),
            "hallucination_risk": atom.hallucination_risk}


@app.post("/api/verify")
async def api_verify(req: VerifyRequest):
    t = get_translator()
    r = t.translate(req.text, source_language=req.source_lang, target_language="english", verify=True)
    v = r.get("metadata", {}).get("verification", {})
    c = v.get("consistency", {})
    add_log("verify", {"risk": v.get('hallucination_risk', 0), "verdict": v.get('overall_verdict', '')})
    return {"risk": v.get('hallucination_risk', 0), "verdict": v.get('overall_verdict', ''),
            "consistency": c.get('score', 0), "flags": c.get('flags', [])}


@app.post("/api/search")
async def api_search(req: SearchRequest):
    t = get_translator()
    r = t.semantic_search(req.query, req.candidates)
    add_log("search", {"query": req.query[:50], "results": len(r)})
    return {"results": r}


@app.get("/api/stats")
async def api_stats():
    t = get_translator()
    s = t.stats()
    s["logs"] = log_entries[-50:]
    return s


@app.get("/api/logs")
async def api_logs():
    return {"logs": log_entries, "total": len(log_entries)}


# ═══════════════════════════════════════════════════════════════
# VOICE endpoints
# ═══════════════════════════════════════════════════════════════

class SpeakRequest(BaseModel):
    text: str
    language: str = "english"

@app.post("/api/voice/speak")
async def api_speak(req: SpeakRequest):
    t = get_translator()
    if not t.voice.tts.available:
        raise HTTPException(400, "TTS not available. Install: pip install edge-tts")
    path = t.voice.text_to_voice(req.text, language=req.language, play=False)
    if not path or not os.path.exists(path):
        raise HTTPException(500, "TTS generation failed")
    add_log("tts", {"lang": req.language, "text": req.text[:40]})
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type="audio/mpeg", filename="aeon_tts.mp3")


class TranscribeRequest(BaseModel):
    language: str = "auto"

@app.post("/api/voice/transcribe")
async def api_transcribe(file: UploadFile = File(None), language: str = "auto"):
    t = get_translator()
    if not t.voice.stt.available:
        raise HTTPException(400, "Whisper not installed. pip install openai-whisper")

    if file and file.filename:
        # Клиент загрузил аудиофайл
        suffix = os.path.splitext(file.filename)[1] or ".wav"
        fd, audio_path = tempfile.mkstemp(suffix=suffix, prefix="aeon_web_")
        os.close(fd)
        with open(audio_path, "wb") as f:
            f.write(await file.read())
    else:
        # Запись с микрофона сервера (fallback)
        audio_path = t.voice.stt.record_audio(duration=6.0)
        if not audio_path:
            raise HTTPException(500, "Recording failed")

    result = t.voice.voice_to_text(audio_path, language=language)
    try: os.unlink(audio_path)
    except: pass
    add_log("stt", {"lang": result.get("language", "?"), "text": result.get("text", "")[:40]})
    return {"text": result.get("text", ""), "language": result.get("language", "unknown")}


# ═══════════════════════════════════════════════════════════════
# IMAGE endpoint
# ═══════════════════════════════════════════════════════════════

class ImageRequest(BaseModel):
    text: str
    style: str = "realistic"
    width: int = 1024
    height: int = 576

@app.post("/api/image")
async def api_image(req: ImageRequest):
    t = get_translator()
    if not t.flux.available:
        raise HTTPException(400, "Flux API key not configured. Check FLUX_API_KEY in .env")
    r = t.text_to_image(req.text, style=req.style, width=req.width, height=req.height)
    add_log("image", {"style": req.style, "text": req.text[:40], "status": r.get("status", "error")})
    if r.get("error"):
        return {"error": r["error"], "images": []}
    paths = r.get("saved_paths", [])
    images = r.get("images", [])
    return {"status": "done", "paths": [os.path.basename(p) for p in paths],
            "urls": [img for img in images if isinstance(img, str) and img.startswith("http")][:3],
            "cost": r.get("cost", 0), "runtime": r.get("runtime", 0)}


# ═══════════════════════════════════════════════════════════════
# VIZ + AXIOMS + SAVE
# ═══════════════════════════════════════════════════════════════

@app.post("/api/viz")
async def api_viz(req: TranslateRequest):
    t = get_translator()
    r = t.translate(req.text, source_language=req.source_lang, target_form="visualization")
    add_log("viz", {"text": req.text[:40]})
    return {"visualization": r["target"]["content"]}


@app.get("/api/axioms")
async def api_axioms():
    from aeon.core import FUNDAMENTAL_AXIOMS
    return {"axioms": [{"name": a.name, "statement": a.statement} for a in FUNDAMENTAL_AXIOMS.values()]}


class SaveRequest(BaseModel):
    text: str
    path: str = "output.aeon"

@app.post("/api/save")
async def api_save(req: SaveRequest):
    t = get_translator()
    filepath = t.save_aeon(req.text, req.path)
    size = os.path.getsize(filepath)
    add_log("save", {"path": req.path, "size": size})
    from fastapi.responses import FileResponse
    return FileResponse(filepath, media_type="application/octet-stream", filename=req.path)


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "web" / "index.html"
    return html_path.read_text(encoding="utf-8")


def run(host: str = "0.0.0.0", port: int = 8080):
    w = 51
    display_host = "localhost" if host in ("0.0.0.0", "::") else host
    print(f"""
╔{'═'*w}╗
║{'🌌 AEON v3.0 Web Interface'.center(w)}║
║{f'http://{display_host}:{port}'.center(w)}║
╚{'═'*w}╝
""")
    uvicorn.run(app, host=host, port=port, log_level="warning")

if __name__ == "__main__":
    run()
