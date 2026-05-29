# Checklist nâng cấp hệ thống Multi-Agent Content Generation

Mục tiêu: biến project hiện tại từ pipeline nhiều bước thành hệ thống multi-agent đúng nghĩa, có orchestration tốt bằng LangGraph, giảm chi phí Gemini bằng LLM local, cải thiện chất lượng nội dung, và sẵn sàng deploy.

---

## Phase 1 - Nền tảng LLM Provider

- [x] Tạo abstraction `LLMProvider` dùng chung cho toàn bộ agent.
- [x] Hỗ trợ provider `gemini`.
- [x] Hỗ trợ provider `ollama`.
- [x] Hỗ trợ provider OpenAI-compatible cho LM Studio hoặc server local khác.
- [x] Thêm cấu hình vào `.env.example`:
  - [x] `LLM_MODE=cheap|balanced|quality`
  - [x] `LLM_PROVIDER=gemini|ollama|openai_compatible|hybrid`
  - [x] `OLLAMA_BASE_URL=http://localhost:11434`
  - [x] `OLLAMA_MODEL=qwen2.5:7b`
  - [x] `OPENAI_COMPATIBLE_BASE_URL=http://localhost:1234/v1`
  - [x] `OPENAI_COMPATIBLE_MODEL=local-model`
- [x] Dùng local LLM cho các bước tốn token: Writer, Editor, draft QA.
- [x] Cho phép cấu hình provider/model theo từng agent bằng `LLM_AGENT_PROVIDERS` và `LLM_AGENT_MODELS`.
- [x] Chuyển phase 1 sang local-first: Research, Outline, Writer, Editor, FactChecker, SEO, QA đều dùng Ollama mặc định.
- [x] Giữ Gemini làm fallback rẻ bằng `gemini-3.1-flash-lite` khi local LLM lỗi hoặc cần structured output ổn định hơn.
- [x] Thêm fallback: local LLM lỗi thì chuyển sang Gemini nếu có key.
- [x] Log riêng số call local và số call Gemini.
- [x] Chạy đúng hạ tầng dev với Postgres + Redis + Celery worker.
- [x] Smoke test web end-to-end trên Postgres:
  - [x] Job completed qua API/web.
  - [x] `llm_usage_by_provider = {"ollama": {"calls": 11, "tokens": 0}}`.
  - [x] QA score 85.
  - [x] Export Markdown trả HTTP 200.
- [x] Chọn và test model local mặc định cho phase 1:
  - [x] `qwen2.5:7b` - cân bằng tốt cho tiếng Việt, viết bài, chỉnh sửa và JSON.
- [x] Nâng cấu hình sang multi-model local pack:
  - [x] Research: `qwen3:8b`
  - [x] Outline: `qwen2.5:7b`
  - [x] Writer: `qwen3:8b`
  - [x] Editor: `qwen3:8b`
  - [x] FactChecker: `qwen3:8b`
  - [x] SEO: `qwen2.5:7b`
  - [x] QA: `qwen3:8b`
  - [x] Fast/local fallback pack: `qwen2.5:3b`
  - [x] Embedding/RAG pack: `nomic-embed-text-v2-moe`
  - [x] Auto image-search không cần vision model mặc định.
- [x] Thêm command `python manage.py check_ollama_models` để kiểm tra model còn thiếu.
- [x] Tắt thinking mặc định cho Qwen3 bằng `OLLAMA_THINK=False` để smoke test/job ngắn không bị kéo quá lâu.
- [x] Smoke test multi-model local:
  - [x] Research/Writer/Editor/FactChecker/QA dùng `qwen3:8b`.
  - [x] Outline/SEO dùng `qwen2.5:7b`.
  - [x] Job completed, 251 words, QA score 87.
  - [x] `llm_usage_by_provider = {"ollama": {"calls": 11, "tokens": 0}}`.
  - [x] Export Markdown trả HTTP 200.
- [ ] Benchmark thêm model local nếu còn dung lượng:
  - [ ] `qwen2.5:3b` nếu cần tiết kiệm RAM/dung lượng.
  - [ ] `deepseek-r1:1.5b` để so sánh tốc độ/chi phí.
  - [ ] `deepseek-r1:8b` nếu cần reasoning mạnh hơn.
  - [ ] `qwen2.5:14b` nếu máy đủ RAM/VRAM.

---

## Phase 2 - Multi-Agent thật bằng LangGraph

- [x] Tách `WriterAgent` hiện tại thành writer planner và writer theo section.
- [x] Tạo `SectionWriterAgent`.
- [x] Xử lý intro như một section riêng.
- [x] Xử lý conclusion như một section riêng.
- [x] Mỗi writer nhận input riêng:
  - [x] `section_id`
  - [x] `heading`
  - [x] `brief`
  - [x] `key_points`
  - [x] `target_words`
  - [x] `relevant_sources`
  - [x] `content_type_guide`
- [x] Thêm node `join_draft` để ghép các section đúng thứ tự outline.
- [x] Refactor graph từ tuyến tính sang fan-out/fan-in:
  - [x] `Outline -> Writer sections`
  - [x] `Writer sections -> JoinDraft`
  - [x] `JoinDraft -> Editor`
- [x] Cho phép chạy writers song song khi dùng local LLM hoặc provider trả phí.
- [x] Giới hạn concurrency bằng `MAX_PARALLEL_WRITERS`.
- [x] Thêm `MAX_PARALLEL_WRITERS` vào settings.
- [x] Đảm bảo graph vẫn chạy được trên Windows/Celery solo.
- [x] Smoke test Phase 2:
  - [x] Sync command completed: 5 section writer tasks, 286 words, QA score 91, 10 Ollama calls.
  - [x] API/Celery completed: 272 words, QA score 92, 11 Ollama calls, export Markdown HTTP 200.

---

## Phase 3 - Coordinator và Router thông minh

- [x] Chuyển `CoordinatorAgent` từ agent hình thức thành router/orchestrator thực sự.
- [x] Thêm routing sau mỗi quality gate.
- [x] QA không chỉ trả pass/fail, mà trả:
  - [x] `decision`
  - [x] `next_action`
  - [x] `target_agent`
  - [x] `target_section_ids`
  - [x] `issues`
  - [x] `revision_instructions`
- [x] Các `next_action` cần hỗ trợ:
  - [x] `approve`
  - [x] `redo_research`
  - [x] `redo_outline`
  - [x] `rewrite_section`
  - [x] `revise_editor`
  - [x] `redo_fact_check`
  - [x] `redo_seo`
  - [x] `fail_with_warning`
- [x] Nếu thiếu nguồn hoặc evidence yếu, quay lại `ResearchAgent`.
- [x] Nếu outline sai format, quay lại `OutlineAgent`.
- [x] Nếu section yếu, chỉ chạy lại section writer đó.
- [x] Nếu văn phong kém, quay lại `EditorAgent`.
- [x] Nếu metadata SEO yếu, chỉ chạy lại `SEOAgent`.
- [x] Giới hạn retry theo từng agent.
- [x] Giới hạn retry toàn job.
- [x] Lưu lý do revision vào DB.
- [x] Smoke test Phase 3:
  - [x] Sync full gate completed: 10 Ollama calls, QA score 91.
  - [x] API/Celery completed: 22 Ollama calls, QA score 84, 2 revisions saved.
  - [x] Export Markdown trả HTTP 200.

---

## Phase 4 - State, Logging và Observability

- [ ] Mở rộng `PipelineState` để lưu output theo từng agent.
- [ ] Lưu `agent_outputs`.
- [ ] Lưu `agent_errors`.
- [ ] Lưu `quality_scores`.
- [ ] Lưu `revision_targets`.
- [ ] Lưu `source_map`.
- [x] Ghi `AgentRun` thật cho từng agent/node.
- [x] Ghi thời gian bắt đầu/kết thúc từng agent.
- [x] Ghi prompt snapshot ngắn gọn, tránh lưu quá dài.
- [x] Ghi response snapshot ngắn gọn.
- [x] Ghi số call, input token, output token nếu provider trả về.
- [x] Ghi `Revision` thật khi QA/router yêu cầu sửa.
- [x] Hiển thị timeline agent trên dashboard.
- [x] Hiển thị agent nào chạy lại trong revision.
- [ ] Hiển thị thời gian và chi phí từng agent.
- [x] Smoke test Phase 4:
  - [x] Khi job đang chạy, API đã trả `agent_runs` realtime với trạng thái `running/completed`.
  - [x] Job completed: 35 AgentRun, 22 Ollama calls, QA score 91, 2 revisions saved.
  - [x] Export Markdown trả HTTP 200.

---

## Phase 5 - Content Templates theo loại bài

- [x] Tạo template riêng cho `blog_post`.
- [x] Tạo template riêng cho `technical_report`.
- [x] Tạo template riêng cho `news_article`.
- [x] Tạo template riêng cho `tutorial`.
- [x] Blog post cần có:
  - [x] Hook
  - [x] Reader problem
  - [x] Practical sections
  - [x] Examples
  - [x] Takeaways hoặc CTA
- [x] Technical report cần có:
  - [x] Executive summary
  - [x] Scope/methodology
  - [x] Findings
  - [x] Evidence
  - [x] Limitations
  - [x] Recommendations
- [x] News article cần có:
  - [x] Lead theo who/what/when/where/why
  - [x] Context
  - [x] Attributed viewpoints
  - [x] Impact
  - [x] Background
- [x] Tutorial cần có:
  - [x] Prerequisites
  - [x] Step-by-step sections
  - [x] Examples
  - [x] Troubleshooting
  - [x] Next steps
- [x] Outline Agent phải chọn template theo `content_type`.
- [x] Writer phải tuân thủ template.
- [x] Editor kiểm tra format theo template.
- [x] QA có điểm `format_adherence`.

---

## Phase 6 - Domain-Specific Assistant

- [x] Thêm field `domain` cho Job.
- [x] Các domain ban đầu:
  - [x] Tech
  - [x] Marketing
  - [x] Education
  - [x] Finance
  - [x] Healthcare
  - [x] Legal
- [x] Tạo `domain_guides`.
- [x] Tạo `style_guides`.
- [x] Tạo `forbidden_claims` hoặc cảnh báo theo domain nhạy cảm.
- [x] Thêm domain-specific source preference.
- [x] Thêm domain terminology/glossary.
- [x] Prompt của Research/Writer/Editor/QA nhận domain guide.
- [x] UI đổi từ generic "AI Content Pipeline" sang domain-focused assistant.
- [x] Cho user chọn domain ở form tạo job.
- [x] Cho user chọn audience/tone rõ ràng.

---

## Phase 7 - Research và Fact-check mạnh hơn

- [x] Cache Tavily/search result theo topic và keywords.
- [x] Cache nội dung scrape theo URL.
- [x] Lưu source document thành artifact riêng.
- [ ] Research output nên có structured fields:
  - [ ] `facts`
  - [ ] `statistics`
  - [ ] `claims`
  - [ ] `quotes`
  - [ ] `sources`
  - [ ] `source_credibility`
  - [ ] `source_dates`
- [x] FactChecker map claim về source cụ thể.
- [x] Claim không có source phải bị flag.
- [ ] Cho phép Editor loại bỏ hoặc viết lại claim không kiểm chứng được.
- [ ] Thêm source confidence score.
- [ ] Thêm source recency score.
- [ ] Thêm source allowlist/blocklist.
- [x] Thêm chế độ không web search khi không có Tavily key.
- [x] Nếu research yếu, router quay lại Research với query mới.

---

## Phase 8 - Auto Image Research

- [x] Gỡ hướng upload PDF/image/audio/video khỏi form tạo job.
- [x] Thêm artifact type `image_assets` cho ảnh tự tìm được.
- [x] Tạo `ImageResearchAgent` chạy tự động từ topic/domain/keywords.
- [x] Dùng nguồn miễn phí, có thông tin license/attribution rõ ràng: Wikimedia Commons.
- [x] Tự sinh `alt_text`, caption, attribution, license và source URL cho mỗi ảnh.
- [x] Tự chèn ảnh vào draft sau phần mở bài và các section thân bài.
- [x] Editor được yêu cầu giữ nguyên Markdown image block và attribution.
- [x] QA tự gắn lại ảnh nếu model editor vô tình làm rơi block ảnh.
- [x] Export Markdown/HTML/DOCX kèm danh sách nguồn ảnh.
- [x] Dashboard hiển thị node `image_research` và số ảnh tìm được realtime.
- [ ] Có thêm UI bật/tắt auto image search theo từng job nếu cần.

---

## Phase 9 - Tối ưu chi phí và thời gian

- [ ] Track token thật từ response metadata.
- [ ] Tính `cost_estimate_usd` theo provider.
- [ ] Lưu cost theo job.
- [ ] Lưu cost theo agent.
- [ ] Cache output từng agent theo hash input.
- [ ] Nếu input không đổi, cho phép reuse artifact cũ.
- [x] Thêm mode `fast`.
- [x] Thêm mode `standard`.
- [x] Thêm mode `strict`/`high_quality`.
- [x] Fast mode bỏ bớt FactChecker hoặc QA chuyên sâu.
- [x] Standard mode dùng local writer/editor và Gemini structured tasks.
- [ ] High quality mode tăng source count, fact-check kỹ hơn, có revision nhiều hơn.
- [ ] Không chạy SEO nếu user không cần SEO.
- [ ] Không chạy FactChecker nếu bài creative/non-factual.
- [ ] Hiển thị ETA trước khi submit job.
- [ ] Hiển thị số Gemini calls dự kiến.

---

## Phase 10 - Dashboard và UX

- [ ] Tách CSS khỏi `templates/dashboard/index.html` sang static file.
- [ ] Tách JS khỏi `templates/dashboard/index.html` sang static file.
- [ ] Tách CSS/JS của `job_detail.html`.
- [x] Hiển thị agent timeline rõ hơn.
- [x] Hiển thị sources/evidence panel.
- [x] Hiển thị outline trước khi viết.
- [x] Cho user approve/edit outline trước khi chạy writer.
- [x] Cho user regenerate từng section.
- [ ] Cho user chọn local/Gemini/balanced mode.
- [ ] Cho user chọn content template.
- [ ] Cho user xem QA report theo từng tiêu chí.
- [ ] Cho user xem fact-check report.
- [ ] Cho user xem SEO metadata và sửa thủ công.
- [ ] Cho phép export:
  - [ ] Markdown
  - [ ] HTML
  - [ ] DOCX
  - [ ] PDF
- [x] Thêm trạng thái worker/Redis/DB trên health panel.

---

## Phase 11 - Deploy-ready

- [ ] Không hardcode `DJANGO_SETTINGS_MODULE=config.settings.development` trong ASGI.
- [ ] Không hardcode `DJANGO_SETTINGS_MODULE=config.settings.development` trong Celery.
- [ ] Đọc settings từ environment khi deploy.
- [ ] Thêm `CSRF_TRUSTED_ORIGINS`.
- [ ] Thêm `SECURE_PROXY_SSL_HEADER`.
- [ ] Cấu hình `ALLOWED_HOSTS` production rõ ràng.
- [ ] Thêm Dockerfile production.
- [ ] Thêm `docker-compose.prod.yml`.
- [ ] Thêm startup command cho web:
  - [ ] migrate
  - [ ] collectstatic
  - [ ] start Daphne
- [ ] Thêm startup command cho worker:
  - [ ] start Celery worker
- [ ] Tách service:
  - [ ] Web
  - [ ] Worker
  - [ ] Redis
  - [ ] Postgres
- [ ] Thêm health check endpoint đầy đủ.
- [ ] Thêm deployment notes cho Render.
- [ ] Thêm deployment notes cho Railway.
- [ ] Ghi rõ local LLM không phù hợp free hosting nếu không có máy riêng/VPS đủ mạnh.
- [ ] Nếu deploy public, thêm auth hoặc simple password protection.

---

## Phase 12 - Testing và Reliability

- [ ] Unit test cho từng agent bằng mock LLM.
- [ ] Test `LLMProvider` Gemini.
- [ ] Test `LLMProvider` Ollama bằng mock HTTP.
- [ ] Test fallback local -> Gemini.
- [ ] Test LangGraph routing.
- [ ] Test QA fail quay về đúng node.
- [ ] Test rewrite một section không chạy lại toàn bài.
- [ ] Test export Markdown.
- [ ] Test export HTML.
- [ ] Test export DOCX.
- [ ] Test WebSocket progress có `detail`.
- [ ] Test cancel job.
- [ ] Test không có Tavily key vẫn chạy được.
- [ ] Test không có Gemini key nhưng dùng local LLM vẫn chạy một phần.
- [ ] Thêm fixtures sample output để demo không tốn LLM call.
- [ ] Thêm CI:
  - [ ] `python manage.py check`
  - [ ] `pytest`
  - [ ] lint cơ bản

---

## Phase 13 - Security và vận hành

- [ ] Rotate mọi API key từng xuất hiện trong repo hoặc file example.
- [ ] Đảm bảo `.env` không bị commit.
- [ ] Không log API key.
- [ ] Không log full prompt nếu chứa dữ liệu nhạy cảm.
- [ ] Sanitize scraped content để giảm prompt injection.
- [ ] Giới hạn số source mỗi job.
- [ ] Giới hạn target words.
- [ ] Giới hạn số revision.
- [ ] Rate limit API tạo job.
- [ ] Nếu cho nhập URL, chặn SSRF/internal network.
- [ ] Thêm timeout scrape.
- [ ] Thêm timeout từng LLM call.
- [ ] Thêm audit log cho job public.

---

## Thứ tự triển khai khuyến nghị

1. [x] LLM provider abstraction và Ollama/LM Studio local.
2. [x] Refactor LangGraph thành fan-out/fan-in với section writers.
3. [x] QA Router và revision quay về đúng agent.
4. [x] AgentRun/Revision logging thật.
5. [x] Content templates và domain guide.
6. [ ] Research/Fact-check nâng cấp.
7. [ ] Dashboard UX: outline review, section regenerate, evidence panel.
8. [ ] Deploy-ready config và Docker.
9. [ ] Tests và CI.
10. [x] Auto image research.
