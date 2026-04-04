import os
import sys
from datetime import date, timedelta
import argparse
import requests
import json
from dotenv import load_dotenv

from extract_timetable import parse_html_to_json

# Skill root is one level up
SKILL_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TIMETABLE_CACHE_PATH = os.path.join(SKILL_ROOT, "timetable.json")




def load_cached_timetable():
    """Load the previously saved timetable from timetable.json, or None if not found."""
    if not os.path.exists(TIMETABLE_CACHE_PATH):
        return None
    try:
        with open(TIMETABLE_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_timetable(data):
    """Save timetable data to timetable.json."""
    with open(TIMETABLE_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_timetable_data(next_week=False):
    # Load environment variables from .env file located in skill root
    env_path = os.path.join(SKILL_ROOT, ".env")
    load_dotenv(dotenv_path=env_path)

    # Get the raw COOKIES string from .env
    cookies_raw = os.getenv("COOKIES")
    if not cookies_raw:
        return {"error": "COOKIES not found in .env"}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:148.0) Gecko/20100101 Firefox/148.0",
        "Accept": "text/html, */*; q=0.01",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://sinhvien.hdu.edu.vn",
        "Connection": "keep-alive",
        "Cookie": cookies_raw,
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
    args = parser.parse_args()

    result = fetch_timetable_data(next_week=args.next_week)

    if args.check_update:
        cached = load_cached_timetable()
        has_update = result != cached

        output = {
            "has_update": has_update,
            "old": cached,
            "new": result,
        }

        # Save the freshly fetched timetable AFTER building the output,
        # so the caller still has the old data available for diffing.
        if not isinstance(result, dict) or "error" not in result:
            save_timetable(result)

        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
