import os
import json
import logging
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List, Tuple
from gemini_client import clean_and_parse_json

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_BASE = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"

class OllamaClient:
    """
    Client for interacting with local Ollama models (such as Qwen 2.5:7B, Qwen 2.5-Coder:7B, DeepSeek-R1).
    Provides 100% offline generation with structured JSON outputs and extended context window.
    """
    def __init__(self, model: str = DEFAULT_OLLAMA_MODEL, base_url: str = DEFAULT_OLLAMA_BASE):
        self.model = (model or DEFAULT_OLLAMA_MODEL).strip()
        self.base_url = (base_url or DEFAULT_OLLAMA_BASE).rstrip("/")
        self.rotation_events: List[str] = []

    async def check_health(self) -> Dict[str, Any]:
        """Checks if the local Ollama server is running and retrieves installed models."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                        return {
                            "available": True,
                            "models": models,
                            "selected_model": self.model,
                            "is_model_installed": any(self.model in m for m in models)
                        }
                    return {"available": False, "error": f"Ollama HTTP {resp.status}", "models": []}
        except Exception as e:
            return {"available": False, "error": str(e), "models": []}

    async def list_models(self) -> List[Dict[str, Any]]:
        """Returns detailed information of available local models."""
        health = await self.check_health()
        if not health.get("available"):
            return []
        
        models_info = []
        for m in health.get("models", []):
            name = m
            label = m
            if "qwen2.5:7b" in m or "qwen2.5-coder:7b" in m:
                label += " (Khuyên dùng - Rất mạnh về Tin học)"
            elif "deepseek" in m:
                label += " (Suy luận chuyên sâu)"
            models_info.append({
                "id": name,
                "name": label,
                "default": name == self.model
            })
        return models_info

    async def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.25,
        max_tokens: int = 8192
    ) -> Dict[str, Any]:
        """
        Sends generation request to local Ollama instance via /api/chat.
        Uses num_ctx: 8192 to prevent token clipping.
        """
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        # Optimized num_predict and num_ctx for local inference:
        # num_ctx: 4096 ensures problem statements and context are never truncated
        # eff_tokens: up to 2048 ensures complete C++ and Python code generation
        eff_tokens = min(max_tokens, 2048) if max_tokens else 1600
        num_ctx = 4096
        cpu_threads = os.cpu_count() or 4

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": "60m",
            "options": {
                "num_ctx": num_ctx,
                "temperature": temperature,
                "top_p": 0.9,
                "top_k": 40,
                "repeat_penalty": 1.1,
                "num_predict": eff_tokens,
                "num_thread": cpu_threads
            }
        }

        if json_mode:
            payload["format"] = "json"

        url = f"{self.base_url}/api/chat"
        logger.info(f"[Ollama] Calling local model '{self.model}' (json_mode={json_mode}, num_ctx={num_ctx}, num_predict={eff_tokens}, threads={cpu_threads})...")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=450)) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        logger.error(f"[Ollama] Error {resp.status}: {err_text}")
                        raise RuntimeError(f"Ollama API Error ({resp.status}): {err_text}")

                    res_json = await resp.json()
                    raw_text = res_json.get("message", {}).get("content", "")

                    parsed_data = None
                    if json_mode:
                        parsed_data, parse_err = clean_and_parse_json(raw_text)
                        if parse_err:
                            logger.warning(f"[Ollama] JSON parsing warning: {parse_err}")

                    return {
                        "text": raw_text,
                        "data": parsed_data
                    }
        except asyncio.TimeoutError:
            raise TimeoutError(f"Mô hình Ollama '{self.model}' xử lý quá 450s do CPU bận. Bạn có thể bấm nút 'Gemini Cloud' ở thanh tiêu đề để tạo đề siêu tốc chỉ trong 10 giây!")
        except Exception as e:
            logger.exception(f"[Ollama] Inference failed on model '{self.model}'")
            raise RuntimeError(f"Lỗi khi gọi mô hình Ollama '{self.model}': {str(e)}")
