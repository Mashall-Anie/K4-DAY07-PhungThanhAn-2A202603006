# Báo Cáo Nhóm — Lab 7: Embedding & Vector Store

**Nhóm:** BLAS

**Thành viên:**
- Đinh Tuấn Long — 2A202602620
- Lê Duy Bảo — 2A202602749
- Trần Quốc Sáng — 2A202602712
- Phùng Thành An — 2A202603006

**Ngày:** 20/09/2026

> **Nộp 1 bản / nhóm.** Phần cá nhân (hướng tiếp cận, kết quả riêng, dự đoán…) mỗi thành viên nộp riêng trong `REPORT_CANHAN.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần nhóm: 40** = Lựa chọn tài liệu (10) + Thiết kế chiến lược (15) + Chất lượng truy xuất (10) + Thuyết trình (5).

---

## 1. Lựa chọn tài liệu (Document Set Quality) — Nhóm (10 điểm)

### Chủ đề (Domain) & Lý Do Chọn

**Chủ đề:** Chính sách hậu mãi Shopee — Trả hàng/Hoàn tiền, Shopee Mall, bảo hành, bảo hiểm và giải quyết tranh chấp.

**Tại sao nhóm chọn chủ đề này?**

> Nhóm chọn chính sách hậu mãi Shopee vì đây là tập tài liệu có cấu trúc rõ nhưng vẫn đủ khó cho bài toán retrieval: nhiều điều khoản có từ vựng gần nhau nhưng khác đối tượng Người Mua/Người Bán, loại chính sách và các mốc thời gian cụ thể. Bộ dữ liệu này phù hợp để đánh giá ảnh hưởng của chunking, semantic embedding và metadata filtering đối với khả năng tìm đúng điều khoản thay vì chỉ tìm đúng chủ đề chung.

### Danh sách tài liệu (Data Inventory)

Corpus chung gồm **9 tài liệu** trong `data/shopee-bao hanh/`.

Số ký tự bên dưới được tính trên phần nội dung tài liệu sau khi loại bỏ YAML/frontmatter, tương ứng với nội dung được đưa vào chunking.

| # | Tên tài liệu | Nguồn (Source URL) | Ngày lấy / Phiên bản | Số ký tự | Metadata đã gán |
|---|---|---|---|---:|---|
| 1 | `dispute-resolution.md` | `https://help.shopee.vn/portal/4/article/77265` | `2026-09-20 / not-stated` | 4,594 | `audience=both`, `policy_type=dispute` |
| 2 | `extended-warranty-insurance.md` | `https://help.shopee.vn/portal/4/article/79229` | `2026-09-20 / not-stated` | 12,957 | `audience=buyer`, `policy_type=extended_warranty` |
| 3 | `insurance-activation.md` | `https://help.shopee.vn/portal/4/article/79230` | `2026-09-20 / not-stated` | 845 | `audience=buyer`, `policy_type=insurance_guide` |
| 4 | `return-refund-guide.md` | `https://help.shopee.vn/portal/4/article/79233` | `2026-09-20 / not-stated` | 2,217 | `audience=buyer`, `policy_type=return_refund_guide` |
| 5 | `return-refund-policy.md` | `https://help.shopee.vn/portal/4/article/77251` | `2026-09-20 / not-stated` | 19,410 | `audience=both`, `policy_type=return_refund` |
| 6 | `shopee-mall-buyer.md` | `https://help.shopee.vn/portal/4/article/77262` | `2026-09-20 / 2026-05-08` | 10,264 | `audience=buyer`, `policy_type=warranty/mall` |
| 7 | `shopee-mall-seller.md` | `https://help.shopee.vn/portal/4/article/77262` | `2026-09-20 / 2026-05-08` | 24,929 | `audience=seller`, `policy_type=warranty/mall` |
| 8 | `warranty-general-buyer.md` | `https://help.shopee.vn/portal/4/article/77245` | `2026-09-20 / 2025-01-03` | 12,769 | `audience=buyer`, `policy_type=warranty/general` |
| 9 | `warranty-general-seller.md` | `https://help.shopee.vn/portal/4/article/77245` | `2026-09-20 / 2025-01-03` | 15,639 | `audience=seller`, `policy_type=warranty/general` |

**Tổng quan corpus:**
- 9 tài liệu.
- `audience=buyer`: 5 tài liệu.
- `audience=seller`: 2 tài liệu.
- `audience=both`: 2 tài liệu.

**Danh sách kiểm tra quản trị dữ liệu (Data governance checklist):**
- [x] Tập tài liệu (Corpus) chỉ chứa nguồn công khai/được phép dùng và không chứa dữ liệu cá nhân, thông tin đăng nhập hoặc tài liệu nội bộ.
- [x] Mỗi tài liệu có `source_url`, `retrieved_at`, `document_version` hoặc ngày hiệu lực trong metadata.

### Cấu trúc Metadata (Metadata Schema)

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho truy xuất (retrieval)? |
|---|---|---|---|
| `doc_id` | string | `shopee-mall-seller` | Truy vết chunk về tài liệu gốc và hỗ trợ quản lý/xóa toàn bộ chunk của một document. |
| `title` | string | `Chính sách Shopee Mall` | Giúp nhận diện nội dung tài liệu và hiển thị nguồn dễ hiểu hơn. |
| `source_url` | string | URL nguồn Shopee | Cho phép kiểm chứng và truy vết về nguồn công khai ban đầu. |
| `retrieved_at` | date/string | `2026-09-20` | Cho biết thời điểm nhóm thu thập tài liệu. |
| `document_version` | string/date | ngày hiệu lực hoặc version | Giúp phân biệt các phiên bản chính sách có thể thay đổi theo thời gian. |
| `audience` | enum/string | `buyer`, `seller`, `both` | Cho phép lọc chính sách theo đúng đối tượng trước khi semantic ranking. |
| `policy_type` | string | `return_refund`, `dispute` | Thu hẹp candidate theo đúng nhóm nghiệp vụ. |
| `seller_type` | string | `mall`, `general` | Phân biệt chính sách Shopee Mall và Người Bán thông thường. |
| `product_scope` | string | `general`, `electronics` | Phân biệt các chính sách áp dụng cho nhóm sản phẩm khác nhau. |

---

## 2. Thiết kế chiến lược (Strategy Design) — Nhóm (15 điểm)

> Mỗi thành viên thử **một chiến lược khác nhau** trên cùng bộ tài liệu; nhóm tổng hợp và so sánh ở đây.

### Phân tích đường cơ sở (Baseline Analysis)

Nhóm chạy `ChunkingStrategyComparator().compare()` trên ba tài liệu đại diện:

- `return-refund-policy.md`: tài liệu trả hàng/hoàn tiền dài.
- `shopee-mall-seller.md`: tài liệu dài nhất trong corpus.
- `dispute-resolution.md`: tài liệu ngắn hơn và có cấu trúc đơn giản hơn.

Comparator sử dụng cấu hình mặc định của repository với `chunk_size=200`.

| Tài liệu | Chiến lược (Strategy) | Số lượng Chunk | Độ dài trung bình | Giữ được ngữ cảnh không? |
|---|---|---:|---:|---|
| `return-refund-policy` | FixedSizeChunker (`fixed_size`) | 130 | 198.9 | Kém — có trường hợp cắt giữa từ hoặc giữa câu. |
| `return-refund-policy` | SentenceChunker (`by_sentences`) | 42 | 459.4 | Khá — giữ được câu nhưng chunk có thể quá dài. |
| `return-refund-policy` | RecursiveChunker (`recursive`) | 162 | 118.1 | Khá — ưu tiên boundary tự nhiên nhưng có thể sinh fragment rất ngắn. |
| `shopee-mall-seller` | FixedSizeChunker (`fixed_size`) | 166 | 199.9 | Kém — có thể cắt giữa một điều khoản policy. |
| `shopee-mall-seller` | SentenceChunker (`by_sentences`) | 32 | 775.2 | Khá — giữ câu nhưng chunk rất dài, tối đa gần 2,000 ký tự. |
| `shopee-mall-seller` | RecursiveChunker (`recursive`) | 186 | 132.4 | Khá — giữ paragraph/newline tốt hơn nhưng đôi khi có chunk rất ngắn. |
| `dispute-resolution` | FixedSizeChunker (`fixed_size`) | 31 | 196.6 | Kém — boundary phụ thuộc số ký tự thay vì cấu trúc nội dung. |
| `dispute-resolution` | SentenceChunker (`by_sentences`) | 10 | 457.7 | Khá — câu nguyên vẹn nhưng dễ gom nhiều nội dung vào cùng chunk. |
| `dispute-resolution` | RecursiveChunker (`recursive`) | 37 | 122.8 | Khá — giữ boundary tự nhiên tốt hơn FixedSize nhưng vẫn có chunk vụn. |

**Nhận xét baseline:**

> **FixedSizeChunker** kiểm soát kích thước tốt nhưng có thể cắt giữa từ/câu hoặc giữa một điều khoản. **SentenceChunker** giữ được câu hoàn chỉnh nhưng trên policy document có nhiều câu dài, khiến chunk có thể quá lớn và heading context không được giữ ở tất cả chunk. **RecursiveChunker** ưu tiên paragraph/newline và các boundary tự nhiên nên giữ cấu trúc tốt hơn FixedSize, nhưng cấu hình baseline vẫn có thể tạo một số fragment rất ngắn.

### Chiến lược của từng thành viên

**Thành viên 1 — Đinh Tuấn Long**
- **Loại chiến lược:** Custom — `HeadingChunker(chunk_size=800)`.
- **Mô tả & lý do chọn cho chủ đề này:** Corpus Shopee có nhiều Markdown heading và điều khoản đánh số như `1.9.2`, `2.7.1`, nên HeadingChunker ưu tiên chia theo section để giữ được context. Nếu một section quá dài, nội dung được chia tiếp bằng RecursiveChunker và heading được gắn lại vào sub-chunk.
- **Embedding benchmark cá nhân:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.

**Code snippet (custom):**
```python
def _chunk_section(self, section: str) -> list[str]:
    section = section.strip()
    if len(section) <= self.chunk_size:
        return [section] if section else []

    heading, separator, content = section.partition("\n")
    heading = heading.rstrip()
    if not separator or not self._is_heading_line(heading):
        return self._fallback.chunk(section)

    content = content.strip()
    if not content:
        return [heading]

    content_size = max(1, self.chunk_size - len(heading) - 1)
    content_chunks = RecursiveChunker(chunk_size=content_size).chunk(content)
    return [f"{heading}\n{chunk}" for chunk in content_chunks]
```

**Thành viên 2 — Lê Duy Bảo**

- **Loại chiến lược:** `SentenceChunker(max_sentences_per_chunk=3)`.
- **Mô tả & lý do chọn:** Gom tối đa ba câu trong một chunk để giữ câu hoàn chỉnh và hạn chế việc cắt giữa câu như FixedSize. Điểm yếu là các điều khoản dài có thể bị mất heading context và benchmark cá nhân dùng `_mock_embed`, nên ranking semantic không phản ánh đầy đủ chất lượng chunking.
- **Embedding benchmark cá nhân:** `_mock_embed`.

**Thành viên 3 — Trần Quốc Sáng**

- **Loại chiến lược:** `FixedSizeChunker`.
- **Mô tả & lý do chọn:** FixedSize giúp kích thước chunk ổn định, dễ kiểm soát và triển khai. Tuy nhiên, khi áp dụng cho policy document, việc cắt theo số ký tự có thể tách mốc thời gian hoặc câu trả lời ra khỏi context liên quan.
- **Embedding benchmark cá nhân:** `text-embedding-3-small`.

**Thành viên 4 — Phùng Thành An**

- **Loại chiến lược:** `RecursiveChunker`.
- **Mô tả & lý do chọn:** RecursiveChunker ưu tiên tách theo paragraph, newline, câu và khoảng trắng, giúp giữ cấu trúc tự nhiên của văn bản tốt hơn FixedSize. Các fragment nhỏ được merge lại đến gần giới hạn kích thước để cân bằng giữa coherence và chunk size.
- **Embedding benchmark cá nhân:** `text-embedding-3-small`.

### So Sánh Giữa Các Thành Viên

| Thành viên | Chiến lược (Strategy) | Điểm truy xuất (/10) | Điểm mạnh | Điểm yếu |
|---|---|---:|---|---|
| Đinh Tuấn Long | HeadingChunker(800) | 6/10 Agent-evaluated | Giữ heading/section tốt; Q1 và Q3 đưa answer-bearing chunk lên rank 1. | Q2 answer ở rank 2; Q4 answer-bearing chunk không vào top-3. |
| Lê Duy Bảo | SentenceChunker(3 câu) | 7/10 tự đánh giá | Giữ câu nguyên vẹn và dễ đọc. | `_mock_embed` không biểu diễn semantic meaning nên score không so trực tiếp được với các thành viên khác. |
| Trần Quốc Sáng | FixedSizeChunker | 6/10 strict | Chunk size ổn định; retrieval tốt ở Q1, Q4 và Q5. | Q2 và Q3 thất bại do thông tin bị cắt rời khỏi context. |
| Phùng Thành An | RecursiveChunker | 9/10 | Retrieval quan sát tốt nhất; giữ natural boundaries tốt hơn FixedSize. | Có thể sinh fragment ngắn; embedding backend khác nên không thể coi điểm là controlled comparison tuyệt đối. |

> **Lưu ý:** Bốn thành viên không dùng cùng embedding backend, vì vậy tổng điểm không phải controlled experiment chỉ đo ảnh hưởng của chunking. Nhóm kết hợp điểm retrieval với answer-bearing rank, failure mode và khả năng giữ cấu trúc khi đánh giá.

**Chiến lược nào tốt nhất cho chủ đề này? Tại sao?**

> Trong các kết quả quan sát, **RecursiveChunker của Phùng Thành An cho retrieval tốt nhất**, đồng thời tránh được việc cắt cứng giữa câu như FixedSize. Tuy nhiên, với corpus policy có nhiều heading và section đánh số, nhóm cho rằng hướng phù hợp nhất nếu tiếp tục phát triển là **Heading-aware chunking kết hợp Recursive fallback**: giữ heading làm context và chỉ recursive split khi section quá dài. Do embedding backend giữa các thành viên khác nhau, nhóm không xem chênh lệch tổng điểm là bằng chứng tuyệt đối rằng một chunker luôn tốt hơn các chunker còn lại.

---

## 3. Câu hỏi đánh giá & Chất lượng truy xuất (Retrieval Quality) — Nhóm (10 điểm)

### Câu hỏi đánh giá & Câu trả lời chuẩn (nhóm thống nhất)

> **Đúng 5 câu hỏi**, đa dạng, có thể kiểm chứng; **ít nhất 1 câu** cần lọc metadata mới trả lời tốt. Đây là bộ câu hỏi chung cho mọi thành viên chạy.

| # | Câu hỏi (Query) | Câu trả lời chuẩn (Gold Answer) | Chunk nào chứa thông tin? |
|---|---|---|---|
| 1 | Người Mua có bao lâu để gửi yêu cầu trả hàng/hoàn tiền sau khi đơn được giao thành công? | **15 ngày** kể từ khi đơn được cập nhật giao thành công; đối với thực phẩm tươi sống/đông lạnh là **24 giờ**. | `return-refund-policy.md`; với HeadingChunker: `return-refund-policy#8`. |
| 2 | Sau khi yêu cầu trả hàng/hoàn tiền Shopee Mall được chấp thuận, Người Mua có bao lâu để gửi trả sản phẩm? | **06 ngày lịch**, trừ trường hợp áp dụng “Hoàn Tiền Ngay”. | `shopee-mall-buyer.md`; với HeadingChunker, answer-bearing chunk là `shopee-mall-buyer#5`. |
| 3 | Khi Shopee yêu cầu bằng chứng cho một yêu cầu trả hàng/hoàn tiền Shopee Mall, Người Bán phải cung cấp trong bao lâu? | Người Bán phải cung cấp trong **tối đa 24 giờ** kể từ khi Shopee yêu cầu. | `shopee-mall-seller.md`; với HeadingChunker: `shopee-mall-seller#4`. |
| 4 | Ai chịu trách nhiệm tiếp nhận bảo hành sản phẩm cho Người Mua trên Shopee? | **Người Bán** chịu trách nhiệm tiếp nhận bảo hành theo cam kết/chính sách; Shopee nhìn chung không trực tiếp thực hiện nghĩa vụ bảo hành, trừ sản phẩm do Shopee trực tiếp bán. | `warranty-general-seller.md`, section quy định trách nhiệm bảo hành của Người Bán. |
| 5 | Đối với tranh chấp không phải khiếu nại trả hàng/hoàn tiền, Shopee đưa ra hướng giải quyết trong bao lâu sau khi nhận đủ tài liệu? | Trong vòng **07 ngày làm việc** sau khi nhận đủ tài liệu; trường hợp phức tạp có thể kéo dài hơn. | `dispute-resolution.md`; với HeadingChunker: `dispute-resolution#3`. |

### Tổng hợp chất lượng truy xuất của nhóm

> Cách chấm (theo `docs/SCORING.md`): **2 điểm/câu** — top-3 chứa chunk liên quan + agent trả lời đúng (2), có liên quan nhưng thiếu/không ở top-1 (1), không có trong top-3 (0).

| # | Câu hỏi | Chiến lược tốt nhất cho câu này | Có chunk liên quan trong top-3? | Ghi chú |
|---|---|---|---|---|
| 1 | Thời hạn gửi yêu cầu trả hàng/hoàn tiền | HeadingChunker | Có | Answer-bearing `return-refund-policy#8` ở rank 1 và Agent trả đúng cả mốc 15 ngày và 24 giờ. |
| 2 | Thời hạn gửi trả hàng Shopee Mall | HeadingChunker / Recursive | Có | HeadingChunker tìm được answer-bearing chunk ở rank 2; retrieval vẫn bị nhiễu bởi các section cùng chủ đề. |
| 3 | Thời hạn Người Bán cung cấp bằng chứng | HeadingChunker | Có | Answer-bearing chunk chứa “tối đa 24 giờ” ở rank 1; FixedSize thất bại do context bị cắt rời. |
| 4 | Ai chịu trách nhiệm tiếp nhận bảo hành | RecursiveChunker | Có | Recursive tìm đúng section trách nhiệm Người Bán; HeadingChunker của Long tìm đúng tài liệu nhưng answer-bearing chunk không nằm trong top-3. |
| 5 | Thời hạn Shopee giải quyết tranh chấp | RecursiveChunker | Có | Recursive giữ được mốc 07 ngày làm việc cùng điều kiện trường hợp phức tạp có thể kéo dài. |

**Lọc bằng metadata có giúp ích không? Ở câu hỏi nào?**

> Có. Case rõ nhất là **Q5 với `metadata_filter={"audience": "both"}`**. Khi không filter, hai chunk từ `warranty-general-buyer` và `warranty-general-seller` có similarity khoảng `0.865` đứng trên `dispute-resolution#3` (`0.8517`), khiến answer chunk chỉ ở **rank 3**. Sau khi filter `audience=both`, `dispute-resolution#3` được đưa lên **rank 1** và các distractor sai audience/policy bị loại.
>
> Q3 cũng cho thấy filter `audience=seller` loại một chunk buyer sai audience, còn Q4 cho thấy giới hạn của metadata filtering: filter giúp tăng document precision nhưng không đảm bảo answer-bearing chunk sẽ lọt vào top-3 nếu semantic ranking vẫn chưa tốt.
>
> Vì nội dung “07 ngày làm việc” có xuất hiện lặp lại ở một số tài liệu, lợi ích chính của metadata filter trong Q5 là đưa **đúng nguồn/chính sách** lên vị trí cao hơn chứ không chỉ làm câu trả lời xuất hiện.

---

## 4. Thuyết trình (Demo) & Bài học nhóm — Nhóm (5 điểm)

**Những phân tích (insights) hay nhất nhóm sẽ trình bày:**

> 1. **Chunk đúng cấu trúc quan trọng không kém embedding mạnh.** FixedSize có thể cắt giữa câu hoặc giữa điều khoản; ngay cả khi dùng embedding semantic tốt, Q2 và Q3 vẫn có thể thất bại nếu thông tin cần thiết bị tách khỏi context.
>
> 2. **Semantic similarity cao không đồng nghĩa với đúng fact.** Các policy về trả hàng, bảo hành và tranh chấp dùng nhiều từ giống nhau, nên retrieval có thể tìm đúng chủ đề nhưng sai mốc thời gian hoặc sai đối tượng.
>
> 3. **Metadata filtering cải thiện precision trước semantic ranking.** Ở Q5, filter đưa answer chunk từ rank 3 lên rank 1. Tuy nhiên, metadata không thể bù hoàn toàn cho chunking hoặc semantic ranking kém.

**Bài học rút ra khi so sánh trong nhóm:**

> Cùng một corpus nhưng các chiến lược chunking tạo ra candidate retrieval khác nhau rõ rệt. SentenceChunker giữ câu tốt nhưng có thể tạo chunk quá dài; FixedSize dễ kiểm soát kích thước nhưng có thể phá vỡ ngữ nghĩa; Recursive giữ natural boundaries tốt hơn nhưng có thể sinh fragment nhỏ; HeadingChunker giữ được context của policy section tốt hơn trên tài liệu có cấu trúc đánh số.

**Nếu làm lại, nhóm sẽ thay đổi gì trong chiến lược dữ liệu (data strategy)?**

> Nhóm sẽ chuẩn hóa **một embedding backend duy nhất cho cả bốn thành viên** để tạo controlled experiment giữa các chunking strategy. Về chunking, nhóm sẽ thử hướng **Heading-aware + Recursive fallback**, trong đó heading/section được giữ làm context và chỉ recursive split khi section quá dài. Metadata cũng sẽ được thiết kế từ đầu theo `audience`, `policy_type`, `seller_type` và `product_scope`, đồng thời có thể bổ sung hybrid retrieval hoặc reranking cho các câu hỏi cần fact cụ thể.

---

## Tự Đánh Giá (Phần Nhóm)

| Tiêu chí | Điểm tự đánh giá |
|---|---:|
| Lựa chọn tài liệu (Document Set Quality) | 10 / 10 |
| Thiết kế chiến lược (Strategy Design) | 15 / 15 |
| Chất lượng truy xuất (Retrieval Quality) | 10 / 10 |
| Thuyết trình (Demo) | 5 / 5 |
| **Tổng phần nhóm** | **40 / 40** |