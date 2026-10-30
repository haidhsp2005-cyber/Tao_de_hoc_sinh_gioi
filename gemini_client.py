import json
import logging
import re
import time
import asyncio
import aiohttp
from typing import Dict, Any, Optional, Tuple, List
from key_manager import KeyManager, mask_key

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

def clean_and_parse_json(text_out: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Robust state-machine JSON parser:
    1. Removes Markdown code blocks.
    2. Directly parses valid JSON if possible.
    3. Handles unescaped LaTeX symbols (e.g. \\le, \\times, \\dots, \\sum).
    4. Handles raw unescaped newlines/tabs inside string literals.
    5. Auto-repairs unclosed quotes and braces if the response was truncated.
    """
    if not text_out:
        return None, "Empty text"

    cleaned = text_out.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    # 1. Direct parse attempt
    try:
        return json.loads(cleaned), None
    except Exception:
        pass

    try:
        return json.loads(cleaned, strict=False), None
    except Exception:
        pass

    # 2. State-machine scanner with intelligent quote escaping & unescaped character repairs
    repaired = []
    in_string = False
    escape = False
    is_key = False
    brace_stack = []
    i = 0
    n = len(cleaned)

    while i < n:
        c = cleaned[i]
        if not in_string:
            if c == '"':
                in_string = True
                prev_non_ws = ""
                for p in reversed(repaired):
                    if p not in " \t\r\n":
                        prev_non_ws = p
                        break
                is_key = (prev_non_ws in ['{', ','] and brace_stack and brace_stack[-1] == '}')
                repaired.append(c)
                i += 1
            elif c == '{':
                brace_stack.append('}')
                repaired.append(c)
                i += 1
            elif c == '[':
                brace_stack.append(']')
                repaired.append(c)
                i += 1
            elif c in ['}', ']']:
                if brace_stack and brace_stack[-1] == c:
                    brace_stack.pop()
                repaired.append(c)
                i += 1
            else:
                repaired.append(c)
                i += 1
        else:
            if escape:
                if c in ['"', '\\', '/', 'b', 'f', 'n', 'r', 't']:
                    repaired.append(c)
                elif c == 'u' and i + 4 < n and all(cleaned[i+1+k] in '0123456789abcdefABCDEF' for k in range(4)):
                    repaired.append(c)
                else:
                    # Invalid escape like \le -> escape previous backslash
                    repaired.insert(len(repaired) - 1, '\\')
                    repaired.append(c)
                escape = False
                i += 1
            else:
                if c == '\\':
                    escape = True
                    repaired.append(c)
                    i += 1
                elif c == '"':
                    # Lookahead to see if this is closing the string or an inner unescaped quote
                    j = i + 1
                    while j < n and cleaned[j] in ' \t\r\n':
                        j += 1
                    next_char = cleaned[j] if j < n else ''

                    if is_key:
                        if next_char == ':':
                            in_string = False
                            is_key = False
                            repaired.append(c)
                        else:
                            # Inner quote in key
                            repaired.append('\\"')
                    else:
                        is_closing = False
                        if next_char in ['}', ']', '']:
                            is_closing = True
                        elif next_char == ',':
                            # Look ahead after comma to see if a valid JSON token follows: "key":, or } / ]
                            k = j + 1
                            while k < n and cleaned[k] in ' \t\r\n':
                                k += 1
                            if k >= n or cleaned[k] in ['}', ']']:
                                is_closing = True
                            elif cleaned[k] == '"':
                                # Check if this is a key (followed by colon)
                                key_end = cleaned.find('"', k + 1)
                                if key_end != -1:
                                    colon_idx = key_end + 1
                                    while colon_idx < n and cleaned[colon_idx] in ' \t\r\n':
                                        colon_idx += 1
                                    if colon_idx < n and cleaned[colon_idx] == ':':
                                        is_closing = True

                        if is_closing:
                            in_string = False
                            repaired.append(c)
                        else:
                            # Inner unescaped quote inside string value (e.g. freopen("A.INP", "r", stdin))
                            repaired.append('\\"')
                    i += 1
                elif c == '\n':
                    repaired.append('\\n')
                    i += 1
                elif c == '\r':
                    repaired.append('\\r')
                    i += 1
                elif c == '\t':
                    repaired.append('\\t')
                    i += 1
                else:
                    repaired.append(c)
                    i += 1

    if escape:
        repaired.append('\\')
    if in_string:
        repaired.append('"')

    while brace_stack:
        repaired.append(brace_stack.pop())

    repaired_str = "".join(repaired)

    try:
        return json.loads(repaired_str, strict=False), None
    except Exception as e:
        # Fallback 3: Substring between first { and last }
        first_b = repaired_str.find('{')
        last_b = repaired_str.rfind('}')
        if first_b != -1 and last_b > first_b:
            try:
                return json.loads(repaired_str[first_b:last_b+1], strict=False), None
            except Exception:
                pass
        return None, str(e)

class GeminiClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_keys: Optional[List[str]] = None,
        key_manager: Optional[KeyManager] = None,
        model: str = "gemini-3.6-flash"
    ):
        self.model = model.strip() if model else "gemini-3.6-flash"
        # Strict guard: normalize local/Ollama model names to Gemini default
        if any(bad in self.model.lower() for bad in ["qwen", "deepseek", "llama", "coder", "mistral", "local"]):
            self.model = "gemini-3.6-flash"
        self.rotation_events: List[str] = []

        if key_manager is not None:
            self.key_manager = key_manager
        elif api_keys:
            self.key_manager = KeyManager(api_keys, name="User Pool")
        elif api_key and api_key.strip():
            self.key_manager = KeyManager([api_key.strip()], name="Single Key")
        else:
            self.key_manager = KeyManager.from_server_env()

    @property
    def api_key(self) -> str:
        k = self.key_manager.get_active_key()
        return k or ""

    async def verify_key(self, specific_key: Optional[str] = None) -> Dict[str, Any]:
        """Verify if a specific key or the active key in the pool is valid."""
        test_key = specific_key or self.key_manager.get_active_key()
        if not test_key:
            return {
                "valid": False,
                "error": "Chưa có Google Gemini API Key nào. Vui lòng thêm vào tệp .env trên máy chủ."
            }

        candidate_models = [self.model]
        if self.model != "gemini-3.6-flash":
            candidate_models.append("gemini-3.6-flash")

        last_error_msg = ""
        last_status = 500

        for attempt_model in candidate_models:
            url = f"{GEMINI_API_BASE}/{attempt_model}:generateContent?key={test_key}"
            payload = {
                "contents": [
                    {
                        "parts": [{"text": "Xin chào, hãy trả lời 'OK' nếu bạn đang hoạt động."}]
                    }
                ],
                "generationConfig": {
                    "maxOutputTokens": 10,
                    "temperature": 0.1
                }
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 200:
                            self.key_manager.mark_key_success(test_key)
                            self.model = attempt_model
                            data = await resp.json()
                            return {
                                "valid": True,
                                "model": attempt_model,
                                "masked_key": mask_key(test_key),
                                "response": data
                            }
                        else:
                            err_text = await resp.text()
                            try:
                                err_json = json.loads(err_text)
                                msg = err_json.get("error", {}).get("message", err_text)
                            except Exception:
                                msg = err_text
                            
                            last_status = resp.status
                            last_error_msg = msg

                            # If model 404 (deprecated / not found) and another candidate exists, retry with next model
                            if resp.status == 404 and attempt_model != "gemini-3.6-flash":
                                logger.warning(f"Mô hình {attempt_model} trả về 404. Tự động thử lại với gemini-3.6-flash...")
                                continue

                            self.key_manager.mark_key_failed(test_key, resp.status, msg)
                            return {
                                "valid": False,
                                "status": resp.status,
                                "masked_key": mask_key(test_key),
                                "error": f"Lỗi Google API ({resp.status}): {msg}"
                            }
            except Exception as e:
                self.key_manager.mark_key_failed(test_key, 500, str(e))
                return {
                    "valid": False,
                    "masked_key": mask_key(test_key),
                    "error": f"Không thể kết nối đến Google Gemini API: {str(e)}"
                }

        self.key_manager.mark_key_failed(test_key, last_status, last_error_msg)
        return {
            "valid": False,
            "status": last_status,
            "masked_key": mask_key(test_key),
            "error": f"Lỗi Google API ({last_status}): {last_error_msg}"
        }

    async def verify_all_keys(self) -> List[Dict[str, Any]]:
        """Verifies each key in the pool and returns diagnostic results."""
        results = []
        for k_obj in self.key_manager.key_objects:
            res = await self.verify_key(specific_key=k_obj.key)
            results.append({
                "masked_key": mask_key(k_obj.key),
                "valid": res.get("valid", False),
                "status": k_obj.status,
                "error": res.get("error", "")
            })
        return results

    async def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.5,
        max_tokens: int = 16384
    ) -> Dict[str, Any]:
        """
        Generate content from Gemini model with automatic key rotation and failover.
        If a key encounters 429 (quota) or 403 (suspended), it rotates to the next healthy key in the pool.
        """
        total_keys = self.key_manager.total_count()
        if total_keys == 0:
            raise ValueError("Chưa có Google Gemini API Key nào. Vui lòng nhập key trên giao diện hoặc thêm vào tệp .env trên máy chủ.")

        max_attempts = max(self.key_manager.healthy_count(), total_keys)
        max_attempts = max(max_attempts, 1)

        last_exception = None

        for attempt in range(max_attempts + 3):
            active_key = self.key_manager.get_active_key()
            if not active_key:
                # Check if some keys are in cooldown and can be recovered with a brief wait
                rate_limited = [k for k in self.key_manager.key_objects if k.status == "rate_limited"]
                if rate_limited:
                    min_wait = min(max(1.0, k.cooldown_until - time.time()) for k in rate_limited)
                    if min_wait <= 25.0:
                        logger.info(f"Toàn bộ key đang chờ hạn mức Quota. Tự động chờ {min_wait:.1f}s để hồi phục...")
                        await asyncio.sleep(min_wait + 0.5)
                        active_key = self.key_manager.get_active_key()
                if not active_key:
                    break

            url = f"{GEMINI_API_BASE}/{self.model}:generateContent?key={active_key}"

            generation_config: Dict[str, Any] = {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }

            if json_mode:
                generation_config["responseMimeType"] = "application/json"

            payload: Dict[str, Any] = {
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": generation_config
            }

            if system_instruction:
                payload["systemInstruction"] = {
                    "parts": [{"text": system_instruction}]
                }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                        if resp.status != 200:
                            err_text = await resp.text()
                            try:
                                err_json = json.loads(err_text)
                                err_msg = err_json.get("error", {}).get("message", err_text)
                            except Exception:
                                err_msg = err_text

                            # If 404 model deprecated, upgrade to gemini-3.6-flash
                            if resp.status == 404 and self.model != "gemini-3.6-flash":
                                logger.warning(f"Mô hình {self.model} không còn khả dụng ({err_msg}). Tự động nâng cấp sang gemini-3.6-flash.")
                                self.model = "gemini-3.6-flash"
                                continue

                            # Mark key failed
                            self.key_manager.mark_key_failed(active_key, resp.status, err_msg)

                            # Handle automatic rotation for 429, 403, 400
                            err_lower = err_msg.lower()
                            is_key_error = (
                                resp.status in [429, 403, 400] or 
                                "suspended" in err_lower or 
                                "quota" in err_lower or 
                                "resourceexhausted" in err_lower
                            )

                            if is_key_error:
                                next_k = self.key_manager.get_active_key()
                                if not next_k:
                                    rate_limited = [k for k in self.key_manager.key_objects if k.status == "rate_limited"]
                                    if rate_limited:
                                        min_wait = min(max(1.0, k.cooldown_until - time.time()) for k in rate_limited)
                                        if min_wait <= 25.0:
                                            logger.info(f"Đang đợi {min_wait:.1f}s để key tiếp theo hồi phục hạn mức...")
                                            await asyncio.sleep(min_wait + 0.5)
                                            next_k = self.key_manager.get_active_key()

                                if next_k and next_k != active_key:
                                    rot_msg = f"Key {mask_key(active_key)} gặp lỗi ({resp.status}). Tự động kích hoạt Key {mask_key(next_k)} để tiếp tục!"
                                    self.rotation_events.append(rot_msg)
                                    logger.warning(rot_msg)
                                    continue

                            raise RuntimeError(f"Gemini API Error ({resp.status}): {err_msg}")

                        result = await resp.json()
                        candidates = result.get("candidates", [])
                        if not candidates:
                            raise RuntimeError("Gemini không trả về kết quả nào (có thể do bộ lọc an toàn).")

                        parts = candidates[0].get("content", {}).get("parts", [])
                        # Gemini thinking models return thoughts with 'thought': True.
                        # We must extract the actual response from non-thought parts!
                        non_thought_parts = [p for p in parts if not p.get("thought")]
                        if non_thought_parts:
                            text_out = "".join(p.get("text", "") for p in non_thought_parts).strip()
                        elif parts:
                            text_out = parts[-1].get("text", "").strip()
                        else:
                            text_out = ""

                        self.key_manager.mark_key_success(active_key)

                        if json_mode:
                            parsed_json, parse_err = clean_and_parse_json(text_out)
                            if parsed_json is not None:
                                return {"text": text_out, "data": parsed_json, "raw": result}
                            else:
                                logger.error(f"JSON parsing error: {parse_err}. Content: {text_out[:500]}")
                                return {"text": text_out, "data": None, "parse_error": parse_err, "raw": result}

                        return {"text": text_out, "raw": result}

            except Exception as e:
                last_exception = e
                err_str = str(e).lower()
                if "suspended" in err_str or "quota" in err_str or "resourceexhausted" in err_str:
                    next_k = self.key_manager.get_active_key()
                    if next_k and next_k != active_key:
                        rot_msg = f"Key {mask_key(active_key)} gặp sự cố ({e}). Tự động xoay vòng sang Key {mask_key(next_k)}!"
                        self.rotation_events.append(rot_msg)
                        logger.warning(rot_msg)
                        continue
                logger.error(f"Generate content attempt {attempt+1} failed with key {mask_key(active_key)}: {e}")

        # If all keys failed or exhausted
        if last_exception:
            raise last_exception
        raise RuntimeError("Tất cả các API Key trong pool đều đã hết hạn mức hoặc bị khóa. Vui lòng bổ sung API Key mới.")
