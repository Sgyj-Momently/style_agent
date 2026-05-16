import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from unittest import TestCase

from src.api_server import app
from src.style_editor import (
    _build_voice_rewrite_prompt,
    _rewrite_sentence_end,
    _rewrite_with_ollama,
    _strip_markdown_fence,
    apply_style,
)


class StyleAgentTest(TestCase):
    def test_applies_warm_style_and_counts_words(self):
        result = apply_style({"draft_markdown": "# Trip\n\n- A long day", "style": "warm_blog"})

        self.assertEqual(result["style_status"], "ok")
        self.assertIn("기록해 둔 순간", result["markdown"])
        self.assertGreater(result["word_count"], 0)

    def test_concise_style_compacts_long_bullet(self):
        result = apply_style(
            {
                "draft_markdown": "# Trip\n\n- " + ("아주 긴 설명 " * 20),
                "style": "concise",
            }
        )

        self.assertIn("...", result["markdown"])

    def test_warm_style_does_not_duplicate_intro(self):
        markdown = "# Trip\n\n기록해 둔 순간들을 차분히 따라가 봅니다.\n\n본문"

        result = apply_style({"draft_markdown": markdown, "style": "warm_blog"})

        self.assertEqual(result["markdown"].count("기록해 둔 순간들을 차분히 따라가 봅니다."), 1)

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

    def test_can_force_deterministic_voice_without_llm(self):
        result = apply_style(
            {
                "draft_markdown": "# Trip\n\n오늘은 좋은 하루였다.",
                "deterministic_voice": True,
                "voice_profile": {
                    "id": "my-blog",
                    "features": {
                        "sentence_endings": ["좋았어요"],
                        "tone_tags": ["polite"],
                    },
                    "style_prompt": "사용자 말투",
                    "sample_preview": "오늘 좋았어요.",
                },
            },
            llm_rewriter=lambda markdown, profile, style: "# Trip\n\n호출되면 안 됩니다.",
        )

        self.assertEqual(result["style_status"], "ok_deterministic_voice")
        self.assertIn("좋은 하루였어요.", result["markdown"])
        self.assertIn("voice-profile: my-blog", result["markdown"])

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

    def test_deterministic_voice_handles_plain_da_ending_and_no_preview(self):
        result = apply_style(
            {
                "draft_markdown": "# Trip\n\n오늘은 좋았어요.",
                "deterministic_voice": True,
                "voice_profile": {
                    "id": "plain-blog",
                    "features": {
                        "sentence_endings": ["좋았다"],
                        "tone_tags": [],
                    },
                },
            },
        )

        self.assertEqual(result["style_status"], "ok_deterministic_voice")
        self.assertIn("오늘은 좋았다.", result["markdown"])
        self.assertNotIn("voice-profile:", result["markdown"])

    def test_rewrite_sentence_end_keeps_short_blank_and_finished_lines(self):
        self.assertEqual(_rewrite_sentence_end("", "요", False), "")
        self.assertEqual(_rewrite_sentence_end("짧다", "요", False), "짧다")
        self.assertEqual(_rewrite_sentence_end("이미 좋아요.", "요", False), "이미 좋아요.")
        self.assertEqual(_rewrite_sentence_end("이미 좋다.", "다", False), "이미 좋다.")

    def test_strip_markdown_fence_and_rejects_chinese_output(self):
        self.assertEqual(_strip_markdown_fence("```markdown\n# 제목\n```"), "# 제목")
        with self.assertRaises(ValueError):
            _strip_markdown_fence("这是中文输出这是中文输出")

    def test_build_voice_rewrite_prompt_contains_profile_and_rules(self):
        prompt = _build_voice_rewrite_prompt(
            "# Trip\n\n본문",
            {
                "id": "my-blog",
                "name": "내 말투",
                "voice_fingerprint": {"persona": "담백함"},
                "rewrite_rules": ["짧게 쓴다"],
            },
            "warm_blog",
        )

        self.assertIn("내 말투", prompt)
        self.assertIn("짧게 쓴다", prompt)
        self.assertIn("# Trip", prompt)

    @patch("src.style_editor.request.urlopen")
    def test_rewrite_with_ollama_sends_request_and_strips_fence(self, mock_urlopen):
        mock_urlopen.return_value = _FakeUrlopenResponse({"response": "```markdown\n# Trip\n\n좋았어요.\n```"})

        rewritten = _rewrite_with_ollama("# Trip\n\n본문", {"id": "my-blog"}, "warm_blog")

        self.assertEqual(rewritten, "# Trip\n\n좋았어요.")
        body = json.loads(mock_urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(body["model"], "qwen2.5:14b")
        self.assertFalse(body["stream"])

    @patch("src.style_editor.request.urlopen")
    def test_rewrite_with_ollama_rejects_empty_response(self, mock_urlopen):
        mock_urlopen.return_value = _FakeUrlopenResponse({"response": ""})

        with self.assertRaises(ValueError):
            _rewrite_with_ollama("# Trip\n\n본문", {"id": "my-blog"}, "warm_blog")

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

    def test_style_endpoint_supports_deterministic_voice(self):
        client = TestClient(app)

        response = client.post(
            "/api/v1/styles",
            json={
                "project_id": "sample",
                "draft_markdown": "# Trip\n\n오늘은 좋은 하루였다.",
                "deterministic_voice": True,
                "voice_profile": {
                    "id": "my-blog",
                    "features": {"sentence_endings": ["좋았어요"]},
                    "sample_preview": "오늘 좋았어요.",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["style_status"], "ok_deterministic_voice")
        self.assertEqual(response.json()["voice_profile_id"], "my-blog")


class _FakeUrlopenResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")
