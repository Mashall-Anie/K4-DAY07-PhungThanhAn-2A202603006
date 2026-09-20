from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(".env"))

from src.embeddings import OpenAIEmbedder
from src.chunking import compute_similarity

embed = OpenAIEmbedder()

pairs = [
    ("Tôi muốn trả lại hàng vì sản phẩm lỗi", "Làm sao để hoàn trả sản phẩm bị hỏng?"),
    ("Người Mua có 15 ngày để gửi yêu cầu trả hàng", "Người Bán phải nhận hàng hoàn trong 7 ngày làm việc"),
    ("Thời hạn bảo hành tính từ ngày nhận hàng", "Shopee không trực tiếp thực hiện nghĩa vụ bảo hành"),
    ("Trả hàng hoàn tiền trong vòng 15 ngày", "Thời tiết hôm nay đẹp, trời nắng không mưa"),
    ("Người Bán có trách nhiệm tiếp nhận bảo hành", "Shop phải bảo hành sản phẩm theo cam kết đã đăng"),
]

for i, (a, b) in enumerate(pairs, 1):
    va, vb = embed(a), embed(b)
    s = compute_similarity(va, vb)
    print(f"Cặp {i}: {s:.4f}")
    print(f"  A: {a}")
    print(f"  B: {b}")
    print()
