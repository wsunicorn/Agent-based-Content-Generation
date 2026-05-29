# Tech Stack

## Backend

| Thành phần | Dependency |
| --- | --- |
| Web framework | Django 5.1 |
| REST API | Django REST Framework 3.15 |
| WebSocket/ASGI | Channels 4.1, channels-redis 4.2, Daphne 4.1 |
| Task queue | Celery 5.4 |
| Broker/channel layer | Redis 7 |
| Database | PostgreSQL 16 local qua Docker |
| Env config | django-environ |
| Test | pytest, pytest-django |

## AI Và Pipeline

| Thành phần | Dependency |
| --- | --- |
| Graph orchestration | LangGraph 0.2 |
| LLM utilities | LangChain 0.3 |
| Gemini integration | langchain-google-genai, google-generativeai |
| Local/OpenAI-compatible calls | httpx |
| Structured models | Pydantic 2 |
| Retry | tenacity |

## Search, Scrape, Export

| Thành phần | Dependency |
| --- | --- |
| Search API | tavily-python |
| HTML parsing | BeautifulSoup4, lxml |
| Browser scraping | Playwright |
| Markdown export/render | markdown2 |
| DOCX export | python-docx |
| Slugs | python-slugify |

## LLM Routing

Routing nằm trong [apps/agents/base.py](../apps/agents/base.py) và provider adapters nằm trong [apps/agents/llm_providers.py](../apps/agents/llm_providers.py).

Các biến chính:

- `LLM_PROVIDER`: `gemini`, `ollama`, `openai_compatible`, `hybrid`.
- `LLM_MODE`: `cheap`, `balanced`, `quality`.
- `LOCAL_LLM_PROVIDER`: thường là `ollama`.
- `STRUCTURED_LLM_PROVIDER`: provider cho output Pydantic/JSON.
- `LOCAL_LLM_AGENTS`: danh sách agent ưu tiên local trong hybrid/balanced.
- `LLM_AGENT_PROVIDERS`: override provider theo agent.
- `LLM_AGENT_MODELS`: override model local theo agent.
- `GEMINI_AGENT_MODELS`: override model Gemini theo agent.

Khuyến nghị local hiện tại:

```env
LLM_PROVIDER=hybrid
LLM_MODE=balanced
LOCAL_LLM_PROVIDER=ollama
STRUCTURED_LLM_PROVIDER=ollama
LLM_AGENT_PROVIDERS=research=ollama,outline=ollama,writer=ollama,section_writer=ollama,editor=ollama,fact_checker=ollama,seo=ollama,qa=ollama
LLM_AGENT_MODELS=research=qwen3:8b,outline=qwen2.5:7b,writer=qwen3:8b,section_writer=qwen3:8b,editor=qwen3:8b,fact_checker=qwen3:8b,seo=qwen2.5:7b,qa=qwen3:8b
```

## Settings Modules

| Module | Dùng cho |
| --- | --- |
| `config.settings.development` | Local dashboard, local API, `start.bat`, tests. |
| `config.settings.production` | ASGI/WSGI/Celery mặc định nếu không set env. |

`manage.py` mặc định development để tiện chạy command local. `asgi.py`, `wsgi.py`, `celery.py` mặc định production để tránh deploy nhầm dev settings.

## Không Còn Dùng

- `django-cors-headers` đã bỏ khỏi requirements vì dashboard và API chạy same-origin.
- `django-celery-beat` không được dùng vì hệ thống chưa có periodic task.
- Các tài liệu agent riêng lẻ cũ đã được gom lại vào [agents/overview.md](./agents/overview.md) để tránh lệch với code.
