"""Unit tests for MultiProviderExecutor."""

import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal

from src.adapters.provider import MultiProviderExecutor
from src.core.execution_result import ExecutionResult


class TestMultiProviderExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = MultiProviderExecutor(
            openai_api_key="test-openai-key",
            anthropic_api_key="test-anthropic-key",
            gemini_api_key="test-gemini-key",
            ollama_base_url="http://localhost:11434",
        )

    def test_provider_inference(self):
        self.assertEqual(self.executor._infer_provider("ollama/qwen2.5-coder"), "ollama")
        self.assertEqual(self.executor._infer_provider("gpt-4o"), "openai")
        self.assertEqual(self.executor._infer_provider("claude-3-5-sonnet"), "anthropic")
        self.assertEqual(self.executor._infer_provider("gemini-1.5-flash"), "gemini")
        self.assertEqual(self.executor._infer_provider("fake-economy"), "fake")

    def test_fake_execution(self):
        result = self.executor.execute("code", "fake-standard", "Test prompt")
        self.assertTrue(result.success)
        self.assertEqual(result.provider, "fake")
        self.assertEqual(result.model_id, "fake-standard")
        self.assertIn("MultiProviderExecutor (fake mode)", result.output_text)
        self.assertGreater(result.usage["total_tokens"], 0)

    def test_missing_api_key_fails_safely(self):
        no_key_executor = MultiProviderExecutor(openai_api_key="")
        result = no_key_executor.execute("code", "gpt-4o", "Test prompt")
        self.assertFalse(result.success)
        self.assertIn("OPENAI_API_KEY is not configured", result.error)

    @patch("httpx.Client")
    def test_ollama_mock_execution(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": "Ollama generated code",
            "prompt_eval_count": 25,
            "eval_count": 40,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = self.executor.execute("code", "ollama/qwen2.5-coder", "Write quicksort")
        self.assertTrue(result.success)
        self.assertEqual(result.provider, "ollama")
        self.assertEqual(result.output_text, "Ollama generated code")
        self.assertEqual(result.usage["input_tokens"], 25)
        self.assertEqual(result.usage["output_tokens"], 40)
        self.assertEqual(result.metadata.get("actual_cost"), "0.0")

    @patch("httpx.Client")
    def test_openai_mock_execution(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "chatcmpl-test1234",
            "choices": [{"message": {"content": "OpenAI generated analysis"}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = self.executor.execute("analyze", "gpt-4o-mini", "Analyze architecture")
        self.assertTrue(result.success)
        self.assertEqual(result.provider, "openai")
        self.assertEqual(result.output_text, "OpenAI generated analysis")
        self.assertEqual(result.usage["total_tokens"], 200)
        self.assertEqual(result.provider_request_id, "chatcmpl-test1234")


if __name__ == "__main__":
    unittest.main()
