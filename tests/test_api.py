import unittest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from src.adapters.provider import MultiProviderExecutor
from src.api.app import app


class TestAPI(unittest.TestCase):
    def test_health_and_models(self):
        client = TestClient(app)
        self.assertEqual(client.get("/health").status_code, 200)
        models = client.get("/models")
        self.assertEqual(models.status_code, 200)
        self.assertTrue(any(item["model_id"] == "gpt-4o-mini" for item in models.json()))

    @patch("httpx.Client")
    def test_openai_base_url_is_configurable(self, mock_client_cls):
        response = MagicMock()
        response.json.return_value = {
            "id": "local-1",
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        response.raise_for_status = MagicMock()
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value = response
        mock_client_cls.return_value = client

        executor = MultiProviderExecutor(openai_api_key="key", openai_base_url="http://gateway/v1")
        result = executor.execute("analyze", "gpt-4o-mini", "hello")

        self.assertTrue(result.success)
        self.assertEqual(client.post.call_args.args[0], "http://gateway/v1/chat/completions")


if __name__ == "__main__":
    unittest.main()
