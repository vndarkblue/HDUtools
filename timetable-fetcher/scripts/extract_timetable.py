import html
from bs4 import BeautifulSoup
import os
import sys
import json
import re

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

def parse_html_to_json(content):
    soup = BeautifulSoup(content, 'html.parser')
    
    # Locate the table
    table = soup.find('table', class_='table')
    if not table:
        return {"error": "Table not found in HTML."}

    # 1. Parse Headers to get Days
    # We need to map column index to Date
    days_map = [] # List of { "date": "DDMMYYYY", "raw_header": "..." }
    
    thead = table.find('thead')
    if thead:
        header_row = thead.find('tr')
        if header_row:
            th_cells = header_row.find_all('th')
            # Skip the first one ("Ca học")
            for th in th_cells[1:]:
                # structure: <span>Thứ 2</span><br>26/01/2026
                # text might be "Thứ 2 26/01/2026"
                text = th.get_text(separator=" ", strip=True)
                
                # Extract date 26/01/2026
                # Regex to find dd/mm/yyyy
                match = re.search(r'(\d{2})/(\d{2})/(\d{4})', text)
                if match:
                    # Format as dd/mm/yyyy
                    date_clean = match.group(0)
                else:
                    date_clean = text # Fallback

                days_map.append(date_clean)
    
    # Structure to hold results: List of objects per day? Or Dict?
    # User asked for "Ngày", "Tên môn", "Tiết", "Phòng". 
    # Let's create a list of objects, one per day.
    timetable_data = []
    
    # Initialize entries for each day found in header
    # We'll use a dictionary simply to aggregate classes quickly, then convert to list
    data_by_day = {date: [] for date in days_map}

    # 2. Parse Body to get Classes per Day
    tbody = table.find('tbody')
    if tbody:
        rows = tbody.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if not cells:
                continue
            
            # First cell is Session (Sáng, Chiều, Tối) - Not requested in JSON output specifically but good for context?
            # User only asked for: Ngày, Tên môn, Tiết bắt đầu, Phòng.
            # We can ignore Session for the output structure if strict, but let's just parse.
            
            # Remaining cells correspond to headers
            course_cells = cells[1:]
            
            for index, cell in enumerate(course_cells):
                if index >= len(days_map):
                    break
                
                current_date = days_map[index]
                
                # Find course blocks in this cell
                pass_blocks = cell.find_all('div', class_='content')
                
                for block in pass_blocks:
                    # Extract Details
                    subject_tag = block.find('b').find('a')
                    raw_subject = subject_tag.get_text(separator=" ", strip=True) if subject_tag else "N/A"
                    # Clean up: replace newlines and list of spaces with single space
                    subject_name = re.sub(r'\s+', ' ', raw_subject).strip()
                    
                    period = ""
                    room = "N/A"
                    
                    p_tags = block.find_all('p')
                    for p in p_tags:
                        text = p.get_text(separator=" ", strip=True)
                        if "Tiết" in text and ":" in text:
                            parts = text.split(":")
                            if len(parts) > 1:
                                period = parts[1].strip().replace(" ", "") # e.g. "1-3"
                                    
                        elif "Phòng" in text and ":" in text:
                             parts = text.split(":")
                             if len(parts) > 1:
                                room = parts[1].strip()
                    
                    class_info = {
                        "subject": subject_name,
                        "period": period,
                        "room": room
                    }
                    
                    data_by_day[current_date].append(class_info)

    # [ { "date": "...", "classes": [...] }, ... ]
    final_output = []
    for date in days_map:
        final_output.append({
            "date": date,
            "classes": data_by_day[date]
        })

    return final_output

def extract_timetable(file_path):
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
    with open(file_path, 'r', encoding='utf-8') as f:
        return parse_html_to_json(f.read())

if __name__ == "__main__":
    file_path = "sample.html"
    result = extract_timetable(file_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
