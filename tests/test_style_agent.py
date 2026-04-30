from fastapi.testclient import TestClient
from unittest import TestCase

from src.api_server import app
from src.style_editor import apply_style


class StyleAgentTest(TestCase):
    def test_applies_warm_style_and_counts_words(self):
        result = apply_style({"draft_markdown": "# Trip\n\n- A long day", "style": "warm_blog"})

        self.assertEqual(result["style_status"], "ok")
        self.assertIn("기록해 둔 순간", result["markdown"])
        self.assertGreater(result["word_count"], 0)

    def test_empty_draft_gets_fallback_document(self):
        result = apply_style({"draft_markdown": ""})

        self.assertIn("# Untitled", result["markdown"])

    def test_health_endpoint(self):
        client = TestClient(app)

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "style_agent")

    def test_style_endpoint(self):
        client = TestClient(app)

        response = client.post(
            "/api/v1/styles",
            json={"project_id": "sample", "draft_markdown": "# Trip\n\nBody"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["project_id"], "sample")
        self.assertEqual(response.json()["style_status"], "ok")

