import os
import sys
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import json
import logging
import asyncio
from aiohttp import web
from gemini_client import GeminiClient
from ollama_client import OllamaClient
from agent_pipeline import OlympiadAgentPipeline, TOPIC_DETAILS, DIFFICULTY_DETAILS
from exporter import create_themis_zip
from docx_exporter import create_olympiad_docx
from key_manager import KeyManager, mask_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

from sample_data import SAMPLE_DEMO_DATA

async def handle_index(request):
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        return web.Response(text=html, content_type="text/html", headers=headers)
    return web.Response(text="Hệ thống Olympiad Exam Generator đang chuẩn bị giao diện...", content_type="text/plain; charset=utf-8")

async def handle_verify_key(request):
    """Verifies the current active key from server .env."""
    try:
        body = await request.json() if request.can_read_body else {}
        model = body.get("model", "gemini-3.6-flash").strip() if body else "gemini-3.6-flash"

        km = KeyManager.from_server_env()
        if km.total_count() == 0:
            return web.json_response({"valid": False, "error": "Chưa cấu hình API Key trong tệp .env trên máy chủ."}, status=400)

        client = GeminiClient(key_manager=km, model=model)
        result = await client.verify_key()
        return web.json_response(result)
    except Exception as e:
        logger.exception("Verify key error")
        return web.json_response({"valid": False, "error": str(e)}, status=500)

async def handle_get_keys_status(request):
    """Returns the status of server-configured hidden keys from .env and keys.txt."""
    try:
        km = KeyManager.from_server_env()
        summary = km.get_status_summary()
        return web.json_response({
            "success": True,
            "has_server_keys": km.total_count() > 0,
            "server_keys_count": km.total_count(),
            "healthy_count": km.healthy_count(),
            "data": summary
        })
    except Exception as e:
        logger.exception("Error checking server keys status")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_load_server_keys(request):
    """Returns the masked server keys list and status."""
    try:
        km = KeyManager.from_server_env()
        return web.json_response({
            "success": True,
            "keys": [k.to_dict() for k in km.key_objects],
            "count": km.total_count()
        })
    except Exception as e:
        logger.exception("Error loading server keys list")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_verify_pool(request):
    """Verifies all keys configured in .env and returns individual health checks."""
    try:
        body = await request.json() if request.can_read_body else {}
        model = body.get("model", "gemini-3.6-flash").strip() if body else "gemini-3.6-flash"

        km = KeyManager.from_server_env()
        if km.total_count() == 0:
            return web.json_response({
                "success": False,
                "error": "Không tìm thấy API Key nào trong tệp .env trên máy chủ. Vui lòng kiểm tra lại tệp .env."
            }, status=400)

        client = GeminiClient(key_manager=km, model=model)
        diagnostics = await client.verify_all_keys()

        return web.json_response({
            "success": True,
            "diagnostics": diagnostics,
            "total_count": km.total_count(),
            "healthy_count": sum(1 for d in diagnostics if d["valid"])
        })
    except Exception as e:
        logger.exception("Error verifying key pool")
        return web.json_response({"success": False, "error": str(e)}, status=500)

async def handle_get_topics(request):
    ollama_client = OllamaClient()
    ollama_health = await ollama_client.check_health()
    ollama_models = await ollama_client.list_models() if ollama_health.get("available") else []

    gemini_models = [
        {"id": "gemini-3.6-flash", "name": "Google Gemini 3.6 Flash (Khuyên dùng Cloud - Nhanh & Chuẩn)", "default": True},
        {"id": "gemini-2.5-flash", "name": "Google Gemini 2.5 Flash", "default": False},
        {"id": "gemini-2.0-flash", "name": "Google Gemini 2.0 Flash", "default": False},
        {"id": "gemini-1.5-flash", "name": "Google Gemini 1.5 Flash", "default": False}
    ]

    return web.json_response({
        "topics": TOPIC_DETAILS,
        "difficulties": DIFFICULTY_DETAILS,
        "models": gemini_models,
        "gemini_models": gemini_models,
        "ollama_models": ollama_models,
        "ollama_available": ollama_health.get("available", False),
        "ollama_default_model": ollama_health.get("selected_model", "qwen2.5:7b")
    })

async def handle_get_ollama_status(request):
    """Returns status and installed models of local Ollama."""
    try:
        client = OllamaClient()
        health = await client.check_health()
        models = await client.list_models()
        return web.json_response({
            "success": True,
            "available": health.get("available", False),
            "selected_model": health.get("selected_model", "qwen2.5:7b"),
            "models": models,
            "error": health.get("error", "")
        })
    except Exception as e:
        return web.json_response({
            "success": False,
            "available": False,
            "error": str(e),
            "models": []
        })

async def handle_get_sample_data(request):
    return web.json_response({
        "success": True,
        "data": SAMPLE_DEMO_DATA
    })

async def handle_generate_problem(request):
    try:
        body = await request.json()
        ai_engine = (body.get("ai_engine") or body.get("engine") or "gemini").lower().strip()
        model = (body.get("model") or "").strip()
        topic = body.get("topic") or body.get("topic_key", "xu_ly_so")
        difficulty = body.get("difficulty") or body.get("difficulty_key", "hsg_tinh")
        custom_theme = body.get("custom_theme", "").strip()
        problem_code = (body.get("problem_code") or body.get("problem_code_preference") or "").strip()
        io_mode = body.get("io_mode", "file")

        km = None
        if ai_engine == "ollama":
            ollama_model = model or "qwen2.5:7b"
            client = OllamaClient(model=ollama_model)
            health = await client.check_health()
            if not health.get("available"):
                return web.json_response({
                    "success": False,
                    "error": "Không thể kết nối đến Ollama trên cổng 11434. Vui lòng mở ứng dụng Ollama hoặc chạy lệnh 'ollama serve' rồi thử lại."
                }, status=503)
            logger.info(f"Generating problem with LOCAL OLLAMA ({ollama_model}) for topic={topic}, difficulty={difficulty}")
        else:
            # Gemini Cloud Mode
            km = KeyManager.from_server_env()
            if km.total_count() == 0:
                return web.json_response({
                    "success": False,
                    "error": "Không tìm thấy API Key nào trong tệp .env trên máy chủ. Vui lòng mở tệp .env và thêm key (ví dụ GEMINI_API_KEY_1=...) hoặc chuyển sang chế độ Ollama Local (Offline 100%)."
                }, status=400)
            gemini_model = model or "gemini-3.6-flash"
            client = GeminiClient(key_manager=km, model=gemini_model)
            logger.info(f"Generating problem with GEMINI CLOUD ({gemini_model}) for topic={topic}, difficulty={difficulty}, pool_size={km.total_count()}")

        fallback_used = False
        fallback_msg = ""
        try:
            pipeline = OlympiadAgentPipeline(client)
            result = await pipeline.generate_full_problem(
                topic_key=topic,
                difficulty_key=difficulty,
                custom_theme=custom_theme,
                problem_code_preference=problem_code,
                io_mode=io_mode
            )
        except Exception as e_gen:
            if ai_engine == "ollama":
                km_fallback = KeyManager.from_server_env()
                if km_fallback.total_count() > 0:
                    logger.warning(f"Ollama generation encountered issue ({e_gen}). Auto-falling back to Gemini Cloud (10 keys in .env)...")
                    gemini_model = "gemini-3.6-flash"
                    cloud_client = GeminiClient(key_manager=km_fallback, model=gemini_model)
                    cloud_pipeline = OlympiadAgentPipeline(cloud_client)
                    result = await cloud_pipeline.generate_full_problem(
                        topic_key=topic,
                        difficulty_key=difficulty,
                        custom_theme=custom_theme,
                        problem_code_preference=problem_code,
                        io_mode=io_mode
                    )
                    client = cloud_client
                    km = km_fallback
                    ai_engine = "gemini"
                    fallback_used = True
                    fallback_msg = "Mô hình Ollama nội bộ bị quá tải CPU. Hệ thống đã tự động chuyển sang Gemini Cloud và hoàn thành xuất sắc trong vài giây!"
                else:
                    raise e_gen
            else:
                raise e_gen

        return web.json_response({
            "success": True,
            "data": result,
            "ai_engine": ai_engine,
            "fallback_used": fallback_used,
            "fallback_message": fallback_msg,
            "key_pool_status": km.get_status_summary() if km else {"type": "ollama_local", "model": getattr(client, "model", "qwen2.5:7b"), "status": "offline_local"},
            "rotation_events": getattr(client, "rotation_events", [])
        })
    except Exception as e:
        logger.exception("Problem generation failed")
        return web.json_response({
            "success": False,
            "error": f"Quá trình sinh đề gặp lỗi: {str(e)}"
        }, status=500)

async def handle_download_zip(request):
    try:
        data = await request.json()
        problem_code = data.get("problem", {}).get("problem_code", "PROBLEM").upper()
        io_mode = data.get("io_mode", "file")
        
        zip_bytes = create_themis_zip(data, io_mode=io_mode)
        filename = f"{problem_code}_THEMIS_TESTS.zip"

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/zip",
            "Content-Length": str(len(zip_bytes))
        }
        return web.Response(body=zip_bytes, headers=headers)
    except Exception as e:
        logger.exception("ZIP generation failed")
        return web.json_response({"error": f"Lỗi tạo tệp ZIP: {str(e)}"}, status=500)

async def handle_download_word(request):
    try:
        data = await request.json()
        problem_code = data.get("problem", {}).get("problem_code", "PROBLEM").upper()
        
        docx_bytes = create_olympiad_docx(data, include_editorial=True)
        filename = f"{problem_code}_DE_THI_HSG.docx"

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "Content-Length": str(len(docx_bytes))
        }
        return web.Response(body=docx_bytes, headers=headers)
    except Exception as e:
        logger.exception("Word docx generation failed")
        return web.json_response({"error": f"Lỗi tạo tệp Word (.docx): {str(e)}"}, status=500)

def create_app():
    app = web.Application(client_max_size=1024 * 1024 * 50)
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/topics", handle_get_topics)
    app.router.add_get("/api/ollama/status", handle_get_ollama_status)
    app.router.add_get("/api/sample-data", handle_get_sample_data)
    app.router.add_get("/api/keys/status", handle_get_keys_status)
    app.router.add_get("/api/keys/load-server-keys", handle_load_server_keys)
    app.router.add_post("/api/verify-key", handle_verify_key)
    app.router.add_post("/api/keys/verify-pool", handle_verify_pool)
    app.router.add_post("/api/generate", handle_generate_problem)
    app.router.add_post("/api/download-zip", handle_download_zip)
    app.router.add_post("/api/download-word", handle_download_word)

    # Static assets
    if os.path.exists(STATIC_DIR):
        app.router.add_static("/static/", path=STATIC_DIR, name="static")

    return app

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    import socket

    def find_available_port(preferred_ports=[5000, 8000, 5050, 8888, 3000]):
        env_port = os.environ.get("PORT")
        if env_port:
            try:
                preferred_ports = [int(env_port)] + preferred_ports
            except ValueError:
                pass
        for p in preferred_ports:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", p))
                    return p
                except Exception:
                    continue
        return 5000

    app = create_app()
    env_port = os.environ.get("PORT")
    env_host = os.environ.get("HOST", "0.0.0.0" if env_port else "127.0.0.1")
    if env_port:
        try:
            port = int(env_port)
        except ValueError:
            port = find_available_port()
    else:
        port = find_available_port()

    print("================================================================")
    print("  OLYMPIAD PROBLEM FORGE - HE THONG TAO DE THI HSG TIN HOC")
    print(f"  Trang web dang chay tai: http://{env_host}:{port}")
    print("================================================================")
    web.run_app(app, host=env_host, port=port)
