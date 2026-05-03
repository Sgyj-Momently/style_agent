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

    def test_applies_voice_profile_hints(self):
        result = apply_style(
            {
                "draft_markdown": "# Trip\n\n오늘은 좋은 하루였다.",
                "voice_profile": {
                    "id": "my-blog",
                    "features": {
                        "sentence_endings": ["좋았어요"],
                        "tone_tags": ["polite", "expressive"],
                    },
                    "style_prompt": "사용자 말투",
                    "sample_preview": "오늘 정말 좋았어요!",
                },
            },
            llm_rewriter=lambda markdown, profile, style: (_ for _ in ()).throw(RuntimeError("offline")),
        )

        self.assertEqual(result["voice_profile_id"], "my-blog")
        self.assertIn("좋은 하루였어요!", result["markdown"])
        self.assertIn("voice-profile: my-blog", result["markdown"])
        self.assertTrue(result["style_status"].startswith("ok_fallback"))

    def test_uses_llm_rewriter_when_available(self):
        result = apply_style(
            {
                "draft_markdown": "# Trip\n\n오늘은 좋은 하루였다.",
                "voice_profile": {
                    "id": "my-blog",
                    "features": {"sentence_endings": ["좋았어요"]},
                    "style_prompt": "사용자 말투",
                },
            },
            llm_rewriter=lambda markdown, profile, style: "# Trip\n\n오늘 진짜 좋았어요.",
        )

        self.assertEqual(result["style_status"], "ok_llm")
        self.assertIn("오늘 진짜 좋았어요.", result["markdown"])

    def test_builtin_voice_profile_id_works_without_profile_payload(self):
        result = apply_style(
            {
                "draft_markdown": "# Trip\n\n오늘은 좋은 하루였다.",
                "voice_profile_id": "preset_manager",
            },
            llm_rewriter=lambda markdown, profile, style: f"# Trip\n\n{profile['name']} 적용 완료입니다.",
        )

        self.assertEqual(result["style_status"], "ok_llm")
        self.assertEqual(result["voice_profile_id"], "preset_manager")
        self.assertIn("부장님 말투 적용 완료입니다.", result["markdown"])

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
