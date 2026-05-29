# Luồng Công Việc Chi Tiết (Detailed Workflow)

Tài liệu này hướng dẫn chi tiết từng bước xử lý dữ liệu và cách các Agent phối hợp nhịp nhàng trong đồ thị LangGraph của hệ thống **Domain LLM Assistant** để tạo ra một bài viết hoàn chỉnh đạt tiêu chuẩn cao.

---

## 1. Sơ đồ luồng xử lý tổng thể

```
                   Người dùng nhập thông tin (Topic, Domain, Keywords...)
                                           │
                                           ▼
                                    [Coordinator]
                         (Khởi tạo cấu hình và phân bổ tham số)
                                           │
                                           ├───► Nếu dàn ý đã được duyệt trước đó
                                           │     │
                                           │     ▼
                                           │  [Writer] (Lập kế hoạch phân chia phần)
                                           │
                                           └───► Nếu chạy lần đầu tiên
                                                 │
                                                 ▼
                                          [ImageResearch]
                                    (Tìm kiếm ảnh Wikimedia Commons)
                                                 │
                                                 ▼
                                            [Research]
                                      (Cào dữ liệu từ internet)
                                                 │
                                                 ▼
                                            [Outline]
                                     (Tạo dàn bài viết chi tiết)
                                                 │
                                                 ▼
                                        [Chờ duyệt Outline]
                                 (Gửi về giao diện UI chờ duyệt)
                                                 │
                                                 ▼ (Sau khi người dùng phê duyệt)
                                              [Writer]
                                                 │
                                                 ▼
                                        [SectionWriters*]
                              (Viết các phần song song bằng Celery)
                                                 │
                                                 ▼
                                            [JoinDraft]
                                (Ghép nối và tự động chèn ảnh)
                                                 │
                                                 ▼
                                             [Editor]
                                    (Biên tập nâng cao văn phong)
                                                 │
                                                 ▼
                                      [Coordinator Router]
                                    (Cổng kiểm định chất lượng)
                              ┌──────────────────┼──────────────────┐
                              ▼                  ▼                  ▼
                        [Fact-Checker]         [SEO]               [QA]
                      (Kiểm chứng sự thật)  (Tối ưu SEO)     (Đánh giá QA)
                              │                  │                  │
                              └──────────────────┼──────────────────┘
                                                 ▼
                                        [Coordinator Router]
                                                 │
                                                 ├───► QA duyệt qua (score >= 75) ──► [HOÀN THÀNH]
                                                 │
                                                 └───► Chất lượng yếu (QA fail)   ──► [SỬA LẠI]
                                                       (Gửi hướng dẫn sửa chi tiết về cho Editor/Writer)
```

---

## 2. Chi Tiết 9 Bước Trong Quy Trình Xử Lý

### Bước 1 — Khởi tạo cấu hình & Phê duyệt tham số (Coordinator Node)
* **Nhiệm vụ:** Tiếp nhận yêu cầu tạo Job từ Web UI/API. Tiến hành chuẩn hóa các tham số và cài đặt các ranh giới (quality gates) cho pipeline.
* **Quy trình:**
  1. Kiểm tra loại bài viết (`content_type`) và chọn hướng dẫn lĩnh vực (`domain`) tương ứng.
  2. Dựa vào chế độ chất lượng (`quality_mode`: standard | fast | strict), thiết lập số vòng sửa đổi tối đa (`max_revisions`) và số lần thử lại tối đa của từng Agent (`max_agent_retries`).
  3. Lưu giữ trạng thái khởi tạo ban đầu và chuyển tiếp sang node xử lý tiếp theo.

---

### Bước 2 — Tìm kiếm hình ảnh tự động (Image Research Agent)
* **Nhiệm vụ:** Tìm kiếm các hình ảnh chất lượng cao, miễn phí bản quyền để minh họa sống động cho bài viết dựa trên chủ đề và từ khóa.
* **Quy trình:**
  1. Gọi API của **Wikimedia Commons** để truy vấn các hình ảnh liên quan trực tiếp đến từ khóa SEO và chủ đề bài viết.
  2. Trích xuất các thông tin siêu dữ liệu (metadata) của ảnh: `url` gốc, `title`, tên tác giả (`attribution`), loại giấy phép sử dụng (`license`) và tự động soạn thảo thẻ mô tả `alt_text` cho công cụ đọc màn hình.
  3. Lưu danh sách ảnh cào được vào kết quả `image_assets` của Pipeline State dưới dạng artifact để sử dụng sau.

---

### Bước 3 — Nghiên cứu nguồn tư liệu (Research Agent)
* **Nhiệm vụ:** Thu thập thông tin thực tế từ internet để làm bằng chứng khoa học cho bài viết.
* **Quy trình:**
  1. Sử dụng **Tavily Search API** phát các câu truy vấn thông minh đa chiều tìm kiếm thông tin về chủ đề.
  2. Tự động loại bỏ các liên kết trùng lặp và lọc ra tối đa 4 nguồn tư liệu uy tín có độ tương đồng ngữ nghĩa cao nhất.
  3. Sử dụng thư viện cào chuyên dụng (Playwright cho trang web dùng nhiều JavaScript, BeautifulSoup cho trang web tĩnh) để tải nội dung thô của các trang web.
  4. LLM trích xuất các facts quan trọng, các số liệu thống kê đáng tin cậy (`statistics`), và các trích dẫn đắt giá (`quotes`), lưu vào `source_documents` và `research_summary` để làm tài liệu đối chiếu cho Fact-Checker Agent sau này.

---

### Bước 4 — Lập dàn ý bài viết & Duyệt Dàn Ý (Outline Agent)
* **Nhiệm vụ:** Thiết lập cấu trúc dàn bài logic, mạch lạc.
* **Quy trình:**
  1. Outline Agent chọn mẫu bài viết tương ứng với `content_type` của người dùng:
     * *Blog Post:* Mở đầu ấn tượng (Hook), Nêu vấn đề, Các phần giải pháp thực tế kèm ví dụ, Các takeaways/Lời kêu gọi hành động (CTA).
     * *Technical Report:* Tóm tắt điều hành, Phương pháp nghiên cứu, Phát hiện chính, Giới hạn và Khuyến nghị.
     * *News Article:* Dẫn dắt thông tin (Lead), Bối cảnh, Quan điểm các bên, Tác động và Thông tin nền.
     * *Tutorial:* Điều kiện cần (Prerequisites), Các bước thực hành, Khắc phục lỗi và Bước tiếp theo.
  2. LLM phân bổ số từ mục tiêu (`target_words`) cho từng phần, viết ngắn gọn nội dung cần đạt của từng phần (`brief`) và chỉ định rõ các `key_points` cùng nguồn dữ liệu cần cào.
  3. **Chờ phê duyệt (Outline Review):** Nếu người dùng chọn bật duyệt dàn ý, Celery task sẽ tạm thời chuyển trạng thái Job sang `paused` và lưu checkpoint trạng thái LangGraph vào DB. Người dùng có thể chỉnh sửa tiêu đề, tóm tắt các phần trực tiếp trên UI rồi nhấn "Approve & continue" để kích hoạt Celery tiếp tục chạy đồ thị từ bước tiếp theo.

---

### Bước 5 — Viết các phần song song & Ghép Bản Nháp (Writer & Join Draft Nodes)
* **Nhiệm vụ:** Soạn thảo nội dung thô cho bài viết một cách nhanh chóng và chất lượng.
* **Quy trình:**
  1. **Writer Planner Node:** Đọc dàn ý được duyệt, phân bổ thành các nhiệm vụ độc lập cho từng phần bài viết (`writer_tasks`).
  2. **Section Writer Agent (Song song):** LangGraph tự động phát tán (fan-out) các luồng Celery bất đồng bộ chạy song song. Mỗi tác vụ nhận một brief của phần tương ứng và thực hiện viết bài thô bám sát giọng văn (`tone`) và đối tượng độc giả mục tiêu. Giới hạn số lượng chạy song song bằng cấu hình `MAX_PARALLEL_WRITERS`.
  3. **Join Draft Node:** Đợi tất cả các phần viết song song hoàn thành, hệ thống thực hiện thu hồi và ghép nối các chuỗi nội dung lại theo đúng thứ tự dàn ý.
  4. **Tự động chèn ảnh:** Join Draft Agent tự động phân tích cấu trúc bài viết và chèn thẻ Markdown hiển thị ảnh bản quyền mở thu được từ bước 2 vào vị trí cực kỳ hợp lý (ngay sau đoạn giới thiệu Intro và sau các H2 chính của thân bài).

---

### Bước 6 — Biên tập chuyên sâu văn phong (Editor Agent)
* **Nhiệm vụ:** Chỉnh sửa ngữ pháp, tăng độ trôi chảy và đồng bộ giọng văn thống nhất giữa các phần do các mô hình song song viết.
* **Quy trình:**
  1. LLM rà soát toàn bộ bài viết, sửa chữa các lỗi lặp từ, cải thiện các đoạn chuyển tiếp mượt mà giữa các chương.
  2. Cắt bỏ hoàn toàn các từ thừa, sáo rỗng (fluff), điều chỉnh số lượng từ sát với mục tiêu ban đầu của người dùng (trong khoảng sai số ±10%).
  3. Lưu bài viết đã được tối ưu hóa vào artifact dạng `edited_draft`.

---

### Bước 7 — Kiểm chứng dữ liệu thực tế (Fact-Checker Agent)
* **Nhiệm vụ:** Đảm bảo tính trung thực và chính xác của bài viết, tránh hiện tượng LLM sinh dữ liệu ảo (hallucination).
* **Quy trình:**
  1. LLM quét bài viết và trích xuất ra tối đa 6 tuyên bố liên quan đến sự thật, số liệu thống kê hoặc sự kiện (factual claims).
  2. So khớp từng tuyên bố này so với tài liệu nghiên cứu gốc `source_documents` thu được từ Bước 3 bằng phương pháp phân tích ngữ nghĩa.
  3. Ánh xạ rõ ràng tuyên bố nào tương ứng với nguồn gốc tham khảo nào. Nếu tuyên bố nào hoàn toàn không tìm thấy bằng chứng trong tài liệu gốc sẽ bị đánh cờ Flag cảnh báo để Editor biên tập loại bỏ hoặc sửa lại.

---

### Bước 8 — Tối ưu hóa SEO (SEO Agent)
* **Nhiệm vụ:** Tăng khả năng tiếp cận của bài viết trên công cụ tìm kiếm Google.
* **Quy trình:**
  1. Sử dụng thuật toán Python thuần để tính toán điểm khả đọc (Flesch-Kincaid) và mật độ từ khóa SEO chính (`focus_keyword`) trong văn bản bài viết (đảm bảo đạt mật độ vàng 1.0% - 2.0%).
  2. Kiểm tra cấu trúc tiêu đề (H1, H2, H3) xem có phân bổ đúng chuẩn SEO.
  3. Gọi LLM sinh tự động: thẻ tiêu đề SEO (`meta_title`), đoạn mô tả ngắn thu hút (`meta_description`), URL thân thiện (`slug`) và các đề xuất cải thiện tối ưu thêm.

---

### Bước 9 — Đánh giá chất lượng cuối cùng & Định tuyến sửa chữa (QA Agent & Router)
* **Nhiệm vụ:** Đưa ra quyết định thông duyệt bài viết cuối cùng dựa trên các chỉ số đo lường khoa học.
* **Quy trình:**
  1. **QA Agent Chấm Điểm:** Đánh giá bài viết dựa trên thang điểm 100 thông qua 5 tiêu chí: Sự rõ ràng mạch lạc (Clarity - 25%), Tính chính xác thông tin (Accuracy - 25%), Sự hấp dẫn lôi cuốn (Engagement - 20%), Điểm chuẩn SEO (SEO - 15%), và Sự tuân thủ định dạng mẫu bài viết (Format Adherence - 15%).
  2. **Quyết định định tuyến (Coordinator Router):**
     * **Phê duyệt (`approve`):** Nếu điểm số đạt trên 75 điểm và không có lỗi kiểm chứng nghiêm trọng -> Pipeline kết thúc thành công, lưu bài viết vào artifact `final_content`, đổi trạng thái Job sang `completed`.
     * **Sửa chữa (`revise`):** Nếu điểm chất lượng thấp hoặc phát sinh cảnh báo sự thật nghiêm trọng -> Tăng số vòng sửa đổi (`revision_count`), trích xuất hướng dẫn sửa đổi cụ thể và tự động gửi trả luồng LangGraph quay về cho `editor` (hoặc `writer` nếu cần viết lại cả phần cụ thể).
     * **Buộc thông qua có cảnh báo (`fail_with_warning`):** Nếu số vòng sửa đã vượt quá giới hạn tối đa đặt ra của hệ thống -> Hệ thống vẫn chấp nhận xuất bài viết kèm theo ghi nhận danh sách các cảnh báo chất lượng để tránh lặp vô hạn gây tốn kém tài nguyên.
