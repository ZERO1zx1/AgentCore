"""Production-ready Multi-Provider Executor for AgentCore.
Supports OpenAI, Anthropic, Google Gemini, Ollama (Local $0), and Custom HTTP endpoints.
Implements OperationExecutor and returns canonical ExecutionResult.
"""

from typing import Dict, Any, Optional, List
from decimal import Decimal
import os
import time
import json
import httpx

from src.core.executor import OperationExecutor
from src.core.execution_result import ExecutionResult


class MultiProviderExecutor(OperationExecutor):
    """Unified provider-backed executor supporting multiple LLM backends.

    Reads API keys from environment or explicit arguments:
    - OPENAI_API_KEY for OpenAI models (gpt-4o, gpt-4o-mini)
    - ANTHROPIC_API_KEY for Anthropic models (claude-3-5-sonnet, claude-3-5-haiku)
    - GEMINI_API_KEY for Google Gemini models (gemini-1.5-flash, gemini-2.0-flash)
    - OLLAMA_BASE_URL for Local models (defaults to http://localhost:11434)
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 60.0,
    ):
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.ollama_base_url = (ollama_base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.custom_headers = custom_headers or {}
        self.timeout_seconds = timeout_seconds

    def execute(
        self,
        unit_type: str,
        model_id: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """Executes the given unit with the specified model."""
        context = context or {}
        start_time = time.perf_counter()

        provider = self._infer_provider(model_id)

        try:
            if provider == "ollama":
                result = self._execute_ollama(model_id, prompt, context)
            elif provider == "openai":
                result = self._execute_openai(model_id, prompt, context)
            elif provider == "anthropic":
                result = self._execute_anthropic(model_id, prompt, context)
            elif provider == "gemini":
                result = self._execute_gemini(model_id, prompt, context)
            elif provider == "fake":
                result = self._execute_fake(unit_type, model_id, prompt, context)
            else:
                # Default to OpenAI-compatible endpoint
                result = self._execute_openai(model_id, prompt, context)

            latency_ms = int((time.perf_counter() - start_time) * 1000)
            result.metadata["latency_ms"] = latency_ms
            return result

        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return ExecutionResult(
                success=False,
                error=f"{provider.upper()} execution error: {str(exc)}",
                provider=provider,
                model_id=model_id,
                metadata={"latency_ms": latency_ms},
                usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            )

    def _infer_provider(self, model_id: str) -> str:
        """Infers provider name from model_id prefix or known naming patterns."""
        model_lower = model_id.lower()
        if model_lower.startswith("ollama/") or "ollama" in model_lower:
            return "ollama"
        if model_lower.startswith("fake-") or model_lower == "fake":
            return "fake"
        if model_lower.startswith("gpt-") or model_lower.startswith("o1") or model_lower.startswith("o3") or "openai" in model_lower:
            return "openai"
        if model_lower.startswith("claude-") or "anthropic" in model_lower:
            return "anthropic"
        if model_lower.startswith("gemini-") or "gemini" in model_lower:
            return "gemini"
        return "openai"

    def _execute_ollama(self, model_id: str, prompt: str, context: Dict[str, Any]) -> ExecutionResult:
        """Executes a local model via Ollama HTTP API (Tier 0 - $0 cost)."""
        clean_model = model_id.replace("ollama/", "")
        endpoint = f"{self.ollama_base_url}/api/generate"

        payload = {
            "model": clean_model,
            "prompt": prompt,
            "stream": False,
        }

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()

        output_text = data.get("response", "")
        prompt_tokens = data.get("prompt_eval_count", max(1, len(prompt) // 4))
        completion_tokens = data.get("eval_count", max(1, len(output_text) // 4))

        return ExecutionResult(
            success=True,
            output_text=output_text,
            usage={
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            provider="ollama",
            model_id=model_id,
            metadata={
                "actual_cost": "0.0",  # Local offline execution is $0
                "cost_source": "provider",
            },
        )

    def _execute_openai(self, model_id: str, prompt: str, context: Dict[str, Any]) -> ExecutionResult:
        """Executes an OpenAI model via REST API."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")

        endpoint = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json",
            **self.custom_headers,
        }

        messages = [{"role": "user", "content": prompt}]

        payload = {
            "model": model_id,
            "messages": messages,
        }

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        choice = data.get("choices", [{}])[0]
        output_text = choice.get("message", {}).get("content", "")
        usage_data = data.get("usage", {})
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", prompt_tokens + completion_tokens)

        return ExecutionResult(
            success=True,
            output_text=output_text,
            usage={
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            provider="openai",
            model_id=model_id,
            provider_request_id=data.get("id", ""),
        )

    def _execute_anthropic(self, model_id: str, prompt: str, context: Dict[str, Any]) -> ExecutionResult:
        """Executes an Anthropic Claude model via Messages API."""
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured.")

        endpoint = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            **self.custom_headers,
        }

        payload = {
            "model": model_id,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content_blocks = data.get("content", [])
        output_text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
        usage_data = data.get("usage", {})
        prompt_tokens = usage_data.get("input_tokens", 0)
        completion_tokens = usage_data.get("output_tokens", 0)

        return ExecutionResult(
            success=True,
            output_text=output_text,
            usage={
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            provider="anthropic",
            model_id=model_id,
            provider_request_id=data.get("id", ""),
        )

    def _execute_gemini(self, model_id: str, prompt: str, context: Dict[str, Any]) -> ExecutionResult:
        """Executes a Google Gemini model via REST API."""
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")

        clean_model = model_id.replace("models/", "")
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={self.gemini_api_key}"
        headers = {"Content-Type": "application/json", **self.custom_headers}

        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates", [{}])
        parts = candidates[0].get("content", {}).get("parts", [{}])
        output_text = parts[0].get("text", "") if parts else ""

        usage_metadata = data.get("usageMetadata", {})
        prompt_tokens = usage_metadata.get("promptTokenCount", 0)
        completion_tokens = usage_metadata.get("candidatesTokenCount", 0)
        total_tokens = usage_metadata.get("totalTokenCount", prompt_tokens + completion_tokens)

        return ExecutionResult(
            success=True,
            output_text=output_text,
            usage={
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            provider="gemini",
            model_id=model_id,
        )

    def _execute_fake(self, unit_type: str, model_id: str, prompt: str, context: Dict[str, Any]) -> ExecutionResult:
        """Deterministic fake execution for testing."""
        return ExecutionResult(
            success=True,
            output_text=f"MultiProviderExecutor (fake mode) output for {unit_type} using {model_id}",
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            provider="fake",
            model_id=model_id,
        )
