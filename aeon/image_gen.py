"""
Генератор изображений через Flux 2 API.
"""

import os
import json
import time
import base64
import requests
import tempfile
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class FluxImageGenerator:
    """
    Генератор изображений через Flux 2 API (gen-api.ru).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("FLUX_API_KEY")
        self.api_url = api_url or os.getenv("FLUX_API_URL", "https://api.gen-api.ru/api/v1/networks/flux-2")
        self.status_url = "https://api.gen-api.ru/api/v1/request/get"
        self.available = bool(self.api_key)

    def generate(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 576,
        model: str = "standard",
        poll_interval: float = 2.0,
        max_wait: float = 120.0
    ) -> dict:
        """
        Генерирует изображение по промпту.
        Возвращает dict с результатами или ошибкой.
        """
        if not self.available:
            return {"error": "FLUX_API_KEY not configured in .env", "images": []}

        # Шаг 1: отправляем запрос на генерацию
        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "width": width,
            "height": height
        })
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        print(f"   Генерация изображения через Flux 2...")
        print(f"   Промпт: {prompt[:120]}...")

        try:
            resp = requests.post(self.api_url, headers=headers, data=payload, timeout=30)
            if resp.status_code == 402:
                return {"error": "Flux API: нет кредитов на счёте. Пополните баланс на gen-api.ru", "images": []}
            if resp.status_code == 401:
                return {"error": "Flux API: неверный API-ключ. Проверьте FLUX_API_KEY в .env", "images": []}
            if resp.status_code == 429:
                return {"error": "Flux API: слишком много запросов. Подождите и попробуйте позже", "images": []}
            resp.raise_for_status()
            create_result = resp.json()
        except requests.exceptions.Timeout:
            return {"error": "Flux API: таймаут запроса. Сервер не отвечает", "images": []}
        except requests.exceptions.ConnectionError:
            return {"error": "Flux API: ошибка соединения. Проверьте интернет", "images": []}
        except Exception as e:
            return {"error": f"Flux API: {e}", "images": []}

        request_id = create_result.get("request_id")
        if not request_id:
            return {"error": "No request_id in Flux response", "raw": create_result, "images": []}

        print(f"   Request ID: {request_id}, ожидание результата...")

        # Шаг 2: полим результат
        start_time = time.time()
        while time.time() - start_time < max_wait:
            time.sleep(poll_interval)
            try:
                status_resp = requests.get(
                    f"{self.status_url}/{request_id}",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=30
                )
                status_resp.raise_for_status()
                status_data = status_resp.json()
            except Exception:
                continue

            status = status_data.get("status", "")
            progress = status_data.get("progress", 0)
            elapsed = time.time() - start_time
            print(f"   Статус: {status} | Прогресс: {progress}% | {elapsed:.0f}с")

            if status in ("completed", "done", "success"):
                return self._extract_images(status_data, request_id)
            elif status in ("failed", "error"):
                return {"error": "Flux generation failed", "status_data": status_data, "images": []}

        return {"error": f"Timeout after {max_wait}s", "request_id": request_id, "images": []}

    def _extract_images(self, status_data: dict, request_id: int) -> dict:
        """Извлекает изображения из ответа API."""
        images = []
        result = status_data.get("result", [])
        full_response = status_data.get("full_response", [])

        # Пробуем разные поля
        candidates = [result, full_response, status_data.get("images", [])]
        for candidate in candidates:
            if isinstance(candidate, list):
                for item in candidate:
                    if isinstance(item, str):
                        images.append(item)
                    elif isinstance(item, dict):
                        for v in item.values():
                            if isinstance(v, str) and len(v) > 100:
                                images.append(v)

        saved_paths = []
        for i, img_data in enumerate(images):
            path = self._save_image(img_data, request_id, i)
            if path:
                saved_paths.append(path)

        return {
            "request_id": request_id,
            "status": status_data.get("status", "unknown"),
            "images": images,
            "saved_paths": saved_paths,
            "cost": status_data.get("cost", 0),
            "runtime": status_data.get("runtime", 0)
        }

    def _save_image(self, data: str, request_id: int, index: int) -> Optional[str]:
        """Сохраняет изображение (из URL или base64)."""
        try:
            if data.startswith("http"):
                resp = requests.get(data, timeout=30)
                resp.raise_for_status()
                content = resp.content
            elif data.startswith("data:"):
                header, b64 = data.split(",", 1)
                content = base64.b64decode(b64)
            else:
                content = base64.b64decode(data)
                # Если не base64 — сохраняем как текст (может быть URL в чистом виде)
                try:
                    pass
                except Exception:
                    return None

            ext = ".png"
            fd, path = tempfile.mkstemp(suffix=ext, prefix=f"aeon_flux_{request_id}_{index}_")
            os.close(fd)
            with open(path, "wb") as f:
                f.write(content)
            return path
        except Exception as e:
            print(f"   Ошибка сохранения изображения {index}: {e}")
            return None

    def generate_from_text(self, text: str, llm_client=None, style: str = "realistic") -> dict:
        """
        Генерирует изображение из текста, используя LLM для создания промпта.
        """
        if llm_client and llm_client.available:
            prompt = llm_client.describe_for_image(text, style)
            if not prompt:
                prompt = text
        else:
            prompt = text

        return self.generate(prompt)

    def generate_from_emotion(self, emotion_text: str, llm_client=None) -> dict:
        """
        Генерирует изображение из описания эмоции.
        """
        return self.generate_from_text(emotion_text, llm_client, style="artistic, emotional, atmospheric")

    def generate_from_code(self, code: str, llm_client=None) -> dict:
        """
        Генерирует визуализацию концепции из кода.
        """
        desc = f"Visualize the abstract concept and architecture of this code as a beautiful technical illustration: {code[:500]}"
        return self.generate_from_text(desc, llm_client, style="technical, abstract, futuristic")
