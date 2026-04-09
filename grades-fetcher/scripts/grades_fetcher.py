"""
grades_fetcher.py
Tự động lấy và parse bảng điểm từ cổng sinh viên HDU.
Cookies được đọc từ file .env cùng thư mục.

Cách dùng:
    python grades_fetcher.py                        # fetch từ mạng, in JSON ra stdout
    python grades_fetcher.py --out grades.json       # lưu vào file
"""

import re
import sys
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from html.parser import HTMLParser


# ──────────────────────── Utility ───────────────────────────────
def clean(text: str) -> str:
    """Normalize whitespace: collapse newlines/spaces thành 1 space."""
    return " ".join(text.split())


# ─────────────────────────── Đọc .env ────────────────────────────
def load_env(env_path: Path) -> dict:
    env = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip().strip('"').strip("'")
    return env


def update_env(env_path: Path, key: str, value: str):
    """Cập nhật hoặc thêm key=value vào file .env."""
    lines = []
    found = False
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith(f"{key}=") or line.strip().startswith(f"{key} ="):
                lines.append(f'{key}="{value}"')
                found = True
            else:
                lines.append(line)
    
    if not found:
        lines.append(f'{key}="{value}"')
    
    # Đảm bảo thư mục tồn tại
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ───────────────────────── Fetch HTML ────────────────────────────
URL = "https://sinhvien.hdu.edu.vn/ket-qua-hoc-tap.html"

HEADERS_TEMPLATE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
}


def fetch_html(cookie_value: str) -> str:
    headers = dict(HEADERS_TEMPLATE)
    # Nếu cookie_value không chứa "ASC.AUTH=", ta bao bọc nó lại.
    # Ngược lại, giả sử người dùng đã cung cấp string cookie hoàn chỉnh.
    if "ASC.AUTH=" not in cookie_value:
        headers["Cookie"] = f"ASC.AUTH={cookie_value}"
    else:
        headers["Cookie"] = cookie_value
    req = urllib.request.Request(URL, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            # thử detect charset từ header
            content_type = resp.headers.get_content_charset("utf-8")
            return raw.decode(content_type, errors="replace")
    except urllib.error.HTTPError as e:
        sys.exit(f"[LỖI] HTTP {e.code}: {e.reason}. Kiểm tra lại cookie.")
    except urllib.error.URLError as e:
        sys.exit(f"[LỖI] Không thể kết nối: {e.reason}")


# ─────────────────────── Parse HTML ──────────────────────────────

# Các cột có title cố định trong <td title="...">
TD_FIELDS = [
    "DiemChuyenCan1",   # Giữa kỳ
    "DiemHeSo11",       # Thường xuyên LT hệ số 1 - cột 1
    "DiemHeSo12",
    "DiemHeSo13",
    "DiemHeSo14",
    "DiemHeSo15",
    "DiemHeSo16",
    "DiemThuongKy6",    # Thường xuyên cột 7
    "DiemThuongKy7",
    "DiemThuongKy8",
    "DiemThuongKy9",
    "DiemTieuLuan1",    # TL/BTL
    "DiemTieuLuan2",
    # "DuocDuThi" → td không có title (icon check) – handled separately
    "DiemThi1",         # Cuối kỳ 1
    "DiemThi2",         # Cuối kỳ 2
    "DiemTongKet",
    "DiemTinChi",
    "DiemChu",
    "GhiChu",
    "DiemThiKN1",
    "DiemThiKN1_2",
    "DiemThiKN2",
    "DiemThiKN2_2",
    "DiemThiKN3",
    "DiemThiKN3_2",
    "DiemThiKN4",
    "DiemThiKN4_2",
    "GhiChu_TK",
    # "IsDat" → td không có title (icon check) – handled separately
]

# subset trường quan trọng (dùng khi --compact)
IMPORTANT_FIELDS = {
    "DiemChuyenCan1", "DiemThi1", "DiemThi2",
    "DiemTongKet", "DiemTinChi", "DiemChu", "GhiChu",
}


class GradeParser(HTMLParser):
    """
    Parse bảng #xemDiem_aaa.
    Chiến lược:
      - Theo dõi trạng thái trong / ngoài bảng
      - Mỗi <tr> là 1 hàng; phân biệt:
        * header row (colspan lớn chứa "HK" hoặc "HKI/HKII/...") → học kỳ
        * subject row (td có title="DiemTongKet") → môn học
        * summary row (td có lang="kqht-tkhk-...") → số liệu tổng kết học kỳ
    """

    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False

        self.current_row_cells: list[dict] = []   # list of {title, text}
        self.current_cell = {"title": "", "text": ""}

        # kết quả
        self.semesters: list[dict] = []
        self.current_semester: dict | None = None

        # trạng thái cell phức tạp
        self._cell_depth = 0  # depth của td hiện tại

    # ── helpers ──
    def _new_semester(self, label: str):
        sem = {
            "hoc_ky": label,
            "mon_hoc": [],
            "tong_ket": {},
        }
        self.semesters.append(sem)
        self.current_semester = sem

    def _parse_subject_row(self, cells: list[dict]):
        """Chuyển cells của 1 hàng môn học thành dict."""
        # Thứ tự cột trong HTML (dựa vào sample):
        # 0: STT, 1: Mã LHP, 2: Tên môn, 3: STC
        # 4..N: các điểm theo TD_FIELDS (nhưng 1 số td ko có title)
        # Ta dùng title attribute để map
        titled = {c["title"]: c["text"].strip() for c in cells if c["title"]}
        no_title = [c for c in cells if not c["title"] and c["text"].strip() == ""]

        subject = {
            "stt": clean(cells[0]["text"]) if len(cells) > 0 else "",
            "ma_lhp": clean(cells[1]["text"]) if len(cells) > 1 else "",
            "ten_mon": clean(cells[2]["text"]) if len(cells) > 2 else "",
            "so_tin_chi": clean(cells[3]["text"]) if len(cells) > 3 else "",
        }

        for field in TD_FIELDS:
            subject[field] = clean(titled.get(field, ""))

        return subject

    # ── HTML handlers ──
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "table" and attrs.get("id") == "xemDiem_aaa":
            self.in_table = True
            return

        if not self.in_table:
            return

        if tag == "tr":
            self.in_row = True
            self.current_row_cells = []
            return

        if tag == "td" and self.in_row:
            if not self.in_cell:
                self.in_cell = True
                self._cell_depth = 1
                cell_class = attrs.get("class", "")
                # bỏ qua td.hidden
                if "hidden" in cell_class:
                    self.current_cell = {"title": "__HIDDEN__", "text": ""}
                else:
                    self.current_cell = {
                        "title": attrs.get("title", ""),
                        "class": cell_class,
                        "colspan": attrs.get("colspan", ""),
                        "lang": attrs.get("lang", ""),
                        "text": "",
                    }
            else:
                self._cell_depth += 1
            return

        if tag == "span" and self.in_cell:
            # span bên trong td summary: thu thập lang
            lang = attrs.get("lang", "")
            if lang:
                self.current_cell["_span_lang"] = lang
            return

    def handle_endtag(self, tag):
        if not self.in_table:
            return

        if tag == "table":
            self.in_table = False
            return

        if tag == "tr" and self.in_row:
            self.in_row = False
            self._process_row(self.current_row_cells)
            self.current_row_cells = []
            return

        if tag == "td" and self.in_row and self.in_cell:
            self._cell_depth -= 1
            if self._cell_depth == 0:
                self.in_cell = False
                if self.current_cell.get("title") != "__HIDDEN__":
                    self.current_row_cells.append(self.current_cell)
                self.current_cell = {"title": "", "text": ""}
            return

    def handle_data(self, data):
        if self.in_cell and self.current_cell.get("title") != "__HIDDEN__":
            self.current_cell["text"] += data

    def _process_row(self, cells: list[dict]):
        if not cells:
            return

        # Hàng tiêu đề học kỳ: 1 td với colspan lớn, text "HK..." hoặc "HKI..."
        if len(cells) == 1:
            text = cells[0]["text"].strip()
            # Học kỳ header: "HK1 (2023-2024)" hay "HKI (2023-2024)" ...
            if re.search(r"HK|Học kỳ", text, re.IGNORECASE):
                self._new_semester(text)
            elif cells[0].get("lang", "").startswith("kqht-tkhk"):
                # tổng kết
                self._add_summary(cells[0])
            return

        # Hàng môn học: có đủ cột số + DiemTongKet
        titled = {c["title"]: c["text"].strip() for c in cells if c["title"]}
        if "DiemTongKet" in titled or "DiemChu" in titled:
            if self.current_semester is not None:
                subject = self._parse_subject_row(cells)
                self.current_semester["mon_hoc"].append(subject)
            return

        # Hàng tổng kết (nhiều td mỗi td chứa span với lang)
        for cell in cells:
            lang = cell.get("_span_lang", "") or cell.get("lang", "")
            if lang.startswith("kqht-tkhk"):
                self._add_summary_cell(lang, cell["text"])

    def _add_summary(self, cell):
        if self.current_semester is None:
            return
        lang = cell.get("_span_lang", "") or cell.get("lang", "")
        self._add_summary_cell(lang, cell["text"])

    def _add_summary_cell(self, lang: str, text: str):
        if self.current_semester is None:
            return

        # Map lang key → tên trường mong muốn (None = bỏ qua)
        KEY_MAP = {
            "diemtbhocluc":        "diemtb",
            "diemtbtinchi":        "diemtb4",
            "diemtbhocluctichluy": "diemtbtichluy",
            "diemtbtinchitichluy": "diemtbtichluy4",
            "tongsotcdangky":      "sotcdangky",
            "sotctichluy":         "sotctichluy",
            "stcdathocky":         "sotcdat",
            "sotckhongdat":        "sotcno",
            "xeploaihocluc":       "xeploaihocluchocky",
            "xeploaihocluctichluy":"xeploaihocluctichluy",
        }

        raw_key = lang.replace("kqht-tkhk-", "")
        mapped = KEY_MAP.get(raw_key, raw_key)   # giữ nguyên nếu không có trong map
        if mapped is None:
            return                               # bỏ qua

        # Lấy phần sau dấu ":" cuối cùng rồi normalize whitespace
        if ":" in text:
            value = clean(text.split(":")[-1])
        else:
            value = clean(text)

        self.current_semester["tong_ket"][mapped] = value


def parse_summary_info(html: str) -> dict:
    """Lấy thông tin tổng quan (TC tích lũy, điểm TB tích lũy...)."""
    info = {}

    patterns = {
        "tong_tc_tich_luy": r'lang="kqht-tongstctl"[^>]*>.*?<span[^>]*>(.*?)</span>',
        "diem_tb_tich_luy": r'lang="kqht-dtbtl"[^>]*>.*?<span[^>]*>(.*?)</span>',
        "nam_thu": r'lang="kqht-svnamthu"[^>]*>.*?<span[^>]*>(.*?)</span>',
    }

    for key, pat in patterns.items():
        m = re.search(pat, html, re.DOTALL | re.IGNORECASE)
        if m:
            raw = m.group(1)
            # decode HTML entities đơn giản
            raw = re.sub(r"&#(\d+);", lambda x: chr(int(x.group(1))), raw)
            raw = raw.replace("&amp;", "&").strip()
            info[key] = raw

    return info


def parse_grades(html: str) -> dict:
    # --- thông tin tổng quan ---
    summary = parse_summary_info(html)

    # --- bảng điểm ---
    parser = GradeParser()
    parser.feed(html)

    return {
        "thong_tin_chung": summary,
        "hoc_ky": parser.semesters,
    }


# ──────────────────────────── main ──────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Lấy bảng điểm sinh viên HDU và xuất ra JSON."
    )
    parser.add_argument("--out", "-o", type=str, default="-",
                        help="File JSON xuất ra. Dùng '-' để in stdout (mặc định).")
    parser.add_argument("--cookie", "-c", type=str,
                        help="Giá trị cookie ASC.AUTH cung cấp trực tiếp.")
    parser.add_argument("--cookie-file", type=str,
                        help="Đường dẫn file chứa cookie.")
    parser.add_argument("--env", type=str, default=".env",
                        help="Đường dẫn file .env (mặc định: .env cùng thư mục script).")
    args = parser.parse_args()

    # ── Xác định Cookie ──
    cookie = None
    from_cli = False

    # Đường dẫn .env
    env_path = Path(args.env)
    if not env_path.is_absolute():
        # Tìm .env ở thư mục cha của script (thư mục gốc của skill)
        env_path = Path(__file__).parent.parent / env_path

    # 1. Từ command line --cookie
    if args.cookie:
        cookie = args.cookie.strip()
        from_cli = True

    # 2. Từ file --cookie-file
    if not cookie and args.cookie_file:
        cf_path = Path(args.cookie_file)
        if cf_path.exists():
            content = cf_path.read_text(encoding="utf-8").strip()
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line and ("ASC.AUTH" in line or "COOKIES" in line):
                        _, _, val = line.partition("=")
                        cookie = val.strip().strip('"').strip("'")
                    else:
                        cookie = line
                    break
        else:
            sys.exit(f"[LỖI] Không tìm thấy file cookie: {args.cookie_file}")

    # 3. Mặc định từ .env
    if not cookie:
        if env_path.exists():
            env = load_env(env_path)
            cookie = env.get("COOKIES", "")

    if not cookie:
        sys.exit("[LỖI] Thiếu cookie. Hãy dùng --cookie, --cookie-file hoặc thiết lập file .env")

    print(f"[INFO] Đang fetch từ {URL} ...", file=sys.stderr)
    html = fetch_html(cookie)
    print("[INFO] Fetch thành công.", file=sys.stderr)

    # ── Lưu vào .env nếu lấy thành công từ CLI ──
    if from_cli:
        update_env(env_path, "COOKIES", cookie)
        print(f"[INFO] Đã cập nhật COOKIES vào {env_path}", file=sys.stderr)

    # ── Parse ──
    data = parse_grades(html)
    total_subjects = sum(len(s["mon_hoc"]) for s in data["hoc_ky"])
    print(f"[INFO] Tìm thấy {len(data['hoc_ky'])} học kỳ, "
          f"{total_subjects} môn học.", file=sys.stderr)

    # ── Xuất JSON ──
    output = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out == "-":
        sys.stdout.write(output)
    else:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"[INFO] Đã lưu vào: {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
