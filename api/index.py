import os
import sys
import logging

# Ensure root directory is in sys.path so modules can be imported inside Vercel serverless environment
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from sample_data import SAMPLE_DEMO_DATA

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = os.path.join(ROOT_DIR, "static")

app = FastAPI(title="Olympiad Problem Forge", redirect_slashes=False, docs_url=None, redoc_url=None)

# Mount static folder
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Edge Cache Headers Constants
CACHE_STATIC_HEADERS = {
    "Cache-Control": "public, max-age=86400, s-maxage=86400, stale-while-revalidate=604800",
    "X-Edge-Cache": "HIT"
}

CACHE_HTML_HEADERS = {
    "Cache-Control": "public, max-age=0, s-maxage=0, must-revalidate",
    "Pragma": "no-cache"
}

def get_index_html():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Olympiad Problem Forge đang chuẩn bị giao diện...</h1>"

# Multi-path index handler ensuring any Vercel entrypoint path loads index.html
@app.get("/", response_class=HTMLResponse)
@app.get("/api", response_class=HTMLResponse)
@app.get("/api/", response_class=HTMLResponse)
@app.get("/api/index", response_class=HTMLResponse)
@app.get("/api/index.py", response_class=HTMLResponse)
async def index():
    html = get_index_html()
    return HTMLResponse(content=html, headers=CACHE_HTML_HEADERS)

# SPA fallback handler: any non-API GET request loads index.html instead of {"detail":"Not Found"}
@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    path = request.url.path
    if path.startswith("/api/"):
        return JSONResponse({"success": False, "error": f"API endpoint not found: {path}"}, status_code=404)
    # Check if requesting static assets directly
    if path.startswith("/static/"):
        file_subpath = path[len("/static/"):]
        file_path = os.path.join(STATIC_DIR, file_subpath)
        if os.path.exists(file_path):
            return FileResponse(file_path, headers=CACHE_STATIC_HEADERS)
    return HTMLResponse(content=get_index_html(), headers=CACHE_HTML_HEADERS)

@app.get("/favicon.ico")
async def favicon():
    fav_path = os.path.join(STATIC_DIR, "favicon.ico")
    if os.path.exists(fav_path):
        return FileResponse(fav_path, headers=CACHE_STATIC_HEADERS)
    return Response(status_code=204)

@app.get("/app.js")
@app.get("/static/app.js")
@app.get("/api/static/app.js")
async def serve_app_js():
    js_path = os.path.join(STATIC_DIR, "app.js")
    if os.path.exists(js_path):
        return FileResponse(js_path, media_type="application/javascript", headers=CACHE_STATIC_HEADERS)
    return Response(status_code=404)

@app.get("/style.css")
@app.get("/static/style.css")
@app.get("/api/static/style.css")
async def serve_style_css():
    css_path = os.path.join(STATIC_DIR, "style.css")
    if os.path.exists(css_path):
        return FileResponse(css_path, media_type="text/css", headers=CACHE_STATIC_HEADERS)
    return Response(status_code=404)

@app.get("/api/topics")
@app.get("/topics")
async def get_topics():
    # Lazy import topic and difficulty details on first request
    from agent_pipeline import TOPIC_DETAILS, DIFFICULTY_DETAILS
    gemini_models = [
        {"id": "gemini-3.6-flash", "name": "Google Gemini 3.6 Flash (Khuyên dùng Cloud - Nhanh & Chuẩn)", "default": True},
        {"id": "gemini-2.5-flash", "name": "Google Gemini 2.5 Flash", "default": False},
        {"id": "gemini-2.0-flash", "name": "Google Gemini 2.0 Flash", "default": False},
        {"id": "gemini-1.5-flash", "name": "Google Gemini 1.5 Flash", "default": False}
    ]
    return JSONResponse({
        "topics": TOPIC_DETAILS,
        "difficulties": DIFFICULTY_DETAILS,
        "models": gemini_models,
        "gemini_models": gemini_models,
        "ollama_models": [],
        "ollama_available": False,
        "ollama_default_model": "qwen2.5:7b"
    })

@app.get("/api/ollama/status")
@app.get("/ollama/status")
async def get_ollama_status():
    return JSONResponse({
        "success": True,
        "available": False,
        "selected_model": "qwen2.5:7b",
        "models": [],
        "error": "Ollama offline không khả dụng trên Vercel Serverless. Hệ thống tự động chuyển sang Gemini Cloud."
    })

@app.get("/api/sample-data")
@app.get("/sample-data")
async def get_sample_data():
    return JSONResponse({
        "success": True,
        "data": SAMPLE_DEMO_DATA
    })

@app.get("/api/keys/status")
@app.get("/keys/status")
async def get_keys_status():
    try:
        from key_manager import KeyManager
        km = KeyManager.from_server_env()
        summary = km.get_status_summary()
        return JSONResponse({
            "success": True,
            "has_server_keys": km.total_count() > 0,
            "server_keys_count": km.total_count(),
            "healthy_count": km.healthy_count(),
            "data": summary
        })
    except Exception as e:
        logger.exception("Error checking server keys status")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.get("/api/keys/load-server-keys")
@app.get("/keys/load-server-keys")
async def load_server_keys():
    try:
        from key_manager import KeyManager
        km = KeyManager.from_server_env()
        return JSONResponse({
            "success": True,
            "keys": [k.to_dict() for k in km.key_objects],
            "count": km.total_count()
        })
    except Exception as e:
        logger.exception("Error loading server keys list")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/api/verify-key")
@app.post("/verify-key")
async def verify_key(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    model = (body.get("model") or "gemini-3.6-flash").strip()
    from key_manager import KeyManager
    from gemini_client import GeminiClient
    km = KeyManager.from_server_env()
    if km.total_count() == 0:
        return JSONResponse({
            "valid": False, 
            "error": "Chưa cấu hình GEMINI_API_KEY trong Environment Variables trên Vercel. Vui lòng vào Vercel Settings -> Environment Variables để thêm key."
        }, status_code=400)
    client = GeminiClient(key_manager=km, model=model)
    result = await client.verify_key()
    return JSONResponse(result)

@app.post("/api/keys/verify-pool")
@app.post("/keys/verify-pool")
async def verify_pool(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    model = (body.get("model") or "gemini-3.6-flash").strip()
    from key_manager import KeyManager
    from gemini_client import GeminiClient
    km = KeyManager.from_server_env()
    if km.total_count() == 0:
        return JSONResponse({
            "success": False,
            "error": "Không tìm thấy GEMINI_API_KEY trong Environment Variables trên Vercel."
        }, status_code=400)
    client = GeminiClient(key_manager=km, model=model)
    diagnostics = await client.verify_all_keys()
    return JSONResponse({
        "success": True,
        "diagnostics": diagnostics,
        "total_count": km.total_count(),
        "healthy_count": sum(1 for d in diagnostics if d.get("valid"))
    })

@app.post("/api/generate")
@app.post("/generate")
async def generate_problem(request: Request):
    try:
        body = await request.json()
        model = (body.get("model") or "").strip()
        topic = body.get("topic") or body.get("topic_key", "xu_ly_so")
        difficulty = body.get("difficulty") or body.get("difficulty_key", "hsg_tinh")
        custom_theme = body.get("custom_theme", "").strip()
        problem_code = (body.get("problem_code") or body.get("problem_code_preference") or "").strip()
        io_mode = body.get("io_mode", "file")

        # Lazy import heavy pipeline and client libraries
        from key_manager import KeyManager
        from gemini_client import GeminiClient
        from agent_pipeline import OlympiadAgentPipeline

        km = KeyManager.from_server_env()
        if km.total_count() == 0:
            return JSONResponse({
                "success": False,
                "error": "Chưa cấu hình GEMINI_API_KEY trên Vercel! Vui lòng truy cập Vercel Dashboard -> Project Settings -> Environment Variables -> thêm biến GEMINI_API_KEY."
            }, status_code=400)

        gemini_model = model or "gemini-3.6-flash"
        client = GeminiClient(key_manager=km, model=gemini_model)
        logger.info(f"[Vercel] Generating problem with GEMINI CLOUD ({gemini_model}) for topic={topic}, difficulty={difficulty}, pool_size={km.total_count()}")

        pipeline = OlympiadAgentPipeline(client)
        result = await pipeline.generate_full_problem(
            topic_key=topic,
            difficulty_key=difficulty,
            custom_theme=custom_theme,
            problem_code_preference=problem_code,
            io_mode=io_mode
        )

        return JSONResponse({
            "success": True,
            "data": result,
            "ai_engine": "gemini",
            "fallback_used": False,
            "fallback_message": "",
            "key_pool_status": km.get_status_summary(),
            "rotation_events": getattr(client, "rotation_events", [])
        })
    except Exception as e:
        logger.exception("Problem generation failed on Vercel")
        return JSONResponse({
            "success": False,
            "error": f"Quá trình sinh đề gặp lỗi: {str(e)}"
        }, status_code=500)

@app.post("/api/download-zip")
@app.post("/download-zip")
async def download_zip(request: Request):
    try:
        data = await request.json()
        problem_code = data.get("problem", {}).get("problem_code", "PROBLEM").upper()
        io_mode = data.get("io_mode", "file")

        # Lazy import ZIP exporter
        from exporter import create_themis_zip

        zip_bytes = create_themis_zip(data, io_mode=io_mode)
        filename = f"{problem_code}_THEMIS_TESTS.zip"
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(zip_bytes))
            }
        )
    except Exception as e:
        logger.exception("ZIP generation failed")
        return JSONResponse({"error": f"Lỗi tạo tệp ZIP: {str(e)}"}, status_code=500)

@app.post("/api/download-word")
@app.post("/download-word")
async def download_word(request: Request):
    try:
        data = await request.json()
        problem_code = data.get("problem", {}).get("problem_code", "PROBLEM").upper()

        # Lazy import Word docx exporter
        from docx_exporter import create_olympiad_docx

        docx_bytes = create_olympiad_docx(data, include_editorial=True)
        filename = f"{problem_code}_DE_THI_HSG.docx"
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(docx_bytes))
            }
        )
    except Exception as e:
        logger.exception("Word docx generation failed")
        return JSONResponse({"error": f"Lỗi tạo tệp Word (.docx): {str(e)}"}, status_code=500)
