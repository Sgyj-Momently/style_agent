"""Deterministic Markdown style pass."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable
from urllib import request


DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_STYLE_MODEL = "qwen2.5:14b"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 120
StyleRewriter = Callable[[str, dict[str, Any], str], str]

BUILTIN_VOICE_PROFILES: dict[str, dict[str, Any]] = {
    "preset_mz": {
        "id": "preset_mz",
        "name": "MZ 말투",
        "description": "친근하고 캐주얼한 MZ세대 스타일",
        "style_prompt": "짧고 캐주얼하게 쓴다. 감탄사, 줄임말, 생생한 반응을 자연스럽게 섞고 너무 격식 차리지 않는다.",
        "features": {
            "tone_tags": ["casual", "expressive", "short-sentence"],
            "sentence_endings": ["좋음", "미쳤음", "좋았음"],
            "frequent_words": ["진짜", "대박", "갬성", "완전", "맛있음"],
        },
        "sample_preview": "오늘 다녀온 곳 진짜 대박... 갬성 터지는 분위기에 음식도 맛있어서 또 가고 싶음",
    },
    "preset_manager": {
        "id": "preset_manager",
        "name": "부장님 말투",
        "description": "약간 격식 있고 넉살 좋은 회식 후기 스타일",
        "style_prompt": "정중하지만 살짝 넉살 있게 쓴다. 칭찬은 큼직하게 하고, 문장은 안정적인 존댓말로 마무리한다.",
        "features": {
            "tone_tags": ["polite", "warm", "confident"],
            "sentence_endings": ["좋습니다", "했습니다", "나왔습니다"],
            "frequent_words": ["역시", "아주", "제맛", "실하게", "만족스럽습니다"],
        },
        "sample_preview": "역시 이런 곳은 함께 와야 제맛입니다. 분위기도 좋고 음식도 아주 실하게 나왔습니다.",
    },
    "preset_retro": {
        "id": "preset_retro",
        "name": "레트로 말투",
        "description": "어른 세대 온라인 후기처럼 구수하고 담백한 문체",
        "style_prompt": "구수하고 담백한 존댓말로 쓴다. 과한 유행어는 피하고, 차분한 감상과 소박한 칭찬을 섞는다.",
        "features": {
            "tone_tags": ["polite", "retro", "balanced"],
            "sentence_endings": ["습니다", "네요", "좋았습니다"],
            "frequent_words": ["간만에", "참", "괜찮았습니다", "생각이", "좋았습니다"],
        },
        "sample_preview": "간만에 좋은 데 다녀왔습니다. 사진으로 보니 그때 생각이 또 나네요.",
    },
    "preset_formal": {
        "id": "preset_formal",
        "name": "정중한 말투",
        "description": "격식 있고 품격 있는 문체",
        "style_prompt": "격식 있고 정돈된 존댓말로 쓴다. 감정보다는 관찰과 평가를 차분하게 전달한다.",
        "features": {
            "tone_tags": ["polite", "formal"],
            "sentence_endings": ["습니다", "였습니다"],
            "frequent_words": ["방문한", "분위기", "완성도", "만족도"],
        },
        "sample_preview": "오늘 방문한 곳은 분위기가 매우 아늑하였으며 음식의 완성도 또한 높았습니다.",
    },
    "preset_emotional": {
        "id": "preset_emotional",
        "name": "감성 글",
        "description": "서정적이고 감성적인 문체",
        "style_prompt": "서정적인 묘사와 감각적인 표현을 사용한다. 문장은 부드럽고 여운 있게 마무리한다.",
        "features": {
            "tone_tags": ["reflective", "emotional"],
            "sentence_endings": ["했다", "같았다", "남았다"],
            "frequent_words": ["햇살", "고요한", "순간", "마음", "여운"],
        },
        "sample_preview": "햇살이 내려앉은 오후, 그 공간은 마치 시간이 멈춘 듯 고요했다...",
    },
    "preset_info": {
        "id": "preset_info",
        "name": "정보형",
        "description": "사실 위주의 깔끔한 정보 전달",
        "style_prompt": "핵심 정보를 먼저 정리하고 사실 위주로 간결하게 쓴다. 감상은 짧게 덧붙인다.",
        "features": {
            "tone_tags": ["concise", "informational"],
            "sentence_endings": ["입니다", "가능합니다"],
            "frequent_words": ["위치", "영업시간", "가격대", "추천"],
        },
        "sample_preview": "위치: 서울 강남구. 영업시간: 11:00-22:00. 가격대: 1인 15,000~25,000원.",
    },
}


def apply_style(payload: dict[str, Any], llm_rewriter: StyleRewriter | None = None) -> dict[str, Any]:
    markdown = _normalize_markdown(str(payload.get("draft_markdown") or ""))
    style = str(payload.get("style") or payload.get("tone") or "warm_blog")
    voice_profile = payload.get("voice_profile") if isinstance(payload.get("voice_profile"), dict) else None
    if voice_profile is None:
        voice_profile = BUILTIN_VOICE_PROFILES.get(str(payload.get("voice_profile_id") or ""))
    style_status = "ok"
    if not markdown:
        markdown = "# Untitled\n\n아직 작성된 본문이 없습니다."

    if style == "concise":
        markdown = _compact_bullets(markdown)
    elif style == "warm_blog":
        markdown = _add_warm_touch(markdown)

    if voice_profile:
        try:
            rewriter = llm_rewriter or _rewrite_with_ollama
            markdown = _normalize_markdown(rewriter(markdown, voice_profile, style))
            style_status = "ok_llm"
        except Exception as exc:
            markdown = _apply_voice_profile(markdown, voice_profile)
            style_status = f"ok_fallback: llm_rewrite_failed ({exc})"

    result = {
        "style_status": style_status,
        "applied_style": style,
        "markdown": markdown,
        "word_count": len(re.findall(r"\S+", markdown)),
    }
    if voice_profile:
        result["voice_profile_id"] = voice_profile.get("id")
        result["voice_profile_summary"] = voice_profile.get("style_prompt", "")
    return result


def _rewrite_with_ollama(markdown: str, profile: dict[str, Any], style: str) -> str:
    model_name = os.getenv("STYLE_MODEL", DEFAULT_STYLE_MODEL)
    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    timeout_seconds = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", str(DEFAULT_OLLAMA_TIMEOUT_SECONDS)))
    prompt = _build_voice_rewrite_prompt(markdown, profile, style)
    body = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
    }
    http_request = request.Request(
        url=f"{base_url.rstrip('/')}/api/generate",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(http_request, timeout=timeout_seconds) as response:
        response_payload = json.loads(response.read().decode("utf-8"))
    rewritten = str(response_payload.get("response") or "").strip()
    if not rewritten:
        raise ValueError("empty Ollama response")
    return _strip_markdown_fence(rewritten)


def _build_voice_rewrite_prompt(markdown: str, profile: dict[str, Any], style: str) -> str:
    compact_profile = {
        "id": profile.get("id"),
        "name": profile.get("name"),
        "description": profile.get("description"),
        "style_prompt": profile.get("style_prompt"),
        "features": profile.get("features"),
        "voice_fingerprint": profile.get("voice_fingerprint"),
        "signature_moves": profile.get("signature_moves"),
        "rewrite_rules": profile.get("rewrite_rules"),
        "do": profile.get("do"),
        "dont": profile.get("dont"),
        "sample_preview": profile.get("sample_preview"),
    }
    return f"""
당신은 한국어 블로그 글의 문체를 바꾸는 편집자다.
아래 초안의 사실, 순서, 이미지 마크다운, 제목 구조는 유지하고 말투만 사용자 말투 프로필에 가깝게 다시 써라.

규칙:
- 출력은 Markdown 본문만 반환한다. 설명, 코드블록, JSON 금지.
- 반드시 한국어로만 출력한다. 중국어, 일본어, 영어 등 다른 언어 혼용 절대 금지.
- 사진 파일명과 이미지 태그는 절대 바꾸지 않는다.
- 없는 장소, 메뉴, 가격, 감정, 사건을 새로 만들지 않는다.
- 너무 과장하지 말고, 사용자의 문장 리듬/어미/감정 표현을 따라 한다.
- 의미가 같은 문장은 자연스럽게 합치거나 나눠도 된다.
- voice_fingerprint, signature_moves, rewrite_rules, do/dont가 있으면 그 지시를 최우선으로 따른다.
- 원문의 문체가 아니라 사용자 프로필의 습관을 적용한다.

적용 스타일: {style}

사용자 말투 프로필:
{json.dumps(compact_profile, ensure_ascii=False, indent=2)}

초안 Markdown:
{markdown}
""".strip()


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:markdown|md)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    stripped = stripped.strip()
    # Qwen 모델이 중국어로 대부분 출력한 경우 fallback을 유발한다.
    cjk_count = sum(1 for ch in stripped if "\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf")
    if len(stripped) > 0 and cjk_count / len(stripped) > 0.2:
        raise ValueError(f"LLM output is predominantly Chinese ({cjk_count}/{len(stripped)} CJK chars), falling back")
    return stripped


def _normalize_markdown(markdown: str) -> str:
    lines = [line.rstrip() for line in markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    normalized: list[str] = []
    blank = False
    for line in lines:
        if not line.strip():
            if not blank:
                normalized.append("")
            blank = True
            continue
        normalized.append(line)
        blank = False
    normalized_markdown = "\n".join(normalized).strip()
    return normalized_markdown + "\n" if normalized_markdown else ""


def _compact_bullets(markdown: str) -> str:
    return re.sub(r"(?m)^- ([^\n]{90})[^\n]*$", r"- \1...", markdown)


def _add_warm_touch(markdown: str) -> str:
    lines = markdown.splitlines()
    if lines and lines[0].startswith("# ") and "기록해 둔 순간들을 차분히 따라가 봅니다." not in markdown:
        lines.insert(2, "기록해 둔 순간들을 차분히 따라가 봅니다.")
    return "\n".join(lines).strip() + "\n"


def _apply_voice_profile(markdown: str, profile: dict[str, Any]) -> str:
    features = profile.get("features") if isinstance(profile.get("features"), dict) else {}
    endings = features.get("sentence_endings") if isinstance(features.get("sentence_endings"), list) else []
    tags = features.get("tone_tags") if isinstance(features.get("tone_tags"), list) else []
    preferred_ending = _preferred_sentence_ending(endings)
    paragraphs = markdown.split("\n\n")
    rewritten = [_rewrite_paragraph(paragraph, preferred_ending, tags) for paragraph in paragraphs]
    markdown = "\n\n".join(rewritten).strip() + "\n"
    preview = str(profile.get("sample_preview") or "").strip()
    if preview and "voice-profile:" not in markdown:
        markdown += f"\n<!-- voice-profile: {profile.get('id', 'custom')} -->\n"
    return markdown


def _preferred_sentence_ending(endings: list[Any]) -> str:
    for ending in endings:
        text = str(ending)
        if text.endswith(("요", "습니다", "네요", "어요", "아요", "예요")):
            return "요"
    for ending in endings:
        text = str(ending)
        if text.endswith(("다", "함", "음")):
            return "다"
    return ""


def _rewrite_paragraph(paragraph: str, preferred_ending: str, tags: list[Any]) -> str:
    if paragraph.startswith("#") or paragraph.startswith("![") or not preferred_ending:
        return paragraph
    expressive = "expressive" in tags
    lines = []
    for line in paragraph.splitlines():
        if line.startswith("- "):
            lines.append(_rewrite_sentence_end(line, preferred_ending, expressive))
        else:
            lines.append(_rewrite_sentence_end(line, preferred_ending, expressive))
    return "\n".join(lines)


def _rewrite_sentence_end(line: str, preferred_ending: str, expressive: bool) -> str:
    stripped = line.rstrip()
    if not stripped:
        return line
    if preferred_ending == "요" and stripped.endswith(("요.", "요!", "요?")):
        return line
    if preferred_ending == "다" and stripped.endswith(("다.", "다!", "다?")):
        return line
    bullet = "- " if stripped.startswith("- ") else ""
    body = stripped[2:] if bullet else stripped
    if len(body) < 8:
        return line
    body = re.sub(r"(입니다|합니다|했습니다|되었습니다|있습니다|없습니다)[.!?]*$", "이에요.", body)
    if preferred_ending == "요":
        body = re.sub(r"였다[.!?]*$", "였어요.", body)
        body = re.sub(r"이었다[.!?]*$", "이었어요.", body)
        body = re.sub(r"다[.!?]*$", "요.", body)
        body = re.sub(r"음[.!?]*$", "어요.", body)
        if not body.endswith(("요.", "요!", "요?")) and re.search(r"[가-힣]$", body):
            body += "요."
    elif preferred_ending == "다" and not body.endswith(("다.", "다!", "다?")):
        body = re.sub(r"요[.!?]*$", "다.", body)
    if expressive and body.endswith("요."):
        body = body[:-1] + "!"
    return bullet + body
