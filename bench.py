"""bench.py — công cụ đo retrieval của nhóm (CP5 + CP6). Không chấm bằng pytest.

Mặc định chạy TẤT CẢ chiến lược chunking trong CHUNKERS (Fixed, Sentence, Recursive, Heading)
trên cùng dữ liệu, cùng 5 query, cùng embedder, rồi in bảng so sánh.

    python bench.py                      # chạy hết
    python bench.py SentenceChunker      # chỉ chạy các chiến lược nêu tên (không phân biệt hoa thường)

Với mỗi chiến lược:
  1. Chunk phần thân của từng file .md (NGOÀI store), mỗi chunk thành một Document
  2. Nạp vào EmbeddingStore, chạy 5 query: CÓ filter và KHÔNG filter (số liệu A/B)
  3. In top-3 kèm score, chấm 2 mức (file gold / chunk có đáp án) theo thang 2/1/0
Kết quả được lưu vào ket_qua_benchmark.txt.
"""
from __future__ import annotations

import os
import re
import sys
import unicodedata
from pathlib import Path

from dotenv import load_dotenv

from src.chunking import FixedSizeChunker, RecursiveChunker, SentenceChunker
from src.embeddings import (
    EMBEDDING_PROVIDER_ENV,
    GeminiEmbedder,
    LocalEmbedder,
    OpenAIEmbedder,
    _mock_embed,
)
from src.models import Document
from src.store import EmbeddingStore


class HeadingChunker:
    """Chunk theo heading Markdown: mỗi section (từ dòng '#...' tới heading kế tiếp) là một chunk.
    Section dài hơn max_chunk_size thì hạ xuống RecursiveChunker và gắn lại dòng heading vào từng mảnh con.
    Chunk chỉ gồm H1 + ghi chú nguồn (ngắn) được gộp vào section kế tiếp để tránh nhiễu top-k.
    """

    def __init__(self, max_chunk_size: int = 800) -> None:
        self.max_chunk_size = max_chunk_size

    def chunk(self, text: str) -> list[str]:
        raw = [s.strip() for s in re.split(r"(?m)^(?=#{1,6}\s)", text) if s.strip()]

        # Gộp section chỉ còn H1 + dòng nguồn ngắn vào section kế tiếp
        sections: list[str] = []
        carry = ""
        for s in raw:
            if s.startswith("# ") and len(s) < 400:
                carry = s + "\n\n"
                continue
            sections.append((carry + s) if carry else s)
            carry = ""
        if carry:
            sections.append(carry.strip())

        chunks: list[str] = []
        for section in sections:
            if len(section) <= self.max_chunk_size:
                chunks.append(section)
                continue
            first_line, _, rest = section.partition("\n")
            heading, body = (first_line, rest.strip()) if first_line.startswith("#") else ("", section)
            room = max(1, self.max_chunk_size - len(heading) - 1)
            for piece in RecursiveChunker(chunk_size=room).chunk(body):
                chunks.append(f"{heading}\n{piece}" if heading else piece)
        return chunks


# ============================================================================
# >>> Thêm / bớt / chỉnh tham số chiến lược ở ĐÂY. Khóa của dict là tên hiển thị. <<<
CHUNKERS = {
    "FixedSizeChunker": FixedSizeChunker(chunk_size=500, overlap=50),
    "SentenceChunker": SentenceChunker(max_sentences_per_chunk=3),
    "RecursiveChunker": RecursiveChunker(chunk_size=500),
    "HeadingChunker": HeadingChunker(max_chunk_size=800),
}
# ============================================================================

DATA_DIR = Path("data/ecommerce-policy")
TOP_K = 3


def num_unit(num: str, unit: str) -> str:
    """Pattern cho '<số> <đơn vị>'. Khớp '15 ngày', '06 ngày', '06 (sáu) ngày', '24 (hai mươi tư) giờ';
    KHÔNG khớp '115 ngày' hay '16 ngày' khi tìm '6 ngày'."""
    return rf"(?<!\d)0?{num}(?:\s*\([^)]{{0,30}}\))?\s*{unit}"


# audience của nhóm: buyer / seller / both (both = tài liệu dùng chung).
# Giá trị list nghĩa là "một trong các giá trị này" (vd Q1: buyer HOẶC both).
BENCHMARK_QUERIES = [
    {
        "id": "Q1",
        "question": "Người Mua có bao lâu để gửi yêu cầu trả hàng/hoàn tiền sau khi đơn được giao thành công?",
        "filter": {"audience": ["buyer", "both"]},
        "gold_doc_id": "return-refund-policy",
        "gold_answer": "15 ngày đối với sản phẩm thông thường; 24 giờ đối với thực phẩm tươi sống/đông lạnh.",
        "keywords": [num_unit("15", "ngày")],
        "hint": "15 ngày",
    },
    {
        "id": "Q2",
        # Câu không nêu người hỏi là ai → filter buyer/seller thật sự phân biệt đáp án
        # buyer: 6 ngày lịch (mục 1.2) | seller: 7 ngày làm việc (mục 1.9.2b)
        "question": (
            "Trong Shopee Mall, sau khi yêu cầu trả hàng/hoàn tiền được chấp thuận, "
            "cần hoàn tất việc gửi hoặc nhận lại sản phẩm trong bao nhiêu ngày?"
        ),
        "filter": {"audience": "buyer"},
        "gold_doc_id": "shopee-mall-buyer",
        "gold_answer": "6 ngày lịch kể từ ngày yêu cầu được chấp thuận.",
        "keywords": [num_unit("6", "ngày")],
        "hint": "6 ngày",
    },
    {
        "id": "Q3",
        "question": (
            "Khi Shopee yêu cầu bằng chứng cho một yêu cầu trả hàng/hoàn tiền Shopee Mall, "
            "Người Bán phải cung cấp trong bao lâu?"
        ),
        # Đáp án 24 giờ nằm ở file seller sau khi tách dữ liệu
        "filter": {"audience": "seller"},
        "gold_doc_id": "shopee-mall-seller",
        "gold_answer": "Tối đa 24 giờ kể từ khi nhận được yêu cầu của Shopee.",
        "keywords": [num_unit("24", "giờ")],
        "hint": "24 giờ",
    },
    {
        "id": "Q4",
        "question": "Ai chịu trách nhiệm tiếp nhận bảo hành sản phẩm cho Người Mua trên Shopee?",
        "filter": {"audience": "seller"},
        "gold_doc_id": "warranty-general-seller",
        "gold_answer": (
            "Người Bán có trách nhiệm tiếp nhận bảo hành theo chính sách của Người Bán "
            "và/hoặc nhà sản xuất; Shopee không phải bên trực tiếp thực hiện nghĩa vụ bảo hành, "
            "trừ sản phẩm do Shopee trực tiếp bán."
        ),
        "keywords": ["tiếp nhận bảo hành"],
        "hint": "tiếp nhận bảo hành",
    },
    {
        "id": "Q5",
        "question": (
            "Đối với tranh chấp không phải khiếu nại trả hàng/hoàn tiền, "
            "Shopee đưa ra hướng giải quyết trong bao lâu sau khi nhận đủ tài liệu?"
        ),
        "filter": {"audience": "both"},
        "gold_doc_id": "dispute-resolution",
        "gold_answer": (
            "Trong vòng 7 ngày làm việc kể từ khi nhận đủ thông tin/tài liệu; "
            "vụ việc phức tạp có thể kéo dài hơn."
        ),
        "keywords": [num_unit("7", "ngày làm việc")],
        "hint": "7 ngày làm việc",
    },
]

_LOG: list[str] = []


def log(line: str = "") -> None:
    print(line, flush=True)
    _LOG.append(line)


# --------------------------------------------------------------------------- #
# Đọc & chunk dữ liệu
# --------------------------------------------------------------------------- #
def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Tách khối YAML giữa hai dòng '---' thành dict, phần còn lại là thân bài.
    Chịu được BOM, dòng trống đầu file, CRLF và khoảng trắng thừa sau '---'."""
    text = text.lstrip("\ufeff").replace("\r\n", "\n").lstrip()
    m = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)(.*)$", text, re.S)
    if not m:
        return {}, text.strip()
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip():
            meta[key.strip()] = value.strip().strip("\"'")
    return meta, m.group(2).strip()


def load_corpus() -> tuple[dict[str, dict], dict[str, str]]:
    """Đọc dữ liệu một lần: {tên file: frontmatter}, {tên file: thân bài}. Không phụ thuộc chunker."""
    metas: dict[str, dict] = {}
    bodies: dict[str, str] = {}
    for path in sorted(DATA_DIR.glob("*.md")):
        metas[path.stem], bodies[path.stem] = parse_frontmatter(path.read_text(encoding="utf-8"))
    return metas, bodies


def chunk_corpus(chunker, metas: dict[str, dict], bodies: dict[str, str]) -> tuple[list[Document], dict[str, int]]:
    docs: list[Document] = []
    per_file: dict[str, int] = {}
    for stem, body in bodies.items():
        chunks = chunker.chunk(body)  # chunk ở ĐÂY, ngoài store
        per_file[stem] = len(chunks)
        for i, text in enumerate(chunks):
            docs.append(
                Document(
                    id=f"{stem}#{i}",  # Document.id = định danh từng chunk
                    content=text,
                    metadata={
                        **metas[stem],  # trải frontmatter vào MỌI chunk để filter có cái mà lọc
                        "doc_id": stem,
                        # bản sao của doc_id: nếu store ghi đè metadata["doc_id"] = Document.id
                        # thì việc chấm điểm vẫn không hỏng
                        "source_doc": stem,
                        "chunk_index": i,
                    },
                )
            )
    return docs, per_file


def with_cache(fn):
    """Nhớ embedding theo nội dung: các chiến lược có chunk trùng nhau không phải embed lại (đỡ chậm, đỡ tốn tiền API)."""
    cache: dict[str, list[float]] = {}

    def wrapped(text: str) -> list[float]:
        if text not in cache:
            cache[text] = fn(text)
        return cache[text]

    return wrapped


def select_embedder():
    load_dotenv(override=False)
    provider = os.getenv(EMBEDDING_PROVIDER_ENV, "mock").strip().lower()
    factories = {"local": LocalEmbedder, "openai": OpenAIEmbedder, "gemini": GeminiEmbedder}
    if provider in factories:
        try:
            emb = factories[provider]()
            return emb, getattr(emb, "_backend_name", provider)
        except Exception as e:  # không im lặng: tránh tưởng đang dùng embedder thật
            log(f"[!] Không khởi tạo được embedder '{provider}' ({e}); dùng mock embedder.")
    return _mock_embed, "mock"


# --------------------------------------------------------------------------- #
# Tìm kiếm & chấm
# --------------------------------------------------------------------------- #
def search(store: EmbeddingStore, question: str, flt: dict | None, top_k: int = TOP_K) -> list[dict]:
    """Lọc TRƯỚC, tìm SAU. store chỉ so sánh bằng (==), nên với giá trị dạng list
    ta gọi từng tổ hợp giá trị rồi gộp theo score."""
    if not flt:
        return store.search_with_filter(question, top_k=top_k, metadata_filter=None)
    combos: list[dict] = [{}]
    for key, val in flt.items():
        values = val if isinstance(val, (list, tuple, set)) else [val]
        combos = [{**c, key: v} for c in combos for v in values]
    merged: list[dict] = []
    for c in combos:
        merged += store.search_with_filter(question, top_k=top_k, metadata_filter=c)
    merged.sort(key=lambda r: r["score"], reverse=True)
    return merged[:top_k]


def source_doc(result: dict) -> str:
    meta = result["metadata"]
    return meta.get("source_doc") or meta.get("doc_id", "?")


def norm(text: str) -> str:
    # NFC + đổi khoảng trắng không ngắt (\xa0) thành khoảng trắng thường: text crawl từ web hay dính hai thứ này
    return unicodedata.normalize("NFC", text).replace("\xa0", " ").lower()


def has_answer(text: str, patterns: list[str]) -> bool:
    t = norm(text)
    return any(re.search(unicodedata.normalize("NFC", p), t) for p in patterns)


def evaluate(results: list[dict], gold_id: str, keywords: list[str]) -> tuple[int | None, int | None]:
    """Trả về (rank chunk đầu tiên thuộc file gold, rank chunk đầu tiên thuộc file gold VÀ chứa đáp án)."""
    doc_rank = ans_rank = None
    for rank, r in enumerate(results, start=1):
        if source_doc(r) != gold_id:
            continue
        doc_rank = doc_rank or rank
        if ans_rank is None and has_answer(r["content"], keywords):
            ans_rank = rank
    return doc_rank, ans_rank


def fmt_rank(rank: int | None) -> str:
    return f"#{rank}" if rank else "—"


def pts(rank: int | None) -> int:
    """Thang CP6: 2 = hạng #1, 1 = hạng #2-3, 0 = vắng."""
    return 2 if rank == 1 else (1 if rank in (2, 3) else 0)


def validate_benchmark(metas: dict[str, dict], bodies: dict[str, str]) -> None:
    """Tự kiểm 5 query trước khi chạy: gold file có tồn tại không, filter có loại mất gold file không,
    đáp án có thật sự nằm trong gold file không (kiểm trên thân bài gốc, không phụ thuộc chunker)."""
    problems = 0
    for q in BENCHMARK_QUERIES:
        gold = q["gold_doc_id"]
        if gold not in bodies:
            log(f"[!] {q['id']}: không có file '{gold}.md' trong {DATA_DIR}")
            problems += 1
            continue
        for key, val in (q["filter"] or {}).items():
            allowed = list(val) if isinstance(val, (list, tuple, set)) else [val]
            if metas[gold].get(key) not in allowed:
                log(
                    f"[!] {q['id']}: filter {key}={allowed} sẽ LOẠI file gold "
                    f"(frontmatter của {gold}.md ghi {key}={metas[gold].get(key)!r})"
                )
                problems += 1
        if not has_answer(bodies[gold], q["keywords"]):
            log(
                f"[!] {q['id']}: không thấy đáp án '{q['hint']}' trong {gold}.md "
                f"— gold answer có thật sự trích từ file này không? "
                f"(thử: grep -n -i \"{q['hint'].split()[0]}\" {DATA_DIR}/{gold}.md)"
            )
            problems += 1
    log("Kiểm tra benchmark: OK" if not problems else f"Kiểm tra benchmark: {problems} vấn đề ở trên")
    log()


# --------------------------------------------------------------------------- #
# Chạy benchmark
# --------------------------------------------------------------------------- #
def print_top(results: list[dict]) -> None:
    if not results:
        log("      (không có chunk nào — filter không khớp file nào?)")
    for rank, r in enumerate(results, start=1):
        preview = r["content"][:80].replace("\n", " ")
        log(f"      [{rank}] score={r['score']:.4f} {source_doc(r)}#{r['metadata'].get('chunk_index')} | {preview}...")


def run_strategy(name: str, chunker, embed_fn, backend: str, metas: dict, bodies: dict) -> dict:
    docs, per_file = chunk_corpus(chunker, metas, bodies)
    store = EmbeddingStore(collection_name=f"bench_{name.lower()}", embedding_fn=embed_fn)
    store.add_documents(docs)
    avg_len = sum(len(d.content) for d in docs) / len(docs) if docs else 0.0

    log("#" * 78)
    log(f"CHIẾN LƯỢC: {name}  {vars(chunker)}")
    log(f"Đã nạp {store.get_collection_size()} chunk, độ dài TB {avg_len:.0f} ký tự")
    log("Số chunk mỗi file: " + ", ".join(f"{k}={v}" for k, v in per_file.items()))
    log("#" * 78)
    log()

    rows = []
    for q in BENCHMARK_QUERIES:
        log(f"{q['id']}: {q['question']}")
        log(f"  gold answer : {q['gold_answer']}")
        log(f"  gold file   : {q['gold_doc_id']}.md")
        row = {"id": q["id"], "filtered": None, "unfiltered": None}
        for label, flt in (("CÓ filter", q["filter"]), ("KHÔNG filter", None)):
            if label == "CÓ filter" and not flt:
                log("  --- CÓ filter: (câu này không dùng filter)")
                continue
            results = search(store, q["question"], flt)
            doc_rank, ans_rank = evaluate(results, q["gold_doc_id"], q["keywords"])
            log(
                f"  --- {label}"
                + (f" {flt}" if flt else "")
                + f"  |  file gold: {fmt_rank(doc_rank)}  chunk có đáp án: {fmt_rank(ans_rank)}"
            )
            print_top(results)
            row["filtered" if flt else "unfiltered"] = (doc_rank, ans_rank)
        rows.append(row)
        log()

    def cell(pair):
        return ("n/a", "n/a") if pair is None else (fmt_rank(pair[0]), fmt_rank(pair[1]))

    log(f"TÓM TẮT top-{TOP_K}  ({name}, {backend})")
    log(f"{'':4} | {'CÓ filter':^22} | {'KHÔNG filter':^22}")
    log(f"{'':4} | {'file gold':^10} {'có đáp án':^11} | {'file gold':^10} {'có đáp án':^11}")
    for row in rows:
        fd, fa = cell(row["filtered"])
        ud, ua = cell(row["unfiltered"])
        log(f"{row['id']:4} | {fd:^10} {fa:^11} | {ud:^10} {ua:^11}")
    log()

    # Điểm: chạy tính điểm = CÓ filter nếu câu có filter, ngược lại KHÔNG filter.
    # "Thực chất" = chunk thuộc file gold VÀ chứa đáp án; "hình thức" = chỉ cần đúng file gold.
    real, form = [], []
    for row in rows:
        doc_rank, ans_rank = row["filtered"] or row["unfiltered"]
        real.append(pts(ans_rank))
        form.append(pts(doc_rank))
    with_filter = [r for r in rows if r["filtered"]]
    stats = {
        "name": name,
        "chunks": len(docs),
        "avg_len": avg_len,
        "real": real,
        "form": form,
        "ab_filtered": sum(1 for r in with_filter if r["filtered"][1]),
        "ab_unfiltered": sum(1 for r in with_filter if r["unfiltered"][1]),
        "ab_top1_filtered": sum(1 for r in with_filter if r["filtered"][1] == 1),
        "ab_top1_unfiltered": sum(1 for r in with_filter if r["unfiltered"][1] == 1),
        "ab_total": len(with_filter),
    }
    log(f"ĐIỂM {name}: thực chất {sum(real)}/{2 * len(rows)} | hình thức {sum(form)}/{2 * len(rows)}")
    log()
    return stats


def print_comparison(all_stats: list[dict], backend: str) -> None:
    n = len(BENCHMARK_QUERIES)
    log("=" * 78)
    log(f"SO SÁNH CÁC CHIẾN LƯỢC  (top-{TOP_K}, embedding: {backend})")
    log("Điểm thang 2/1/0. 'thực chất' = chunk thuộc file gold và chứa đáp án; 'hình thức' = chỉ cần đúng file gold.")
    log("A/B = số câu có đáp án trong top-3 khi CÓ filter / KHÔNG filter (chỉ tính các câu có dùng filter).")
    log("-" * 78)
    log(
        f"{'Chiến lược':18} | {'chunk':>5} | {'TB ký tự':>8} | "
        f"{'thực chất':>9} | {'hình thức':>9} | {'A/B có đáp án':>13}"
    )
    for s in all_stats:
        ab = f"{s['ab_filtered']}/{s['ab_total']} vs {s['ab_unfiltered']}/{s['ab_total']}"
        log(
            f"{s['name']:18} | {s['chunks']:>5} | {s['avg_len']:>8.0f} | "
            f"{sum(s['real']):>4}/{2 * n:<4} | {sum(s['form']):>4}/{2 * n:<4} | {ab:>13}"
        )
    log("-" * 78)
    log("A/B theo hạng #1 (đáp án ở chunk đầu tiên): CÓ filter vs KHÔNG filter")
    for s in all_stats:
        log(
            f"{s['name']:18} | "
            f"{s['ab_top1_filtered']}/{s['ab_total']} vs {s['ab_top1_unfiltered']}/{s['ab_total']}"
        )
    log("-" * 78)
    log("Điểm thực chất từng câu (2/1/0):")
    log(f"{'Chiến lược':18} | " + " ".join(f"{q['id']:>3}" for q in BENCHMARK_QUERIES))
    for s in all_stats:
        log(f"{s['name']:18} | " + " ".join(f"{p:>3}" for p in s["real"]))
    log("(chênh lệch giữa 'hình thức' và 'thực chất' = số điểm bị thổi phồng khi chỉ kiểm file gold)")
    if backend == "mock":
        log("[!] Backend là MOCK (băm MD5, không mã hóa ngữ nghĩa): điểm số là nhiễu, không dùng để kết luận.")
        log("    Chỉ 'chunk' và 'TB ký tự' là chỉ số không phụ thuộc embedding.")
    log("=" * 78)


def main() -> None:
    wanted = {a.lower() for a in sys.argv[1:]}
    chunkers = {k: v for k, v in CHUNKERS.items() if not wanted or k.lower() in wanted}
    if not chunkers:
        raise SystemExit(f"Không có chiến lược nào khớp {sys.argv[1:]}. Có sẵn: {', '.join(CHUNKERS)}")

    metas, bodies = load_corpus()
    if not bodies:
        raise SystemExit(f"Không đọc được file nào từ {DATA_DIR}/*.md — kiểm tra đường dẫn DATA_DIR.")

    embedder, backend = select_embedder()
    embed_fn = with_cache(embedder)

    log("=" * 78)
    log(f"Embedding backend : {backend}")
    log(f"Dữ liệu           : {len(bodies)} file trong {DATA_DIR}")
    log(f"Chiến lược        : {', '.join(chunkers)}")
    log("=" * 78)
    log()
    log("Frontmatter đọc được:")
    for stem, m in metas.items():
        if not m:
            log(f"  [!] {stem}.md: KHÔNG đọc được frontmatter (file thiếu khối '---' ở đầu?)")
        else:
            log(
                f"  {stem}.md: audience={m.get('audience')!r} policy_type={m.get('policy_type')!r} "
                f"(các trường: {', '.join(m)})"
            )
    log()
    validate_benchmark(metas, bodies)

    all_stats = [run_strategy(name, ch, embed_fn, backend, metas, bodies) for name, ch in chunkers.items()]
    print_comparison(all_stats, backend)

    out = Path("ket_qua_benchmark.txt")
    out.write_text("\n".join(_LOG), encoding="utf-8")
    print(f"\nĐã lưu: {out.resolve()}")


if __name__ == "__main__":
    main()