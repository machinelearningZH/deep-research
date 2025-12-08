from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import os
import requests
import json
from datetime import datetime
from openai import OpenAI
from tenacity import retry, stop_after_attempt, stop_after_delay
from dotenv import load_dotenv
from _core.config import config
from _core.logger import custom_logger
from _core.utils import TokenCounter


try:
    dotenv_path = config["api_keys"]["dotenv_path"]
    load_dotenv(dotenv_path)
    custom_logger.info_console(f"Loaded .env from: {dotenv_path}")
except Exception as e:
    custom_logger.info_console(f"Error loading .env file: {e}")


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    def call(self, prompt: str, **kwargs) -> str:
        """Make a standard call to the LLM."""
        pass

    @abstractmethod
    def call_structured(
        self, prompt: str, json_schema: Dict[str, Any], **kwargs
    ) -> str:
        """Make a call to the LLM and retrieve a structured response."""
        pass

    @abstractmethod
    def call_with_reasoning(self, prompt: str, **kwargs) -> tuple[str, dict]:
        """Call LLM API with reasoning parameters."""
        pass


class OpenRouterClient(LLMClient):
    """OpenRouter API client implementation."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OpenRouter API key not found")

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1", api_key=self.api_key
        )

        # Retry configuration
        self.retry_decorator = retry(
            stop=(
                stop_after_delay(config["llm"]["tenacity_wait_max"])
                | stop_after_attempt(config["llm"]["tenacity_stop_attempts"])
            )
        )

    @property
    def _retry(self):
        return self.retry_decorator

    def call(
        self,
        prompt: str,
        model_id: str = None,
        temperature: float = None,
        max_tokens: int = None,
        reasoning_effort: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Make a standard call to OpenRouter."""

        @self._retry
        def _call():
            completion = self.client.chat.completions.create(
                model=model_id or config["models"]["performance_low"],
                temperature=temperature or config["temperature"]["low"],
                max_tokens=max_tokens or config["llm"]["max_tokens_output"],
                reasoning_effort=reasoning_effort,
                messages=[{"role": "user", "content": prompt}],
                **kwargs,
            )
            return completion.choices[0].message.content.strip()

        return _call()

    def call_structured(
        self,
        prompt: str,
        json_schema: Dict[str, Any],
        model_id: str = None,
        temperature: float = None,
        max_tokens: int = None,
        system_message: str = None,
        **kwargs,
    ) -> str:
        """Make a structured call to OpenRouter."""

        @self._retry
        def _call():
            completion = self.client.chat.completions.create(
                model=model_id or config["models"]["performance_low"],
                temperature=temperature or config["temperature"]["low"],
                max_tokens=max_tokens or config["llm"]["max_tokens_output"],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "output",
                        "strict": True,
                        "schema": json_schema,
                    },
                },
                messages=[
                    {
                        "role": "developer",
                        "content": system_message or config["llm"]["system_message"],
                    },
                    {"role": "user", "content": prompt},
                ],
                **kwargs,
            )
            return completion.choices[0].message.content

        return _call()

    def call_with_reasoning(
        self,
        prompt: str,
        model_id: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> tuple[str, dict]:
        """Call LLM API with reasoning parameters."""

        # At the moment, only the Gemini 2.5 model support context lengths beyond 200k.
        # Here we check if the model is not Gemini 2.5 and if the token count exceeds the fallback limit.
        # If so, we switch to the fallback model.
        if "google/gemini-2.5" not in model_id or config["models"]["performance_high"]:
            token_count = TokenCounter.count_tokens(prompt)
            if token_count > config["llm"]["fallback_token_limit"]:
                custom_logger.info_console(
                    f"Token count ({token_count}) exceeds fallback limit. Using fallback model."
                )
                model_id = config["models"]["fallback"]

        custom_logger.info_console(
            f"Calling API with prompt: {prompt[:200]}... (model: {model_id or config['models']['performance_high']})"
        )

        # Since the final call is costly, we do not retry it, if it fails.
        # If you want to retry it, uncomment the decorator below.
        # @self._retry
        def _call_model():
            try:
                url = "https://openrouter.ai/api/v1/chat/completions"
                payload = {
                    "model": model_id or config["models"]["performance_high"],
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature or config["temperature"]["low"],
                    "max_tokens": max_tokens or config["llm"]["max_tokens_output"],
                    # Adjust this according to the model specifications. Details:
                    # https://openrouter.ai/docs/use-cases/reasoning-tokens
                    "reasoning": {
                        "max_tokens": -1,
                        # "effort": "high",
                    },
                }
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                response = requests.post(url, json=payload, headers=headers)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                with open(
                    f"{config['app']['save_final_docs_to']}response_{timestamp}.json",
                    "w",
                ) as f:
                    json.dump(response.json(), f)

                response = response.json()
                usage = response.get("usage", {})
                response = response["choices"][0]["message"]["content"]
                return response, usage
            except Exception as e:
                custom_logger.info_console(f"Error during final reasoning: {e}")
                return "", {}

        response, usage = _call_model()
        return response, usage


class ClientManager:
    """Manages LLM client instances."""

    _instances: Dict[str, LLMClient] = {}

    @classmethod
    def get_client(cls, provider: str = "openrouter") -> LLMClient:
        """Get or create a client instance."""
        if provider not in cls._instances:
            if provider == "openrouter":
                cls._instances[provider] = OpenRouterClient()
            else:
                raise ValueError(f"Unknown provider: {provider}")

        return cls._instances[provider]
