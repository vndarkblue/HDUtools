import os
import sys
from datetime import date, timedelta
import argparse
import requests
import json
from pathlib import Path
from dotenv import load_dotenv, set_key

from extract_timetable import parse_html_to_json

# Skill root is one level up
SKILL_ROOT = Path(__file__).parent.parent
TIMETABLE_CACHE_PATH = SKILL_ROOT / "timetable.json"


def load_cached_timetable():
    """Load the previously saved timetable from timetable.json, or None if not found."""
    if not TIMETABLE_CACHE_PATH.exists():
        return None
    try:
        return json.loads(TIMETABLE_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_timetable(data):
    """Save timetable data to timetable.json."""
    TIMETABLE_CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def update_env(env_path: Path, key: str, value: str):
    """Cập nhật hoặc thêm key=value vào file .env using python-dotenv."""
    # set_key handles everything for us
    set_key(str(env_path), key, value)


def fetch_timetable_data(cookie_value, next_week=False):
    # Đảm bảo có tiền tố ASC.AUTH= nếu người dùng chỉ cung cấp token
    if "ASC.AUTH=" not in cookie_value:
        cookie_header = f"ASC.AUTH={cookie_value}"
    else:
        cookie_header = cookie_value

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0",
        "Accept": "text/html, */*; q=0.01",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://sinhvien.hdu.edu.vn",
        "Connection": "keep-alive",
        "Cookie": cookie_header,
    }

    # API accepts any valid date string "DD/MM/YYYY" within the target week
    offset = timedelta(weeks=1) if next_week else timedelta(0)
    date_str = (date.today() + offset).strftime("%d/%m/%Y")

    url = "https://sinhvien.hdu.edu.vn/SinhVien/GetDanhSachLichTheoTuan"
    data = {
        "pNgayHienTai": date_str,
        "pLoaiLich": 0,
    }

    try:
        session = requests.Session()
        session.trust_env = False  # Ignore system/env proxy settings (fixes SOCKS proxy errors)
        response = session.post(url, headers=headers, data=data)
        response.raise_for_status()

        # Parse the returned HTML using the existing logic
        return parse_html_to_json(response.text)

    except Exception as e:
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Fetch timetable from HDU student portal."
    )
    parser.add_argument(
        "-c",
        "--check-update",
        action="store_true",
        help=(
            "So sánh thời khoá biểu vừa lấy với timetable.json đã lưu trước đó. "
            "Xuất ra 'true' nếu có thay đổi, 'false' nếu không. "
            "Dữ liệu mới vẫn được lưu lại vào timetable.json."
        ),
    )
    parser.add_argument(
        "-n",
        "--next-week",
        action="store_true",
        help="Lấy thời khoá biểu của tuần sau thay vì tuần hiện tại.",
    )
    parser.add_argument("--cookie", "-k", type=str, help="Giá trị cookie ASC.AUTH cung cấp trực tiếp.")
    parser.add_argument("--cookie-file", type=str, help="Đường dẫn file chứa cookie.")
    parser.add_argument("--env", type=str, default=".env", help="Đường dẫn file .env.")
    args = parser.parse_args()

    # ── Xác định Cookie ──
    cookie = None
    from_cli = False
    env_path = SKILL_ROOT / args.env

    if args.cookie:
        cookie = args.cookie.strip()
        from_cli = True

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

    if not cookie:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            cookie = os.getenv("COOKIES", "")

    if not cookie:
        sys.exit("[LỖI] Thiếu cookie. Hãy dùng --cookie, --cookie-file hoặc .env")

    # ── Fetch ──
    result = fetch_timetable_data(cookie_value=cookie, next_week=args.next_week)

    # ── Cập nhật .env nếu thành công ──
    if from_cli and not (isinstance(result, dict) and "error" in result):
        update_env(env_path, "COOKIES", cookie)
        print(f"[INFO] Đã cập nhật COOKIES vào {env_path.name}", file=sys.stderr)

    # ── Xử lý kết quả ──
    if args.check_update:
        cached = load_cached_timetable()
        has_update = result != cached

        output = {
            "has_update": has_update,
            "old": cached,
            "new": result,
        }

        if not isinstance(result, dict) or "error" not in result:
            save_timetable(result)

        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
