---
name: timetable-fetcher
description: Agent skill to fetch timetable data from the university portal using user cookies, format it using extract_timetable, and output the data as JSON. Supports fetching next week's schedule and detecting changes against a local cache.
---

# Timetable Fetcher Skill

This skill allows the Agent to automatically fetch timetable data from the `sinhvien.hdu.edu.vn` portal using the user's cookies, make an authenticated POST query, and process the returned HTML using the `extract_timetable.py` script to generate a structured JSON object.

## Overview

- **Source Code:** `scripts/fetch_timetable.py`
- **Dependencies:** `python-dotenv`, `requests`, `bs4`
- **Inputs:** `COOKIES` mapped within the `.env` file in this skill's root directory.
- **Outputs:** JSON format parsing dates as `dd/mm/yyyy` and returning lists of subjects, periods (`period`), room numbers (`room`), event type (`event_type`), and exam time (`exam_time` — only present for exams).
- **Cache file:** `timetable.json` in this skill's root directory — stores the last fetched timetable and is used for update detection.

## Usage

```bash
# Fetch current week's timetable (default uses .env)
python scripts/fetch_timetable.py

# Use cookie directly from CLI (updates .env automatically)
python scripts/fetch_timetable.py --cookie "your_cookie_here"

# Use cookie from a file
python scripts/fetch_timetable.py --cookie-file cookie.txt

# Fetch next week's timetable
python scripts/fetch_timetable.py --next-week

# Check for updates vs. cached timetable.json
python scripts/fetch_timetable.py --check-update
```

### Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--next-week` | `-n` | Shifts the request timestamp by +7 days so the server returns next week's schedule. |
| `--check-update` | `-c` | Compares the freshly fetched timetable against `timetable.json`. |
| `--cookie` | `-k` | Provides the `ASC.AUTH` cookie value directly. Updates `.env` on success. |
| `--cookie-file` | | Provides a path to a file containing the cookie value. |
| `--env` | | Path to the `.env` file (defaults to `.env` in skill root). |

### Output format (single fetch)

Each element in the returned array represents one day of the week:

```json
[
  {
    "date": "dd/mm/yyyy",
    "classes": [
      {
        "subject": "Tên môn học",
        "period": "1-3",
        "room": "A1.101",
        "event_type": "class"
      },
      {
        "subject": "Tên môn thi",
        "period": "6-7",
        "room": "A6.B.305",
        "event_type": "exam",
        "exam_time": "14h00"
      }
    ]
  }
]
```

#### Fields per class entry

| Field | Always present | Description |
|-------|---------------|-------------|
| `subject` | ✓ | Tên môn học / thi |
| `period` | ✓ | Tiết bắt đầu – kết thúc (e.g. `"1-3"`) |
| `room` | ✓ | Phòng học / phòng thi |
| `event_type` | ✓ | `"class"` = lịch học, `"exam"` = lịch thi |
| `exam_time` | Chỉ khi `event_type == "exam"` | Giờ thi cụ thể (e.g. `"14h00"`) |

### `--check-update` output format

```json
{
  "has_update": true,
  "old": [ { "date": "dd/mm/yyyy", "classes": [ ... ] } ],
  "new": [ { "date": "dd/mm/yyyy", "classes": [ ... ] } ]
}
```

- `has_update` — `true` if the new timetable differs from the cached one, `false` otherwise.
- `old` — the timetable stored in `timetable.json` before this run (`null` if the file did not exist yet).
- `new` — the freshly fetched timetable.

The Agent should diff `old` vs `new` to describe the specific changes to the user (e.g. room change, added/removed class, added/removed exam).

## Instructions for Agent

1. Check if the `.env` file in this skill's root directory contains the `COOKIES` key.
2. If `requests` or `python-dotenv` are not installed, run `pip install requests python-dotenv bs4 lxml`.
3. Run the script with the appropriate flags for the task:
   - **Default (current week):** `python scripts/fetch_timetable.py`
   - **Next week:** `python scripts/fetch_timetable.py --next-week`
   - **Detect changes:** `python scripts/fetch_timetable.py --check-update`
4. The script outputs the schedule as JSON. Each class entry contains `"subject"`, `"period"`, `"room"`, and `"event_type"`. Exam entries additionally contain `"exam_time"`.
5. **Distinguish class vs exam using `event_type`**:
   - `"class"` — regular lecture/lab. Notify the user about the class start time derived from the period number.
   - `"exam"` — exam session. Notify the user using the explicit `"exam_time"` field (e.g. `"14h00"`) instead of the period-based lookup. Always highlight exam entries prominently when reporting the schedule to the user.
6. When `--check-update` is used and `has_update` is `true`, compare `old` and `new` to summarise what changed for the user. Pay special attention to any newly added or removed entries where `event_type == "exam"`.
7. **Class Schedule Notification**: To notify users about an upcoming class (`event_type == "class"`), use `lesson-start-time-schema.json` as a basis to find the actual start time:
   - Extract the start period from the `"period"` string (e.g., if `"period"` is `"1-3"`, the start lesson is `1`).
   - Match this lesson number inside `lesson-start-time-schema.json`.
   - Based on the current season (winter for Oct–Apr, summer for May–Sep), look up the exact `start_time` (e.g. `"07:00"` for winter lesson 1).
   - Use this `start_time` to schedule or trigger notifications for the user accurately.
8. **Exam Notification**: For entries where `event_type == "exam"`, use `"exam_time"` directly as the exam start time — do **not** perform a period-to-time lookup.

## Development & Maintenance

- If the HTML structure changes, modify `parse_html_to_json` in `scripts/extract_timetable.py`.
- If the required headers/parameters for `https://sinhvien.hdu.edu.vn/SinhVien/GetDanhSachLichTheoTuan` change, update `scripts/fetch_timetable.py` directly.
- The cache file `timetable.json` is written automatically; do not hand-edit it.
