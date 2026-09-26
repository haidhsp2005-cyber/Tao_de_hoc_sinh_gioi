import os
import re
import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

def mask_key(key: str) -> str:
    """Masks an API key to protect privacy, e.g. AIzaSyB1...2a9F"""
    if not key:
        return "None"
    k = key.strip()
    if len(k) <= 10:
        return k[:3] + "..." + k[-2:]
    return f"{k[:8]}...{k[-4:]}"

class ApiKeyInfo:
    def __init__(self, key: str):
        self.key = key.strip()
        self.status = "healthy"  # 'healthy', 'rate_limited', 'suspended', 'invalid'
        self.cooldown_until = 0.0
        self.uses_count = 0
        self.fail_count = 0
        self.last_error = ""

    def is_available(self) -> bool:
        if self.status in ["suspended", "invalid"]:
            return False
        if self.status == "rate_limited":
            if time.time() >= self.cooldown_until:
                # Cooldown expired, restore to healthy
                self.status = "healthy"
                return True
            return False
        return True

    def mark_success(self):
        self.status = "healthy"
        self.uses_count += 1

    def mark_failed(self, status_code: int, error_msg: str):
        self.fail_count += 1
        self.last_error = error_msg
        err_lower = error_msg.lower()

        if status_code == 429 or "resourceexhausted" in err_lower or "quota" in err_lower:
            self.status = "rate_limited"
            # Try parsing exact retry-after seconds if provided by Google API
            retry_match = re.search(r'retry in ([\d\.]+)s', error_msg, re.IGNORECASE)
            wait_sec = min(60.0, float(retry_match.group(1)) + 2.0) if retry_match else 30.0
            self.cooldown_until = time.time() + wait_sec
            logger.warning(f"Key {mask_key(self.key)} rate-limited (429). Cooldown for {wait_sec:.1f}s.")
        elif status_code == 403 or "suspended" in err_lower or "permissiondenied" in err_lower:
            self.status = "suspended"
            logger.error(f"Key {mask_key(self.key)} suspended (403). Disabled permanently.")
        elif status_code == 400 and ("invalid" in err_lower or "not found" in err_lower):
            self.status = "invalid"
            logger.error(f"Key {mask_key(self.key)} is invalid (400). Disabled permanently.")
        else:
            if self.fail_count >= 3:
                self.status = "rate_limited"
                self.cooldown_until = time.time() + 20.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "masked_key": mask_key(self.key),
            "status": self.status,
            "is_available": self.is_available(),
            "uses_count": self.uses_count,
            "fail_count": self.fail_count,
            "cooldown_remaining": max(0, int(self.cooldown_until - time.time())) if self.status == "rate_limited" else 0,
            "last_error": self.last_error
        }

class KeyManager:
    """
    Manages a pool of Google Gemini API keys.
    Provides round-robin rotation, automatic failover across 429/403/400 errors,
    and server-side secret key loading from .env and keys.txt.
    """
    def __init__(self, keys: Optional[List[str]] = None, name: str = "Pool"):
        self.name = name
        self.key_objects: List[ApiKeyInfo] = []
        self._current_index = 0
        if keys:
            self.add_keys(keys)

    def add_keys(self, keys: List[str]):
        seen = {k.key for k in self.key_objects}
        placeholder_patterns = ["yourkey", "your_key", "here", "placeholder"]
        for k in keys:
            cleaned = k.strip()
            if not cleaned or cleaned.startswith("#") or cleaned in seen:
                continue
            lower = cleaned.lower()
            if any(p in lower for p in placeholder_patterns):
                continue
            self.key_objects.append(ApiKeyInfo(cleaned))
            seen.add(cleaned)

    def get_all_keys(self) -> List[str]:
        return [k.key for k in self.key_objects]

    def get_active_key(self) -> Optional[str]:
        """Returns the next available healthy key via round-robin."""
        available = [k for k in self.key_objects if k.is_available()]
        if not available:
            return None

        # Round-robin selection
        self._current_index = (self._current_index + 1) % len(available)
        chosen = available[self._current_index]
        return chosen.key

    def mark_key_failed(self, key: str, status_code: int, error_msg: str):
        for k in self.key_objects:
            if k.key == key:
                k.mark_failed(status_code, error_msg)
                break

    def mark_key_success(self, key: str):
        for k in self.key_objects:
            if k.key == key:
                k.mark_success()
                break

    def total_count(self) -> int:
        return len(self.key_objects)

    def healthy_count(self) -> int:
        return sum(1 for k in self.key_objects if k.is_available())

    def get_status_summary(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "total_keys": self.total_count(),
            "healthy_keys": self.healthy_count(),
            "keys": [k.to_dict() for k in self.key_objects]
        }

    @classmethod
    def from_server_env(cls, project_dir: Optional[str] = None) -> "KeyManager":
        """
        Loads hidden keys from .env, keys.txt, or os.environ.
        Enables 100% hidden server-side key usage.
        """
        keys: List[str] = []
        base_dir = project_dir or os.path.dirname(os.path.abspath(__file__))

        # 1. Check keys.txt in project directory
        keys_file = os.path.join(base_dir, "keys.txt")
        if os.path.exists(keys_file):
            try:
                with open(keys_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            keys.append(line)
                logger.info(f"Loaded {len(keys)} keys from keys.txt")
            except Exception as e:
                logger.warning(f"Error reading keys.txt: {e}")

        # 2. Check .env file
        env_file = os.path.join(base_dir, ".env")
        if os.path.exists(env_file):
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("#") or not line or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k in ["GEMINI_API_KEY", "GOOGLE_API_KEY"] and v:
                            keys.append(v)
                        elif k in ["GEMINI_API_KEYS", "GOOGLE_API_KEYS"] and v:
                            parts = re.split(r'[,;\n]', v)
                            for p in parts:
                                if p.strip():
                                    keys.append(p.strip())
                        elif k.startswith("GEMINI_API_KEY_") and v:
                            keys.append(v)
                logger.info(f"Loaded keys from .env: total accumulated = {len(keys)}")
            except Exception as e:
                logger.warning(f"Error reading .env: {e}")

        # 3. Check os.environ (supports Render Environment Variables)
        for env_k, env_v in os.environ.items():
            if not env_v:
                continue
            if env_k in ["GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEYS", "GOOGLE_API_KEYS"]:
                parts = re.split(r'[,;\n]', env_v)
                for p in parts:
                    if p.strip():
                        keys.append(p.strip())
            elif env_k.startswith("GEMINI_API_KEY_") or env_k.startswith("GOOGLE_API_KEY_"):
                parts = re.split(r'[,;\n]', env_v)
                for p in parts:
                    if p.strip():
                        keys.append(p.strip())

        return cls(keys=keys, name="Server Key Pool")
