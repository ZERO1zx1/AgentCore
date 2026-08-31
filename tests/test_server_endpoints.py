"""Integration tests for AgentCore FastAPI server endpoints."""

import unittest
from urllib.parse import quote
from fastapi.testclient import TestClient
from src.server.app import app


class TestServerEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["engine"], "AgentCore")

    def test_models_endpoint(self):
        response = self.client.get("/api/models")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("models", data)
        self.assertGreater(len(data["models"]), 0)
        # Verify both real and fake models are returned
        model_ids = [m["model_id"] for m in data["models"]]
        self.assertIn("fake-economy", model_ids)
        self.assertIn("gpt-4o-mini", model_ids)

    def test_task_creation_and_stepping(self):
        payload = {
            "task_id": "test_server_task_01",
            "prompt": "Test repository security and structure",
            "repository": ".",
            "budget": 5.0,
            "execution_mode": "AUTO",
            "provider": "fake",
        }
        res_create = self.client.post("/api/tasks", json=payload)
        self.assertEqual(res_create.status_code, 200)
        data_create = res_create.json()
        self.assertEqual(data_create["task_id"], "test_server_task_01")
        self.assertIn("manifest", data_create)
        self.assertGreater(len(data_create["work_units"]), 0)

        # The monitoring list must use the canonical manifest projection.
        res_list = self.client.get("/api/tasks")
        self.assertEqual(res_list.status_code, 200)
        listed = next(item for item in res_list.json()["tasks"] if item["task_id"] == "test_server_task_01")
        self.assertEqual(listed["source"], "local_web")
        self.assertEqual(listed["prompt"], payload["prompt"])

        # Get task details
        res_get = self.client.get("/api/tasks/test_server_task_01")
        self.assertEqual(res_get.status_code, 200)
        data_get = res_get.json()
        self.assertEqual(data_get["task_id"], "test_server_task_01")

        # Step 1
        res_step = self.client.post("/api/tasks/test_server_task_01/step")
        self.assertEqual(res_step.status_code, 200)
        data_step = res_step.json()
        self.assertIn("budget_info", data_step)

        # Run to completion
        res_run = self.client.post("/api/tasks/test_server_task_01/run")
        self.assertEqual(res_run.status_code, 200)
        data_run = res_run.json()
        self.assertEqual(data_run["status"].upper(), "COMPLETED")
        self.assertIn("report", data_run)

        # Only artifacts registered by this task can be opened.
        artifact_path = data_run["outputs"][0]
        encoded = quote(artifact_path, safe="")
        res_artifact = self.client.get(f"/api/tasks/test_server_task_01/artifacts/{encoded}")
        self.assertEqual(res_artifact.status_code, 200)

    def test_artifact_endpoint_rejects_unregistered_repository_file(self):
        response = self.client.get("/api/tasks/no-such-task/artifacts/README.md")
        self.assertEqual(response.status_code, 404)

    def test_static_index_serving(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("AgentCore ажиллаж буйг эндээс харна", response.text)
        self.assertIn("Нарийн тохиргоо", response.text)


if __name__ == "__main__":
    unittest.main()
