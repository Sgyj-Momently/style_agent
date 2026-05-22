# style_agent

완성된 초안 Markdown에 문체(voice profile)를 입히는 FastAPI 에이전트.

## 역할

파이프라인에서 `review_agent` 다음, 최종 저장 직전에 호출된다. Spring orchestrator가 초안과 선택적으로 voice profile을 전달하면, Ollama LLM으로 해당 사용자의 말투를 모방해 초안을 다시 쓴다. LLM이 비활성이거나 중국어 출력 오류가 발생하면 결정론적 어미 치환(deterministic fallback)으로 자동 전환한다.

**입력**: 초안 Markdown + (선택) voice profile  
**출력**: 말투가 적용된 Markdown + 적용 상태 코드

## API

### `GET /health`

서비스 활성 확인.

**응답**
```json
{"status": "ok", "service": "style_agent"}
```

---

### `POST /api/v1/styles`

초안에 스타일/말투를 적용한다.

**요청 본문**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `project_id` | string | Y | 프로젝트 식별자 (최소 1자) |
| `draft_markdown` | string | Y | 스타일을 입힐 Markdown 초안 |
| `style` | string | N | `warm_blog`(기본) 또는 `concise` |
| `tone` | string | N | `style`와 동일하게 처리됨 |
| `voice_profile` | object | N | voice_profile_agent가 반환한 프로필 객체 |
| `voice_profile_id` | string | N | 내장 프리셋 ID (아래 목록 참조) |
| `deterministic_voice` | bool | N | `true`이면 LLM 없이 결정론적 어미 치환만 수행 |

**내장 프리셋 (`voice_profile_id`)**

| ID | 이름 | 설명 |
|----|------|------|
| `preset_mz` | MZ 말투 | 캐주얼, 감탄사, 줄임말 |
| `preset_manager` | 부장님 말투 | 정중하되 넉살 있는 존댓말 |
| `preset_retro` | 레트로 말투 | 구수하고 담백한 문어체 |
| `preset_formal` | 정중한 말투 | 격식 있는 존댓말 |
| `preset_emotional` | 감성 글 | 서정적, 여운 있는 문체 |
| `preset_info` | 정보형 | 사실 위주의 간결한 문체 |

**응답**

```json
{
  "project_id": "proj-123",
  "style_status": "ok_llm",
  "applied_style": "warm_blog",
  "markdown": "# 제목\n\n...",
  "word_count": 312,
  "voice_profile_id": "my-blog",
  "voice_profile_summary": "..."
}
```

**`style_status` 값**

| 값 | 의미 |
|----|------|
| `ok` | voice profile 없이 스타일만 적용 |
| `ok_llm` | Ollama LLM으로 말투 재작성 성공 |
| `ok_deterministic_voice` | 결정론적 어미 치환으로 적용 |
| `ok_fallback: ...` | LLM 실패 → 결정론적 fallback으로 전환 |

## 실행

### 로컬

```bash
pip install -r requirements.txt
uvicorn src.api_server:app --reload --port 8500
```

### Docker

```bash
# deploy/ 의 docker-compose에서 style_agent 서비스로 포함되어 있음
docker compose up --build style_agent
```

컨테이너 내부 포트는 `PORT` 환경 변수로 지정하며 기본값은 `8500`이다.

## 설정

| 이름 | 설명 | 기본값 |
|------|------|--------|
| `OLLAMA_BASE_URL` | Ollama API 엔드포인트 | `http://localhost:11434` |
| `STYLE_MODEL` | 사용할 Ollama 모델 | `qwen2.5:14b` |
| `OLLAMA_TIMEOUT_SECONDS` | Ollama 요청 타임아웃 (초) | `120` |

## 테스트

```bash
# .venv 사용 시
scripts/verify.sh

# Python 경로 지정 시
PYTHON=/usr/bin/python3 scripts/verify.sh
```

커버리지 기준: **85% 이상** (미달 시 스크립트가 0이 아닌 코드로 종료).

## 구조

```
src/
  api_server.py       # FastAPI 앱 + StyleRequest 모델 + 라우터
  style_editor.py     # apply_style() 핵심 로직, Ollama 호출, 결정론적 어미 치환,
                      # 내장 프리셋 6종 (BUILTIN_VOICE_PROFILES)
tests/
  test_style_agent.py # unittest 기반 통합/단위 테스트
scripts/
  verify.sh           # coverage run + 85% 기준 체크
requirements.txt      # fastapi, uvicorn, pydantic, httpx, coverage
```
