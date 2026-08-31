"""Unit tests for AgentCore Model Context Protocol (MCP) Server."""

import unittest
import json
from src.mcp.server import process_mcp_request, MCP_TOOLS


class TestMCPServer(unittest.TestCase):
    def test_initialize_method(self):
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        }
        res = process_mcp_request(req)
        self.assertEqual(res["jsonrpc"], "2.0")
        self.assertEqual(res["id"], 1)
        self.assertIn("serverInfo", res["result"])
        self.assertEqual(res["result"]["serverInfo"]["name"], "agentcore-mcp-server")

    def test_tools_list_method(self):
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        res = process_mcp_request(req)
        self.assertEqual(res["id"], 2)
        tools = res["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        self.assertIn("run_agentcore_task", tool_names)
        self.assertIn("get_agentcore_status", tool_names)
        self.assertIn("list_agentcore_checkpoints", tool_names)

    def test_initialized_notification_has_no_response(self):
        req = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        self.assertIsNone(process_mcp_request(req))

    def test_run_agentcore_task_fake_execution(self):
        req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "run_agentcore_task",
                "arguments": {
                    "prompt": "Test repository scan from MCP client",
                    "budget": 3.0,
                    "provider": "fake",
                },
            },
        }
        res = process_mcp_request(req)
        self.assertEqual(res["id"], 3)
        self.assertIn("content", res["result"])
        content_text = res["result"]["content"][0]["text"]
        data = json.loads(content_text)
        self.assertIn("task_id", data)
        self.assertEqual(data["status"], "COMPLETED")
        self.assertGreater(data["work_units_completed"], 0)
        checkpoints_req = {
            "jsonrpc": "2.0",
            "id": 31,
            "method": "tools/call",
            "params": {"name": "list_agentcore_checkpoints", "arguments": {}},
        }
        checkpoints = json.loads(process_mcp_request(checkpoints_req)["result"]["content"][0]["text"])
        task = next(item for item in checkpoints["checkpoints"] if item["task_id"] == data["task_id"])
        self.assertEqual(task["source"], "mcp")

    def test_list_agentcore_checkpoints(self):
        req = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "list_agentcore_checkpoints",
                "arguments": {},
            },
        }
        res = process_mcp_request(req)
        self.assertEqual(res["id"], 4)
        content_text = res["result"]["content"][0]["text"]
        data = json.loads(content_text)
        self.assertIn("checkpoints", data)

    def test_empty_prompt_is_rejected_without_execution(self):
        req = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "run_agentcore_task", "arguments": {"prompt": "   ", "provider": "fake"}},
        }
        data = json.loads(process_mcp_request(req)["result"]["content"][0]["text"])
        self.assertIn("error", data)

    def test_unknown_tool_returns_json_rpc_error(self):
        req = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "not_a_tool", "arguments": {}},
        }
        response = process_mcp_request(req)
        self.assertEqual(response["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
