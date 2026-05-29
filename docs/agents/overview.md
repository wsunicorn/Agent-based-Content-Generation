# Agents Overview

Agent code nằm trong `apps/agents/`. Mỗi agent nhận `PipelineState`, cập nhật một phần state và trả state mới.

## Danh Sách Agent

| Agent | File | Gọi LLM | Vai trò |
| --- | --- | --- | --- |
| Coordinator | [coordinator.py](../../apps/agents/coordinator.py) | Có | Chuẩn hóa metadata và router quyết định bước kế tiếp. |
| ImageResearch | [image_research.py](../../apps/agents/image_research.py) | Không bắt buộc | Tìm ảnh Wikimedia/Tavily, tạo `image_assets`. |
| Research | [research.py](../../apps/agents/research.py) | Có | Tìm nguồn, scrape và tóm tắt research. |
| Outline | [outline.py](../../apps/agents/outline.py) | Có | Sinh outline structured theo content type/domain. |
| Writer | [writer.py](../../apps/agents/writer.py) | Không | Chia outline thành các `SectionWriteTask`. |
| SectionWriter | [section_writer.py](../../apps/agents/section_writer.py) | Có | Viết từng section độc lập. |
| JoinDraft | [join_draft.py](../../apps/agents/join_draft.py) | Không | Ghép sections, chèn ảnh, tạo draft. |
| Editor | [editor.py](../../apps/agents/editor.py) | Có | Biên tập draft. |
| FactChecker | [fact_checker.py](../../apps/agents/fact_checker.py) | Có | Kiểm chứng claim dựa trên sources. |
| SEO | [seo.py](../../apps/agents/seo.py) | Có | Sinh metadata SEO và chấm điểm SEO. |
| QA | [qa.py](../../apps/agents/qa.py) | Có | Chấm chất lượng cuối và đề xuất next action. |

## Shared BaseAgent

[base.py](../../apps/agents/base.py) cung cấp:

- chọn provider theo `LLM_PROVIDER`, `LLM_MODE`, agent override;
- retry với backoff;
- fallback từ local provider sang Gemini nếu `LLM_FALLBACK_TO_GEMINI=True`;
- tracking usage theo provider.

## Provider Adapters

[llm_providers.py](../../apps/agents/llm_providers.py) hỗ trợ:

- Gemini qua `langchain-google-genai`;
- Ollama qua HTTP API `/api/chat`;
- OpenAI-compatible local server, ví dụ LM Studio.

Structured output dùng Pydantic schema. Local providers nhận thêm JSON schema instruction và parse JSON trả về.

## Domain Và Content Guides

- [domain_guides.py](../../apps/agents/domain_guides.py): quy tắc theo lĩnh vực như healthcare, finance, legal.
- [content_guides.py](../../apps/agents/content_guides.py): cấu trúc khác nhau cho blog post, technical report, news article, tutorial.

Các guide này giúp prompt không chung chung và giúp QA/Editor biết tiêu chí của từng loại nội dung.

## AgentRun Logging

LangGraph wrapper trong [apps/pipeline/graph.py](../../apps/pipeline/graph.py) gọi:

- `start_agent_run`
- `complete_agent_run`
- `fail_agent_run`

Các helper này nằm trong [apps/jobs/progress.py](../../apps/jobs/progress.py), dùng để ghi log vào `AgentRun` và thống kê usage.

## Khi Thêm Agent Mới

1. Tạo file agent trong `apps/agents/`.
2. Kế thừa `BaseAgent`.
3. Thêm enum vào `AgentRun.AgentType` nếu cần lưu log.
4. Thêm field cần thiết vào `PipelineState`.
5. Thêm node/edge trong `apps/pipeline/graph.py`.
6. Thêm artifact nếu agent tạo output cần lưu lâu dài.
7. Cập nhật docs và test.
