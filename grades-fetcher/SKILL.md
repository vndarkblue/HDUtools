---
name: grades-fetcher
description: Lấy và phân tích bảng điểm sinh viên từ cổng thông tin HDU (sinhvien.hdu.edu.vn), trả về dữ liệu JSON có cấu trúc theo từng học kỳ.
---

# Grades Fetcher — HDU Student Portal

Skill này tự động fetch và parse bảng điểm từ cổng sinh viên HDU, xuất ra JSON có cấu trúc gồm thông tin tổng quan và chi tiết từng học kỳ.

## Cấu trúc thư mục

```
grades-fetcher/
├── .env                   # Cookie xác thực (ASC.AUTH)
├── SKILL.md               # File hướng dẫn này
└── scripts/
    └── grades_fetcher.py  # Script chính
```

## Yêu cầu

- Python 3.10+ (chỉ dùng thư viện chuẩn, không cần cài thêm package)
- Cookie `ASC.AUTH` hợp lệ trong file `.env`

## Cấu hình `.env`

File `.env` phải chứa:

```env
COOKIES="<giá trị cookie ASC.AUTH>"
```

Cookie cần được lấy từ trình duyệt sau khi đăng nhập vào [sinhvien.hdu.edu.vn](https://sinhvien.hdu.edu.vn).

## Cách chạy

```bash
# In JSON ra stdout (mặc định dùng .env)
python scripts/grades_fetcher.py

# Dùng cookie trực tiếp từ dòng lệnh
python scripts/grades_fetcher.py --cookie "giá_trị_cookie"

# Đọc cookie từ file text
python scripts/grades_fetcher.py --cookie-file cookie.txt

# Lưu vào file
python scripts/grades_fetcher.py --out grades.json

# Chỉ định file .env khác
python scripts/grades_fetcher.py --env /path/to/.env --out grades.json
```

> **Lưu ý:** Script mặc định tìm `.env` tại thư mục gốc của skill (`grades-fetcher/.env`).

## Cấu trúc JSON đầu ra

```json
{
  "thong_tin_chung": {
    "tong_tc_tich_luy": "...",
    "diem_tb_tich_luy": "...",
    "nam_thu": "..."
  },
  "hoc_ky": [
    {
      "hoc_ky": "HK1 (2023-2024)",
      "mon_hoc": [
        {
          "stt": "1",
          "ma_lhp": "...",
          "ten_mon": "...",
          "so_tin_chi": "3",
          "DiemTongKet": "8.5",
          "DiemChu": "A",
          ...
        }
      ],
      "tong_ket": {
        "diemtb": "...",
        "diemtb4": "...",
        "sotcdat": "...",
        ...
      }
    }
  ]
}
```

## Hướng dẫn cho AI Agent

Khi được yêu cầu lấy bảng điểm, hãy thực hiện theo các bước sau:

1. Chạy script để fetch dữ liệu mới nhất:
   ```bash
   python scripts/grades_fetcher.py --out grades_new.json
   ```

2. Đọc và trả lời dựa trên nội dung JSON đã xuất.

3. **⚠️ Phát hiện thay đổi:** Nếu trước đó đã có dữ liệu cũ (ví dụ `grades.json`), hãy so sánh với dữ liệu mới fetch được. Nếu phát hiện bất kỳ thay đổi nào (điểm mới, môn mới, điểm được cập nhật, thay đổi xếp loại học lực...), **hãy thông báo rõ ràng cho user** về những thay đổi đó trước khi trả lời câu hỏi chính. Ví dụ:
   > 📢 **Phát hiện thay đổi so với dữ liệu cũ:**
   > - Môn "Lập trình Python" (HK2 2024-2025): Điểm tổng kết cập nhật từ `chưa có` → `8.0` (B+)
   > - Điểm TB tích lũy thay đổi: `3.12` → `3.18`
