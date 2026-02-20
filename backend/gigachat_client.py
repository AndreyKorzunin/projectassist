import os
import base64
import requests
from typing import Dict, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
import structlog

load_dotenv()
logger = structlog.get_logger()


class GigaChatClient:


    def __init__(self):
        self.client_id = os.getenv("GIGACHAT_CLIENT_ID")
        self.secret = os.getenv("GIGACHAT_SECRET")
        self.scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self.model = os.getenv("GIGACHAT_MODEL", "GigaChat")
        self.temperature = float(os.getenv("GIGACHAT_TEMPERATURE", 0.3))

        if not self.client_id or not self.secret:
            raise ValueError(
                "Необходимо указать ключи в .env файле.\n"

            )

        self._access_token = None
        self._token_expires_at = None


        self._init_cache()

    def _init_cache(self):

        try:
            import redis
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", 6379))
            self.cache = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=0,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=5
            )
            self.cache.ping()
            self.use_redis = True
            logger.info("redis_cache_enabled")
        except Exception as e:
            logger.warning("redis_not_available", error=str(e))
            self.cache = {}
            self.use_redis = False

    def _get_auth_header(self) -> str:

        auth_str = f"{self.client_id}:{self.secret}"
        auth_bytes = auth_str.encode('utf-8')
        return base64.b64encode(auth_bytes).decode('utf-8')

    def _refresh_token(self) -> None:

        if self._access_token and self._token_expires_at and self._token_expires_at > datetime.now():
            return

        logger.info("refreshing_gigachat_token")

        try:
            response = requests.post(
                "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
                headers={
                    "Authorization": f"Basic {self._get_auth_header()}",
                    "RqUID": str(datetime.now().timestamp()),
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={"scope": self.scope},
                verify=False,
                timeout=10
            )
            response.raise_for_status()

            token_data = response.json()
            self._access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 1800)
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)

            logger.info("token_refreshed", expires_in=expires_in)

        except requests.exceptions.RequestException as e:
            error_msg = f"Ошибка получения токена GigaChat: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg += f"\nКод ошибки: {error_data.get('error_code', 'N/A')}"
                except:
                    pass
            logger.error("token_refresh_failed", error=error_msg)
            raise Exception(error_msg)

    def _get_cache_key(self, context: str, query: str, task_type: str) -> str:

        import hashlib
        key_str = f"{context[:1000]}|{query}|{task_type}"
        return "gigachat:" + hashlib.md5(key_str.encode()).hexdigest()

    def _get_cached_response(self, cache_key: str) -> Optional[str]:

        try:
            if self.use_redis:
                return self.cache.get(cache_key)
            else:
                return self.cache.get(cache_key)
        except Exception as e:
            logger.warning("cache_get_failed", error=str(e))
            return None

    def _set_cached_response(self, cache_key: str, response: str, ttl: int = 3600):

        try:
            if self.use_redis:
                self.cache.setex(cache_key, ttl, response)
            else:
                self.cache[cache_key] = response
        except Exception as e:
            logger.warning("cache_set_failed", error=str(e))

    def _build_prompt(self, context: str, query: str, task_type: str = "answer") -> list:


        system_prompts = {
            "answer": """Ты — эксперт по анализу документов. Отвечай ТОЛЬКО на основе предоставленного контекста.
Правила:
1. Если информации в контексте недостаточно — скажи: "В документе нет информации об этом".
2. Приводи точные цитаты или данные из документа.
3. Отвечай кратко, по делу, на русском языке.
4. Не выдумывай факты и даты.""",

            "grammar_check": """Ты — редактор с опытом работы в деловой переписке. Проанализируй текст на ошибки.
Формат ответа:
- Орфография: [список ошибок с исправлениями]
- Пунктуация: [проблемные места]
- Стиль: [рекомендации по улучшению]
- Избыточность: [повторяющиеся конструкции]""",

            "find_repeats": """Ты — аналитик текстов. Найди семантические повторы и избыточные формулировки.
Формат ответа:
1. Группа повторов: "[фраза 1]" ↔ "[фраза 2]" (сходство: 85%)
   Рекомендация: объединить в "[оптимальная формулировка]"
2. ...""",

            "structure_analysis": """Ты — эксперт по структуре документов. Проанализируй организацию текста.
Оцени:
- Наличие логических разделов (введение, основная часть, заключение)
- Иерархию заголовков
- Сбалансированность объёма разделов
- Рекомендации по улучшению структуры"""
        }

        return [
            {"role": "system", "content": system_prompts.get(task_type, system_prompts["answer"])},
            {"role": "user", "content": f"КОНТЕКСТ ИЗ ДОКУМЕНТА:\n{context}\n\nВОПРОС ПОЛЬЗОВАТЕЛЯ:\n{query}"}
        ]

    def generate(self, context: str, query: str, task_type: str = "answer") -> dict:

        cache_key = self._get_cache_key(context, query, task_type)
        cached_response = self._get_cached_response(cache_key)
        if cached_response:
            logger.info("response_from_cache", task_type=task_type)
            return {"response": cached_response, "cached": True, "from_cache": True}

        self._refresh_token()

        messages = self._build_prompt(context, query, task_type)

        try:
            logger.info("calling_gigachat_api", task_type=task_type, query=query[:50])

            response = requests.post(
                "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": 1024,
                    "stream": False
                },
                verify=False,
                timeout=30
            )

            if response.status_code == 401:
                logger.warning("token_expired_retrying")
                self._access_token = None
                return self.generate(context, query, task_type)

            response.raise_for_status()

            result = response.json()["choices"][0]["message"]["content"].strip()


            self._set_cached_response(cache_key, result)

            logger.info("response_received", task_type=task_type, chars=len(result))

            return {
                "response": result,
                "cached": False,
                "model": self.model,
                "from_cache": False
            }

        except requests.exceptions.Timeout:
            logger.error("gigachat_timeout")
            raise Exception("Таймаут запроса к GigaChat API. Попробуйте ещё раз.")
        except requests.exceptions.RequestException as e:
            error_msg = f"Ошибка GigaChat API: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg += f"\nКод ошибки: {error_data.get('error_code', 'N/A')}"
                    error_msg += f"\nСообщение: {error_data.get('message', 'N/A')}"
                except:
                    error_msg += f"\nResponse: {e.response.text}"
            logger.error("gigachat_api_error", error=error_msg)
            raise Exception(error_msg)

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    def health_check(self) -> dict:

        try:
            self._refresh_token()
            return {
                "status": "ok",
                "model": self.model,
                "token_expires_in": int(
                    (self._token_expires_at - datetime.now()).total_seconds()) if self._token_expires_at else None,
                "cache_enabled": self.use_redis,
                "scope": self.scope
            }
        except Exception as e:
            logger.error("health_check_failed", error=str(e))
            return {"status": "error", "message": str(e)}