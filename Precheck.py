import csv
import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs, unquote

import requests

INVALID_WINDOWS_CHARS = re.compile(r'[<>:"/\\|?*]')
FOLDER_ID_RE = re.compile(r"/folders/([A-Za-z0-9_-]+)")
FILE_ID_RE = re.compile(r"/file/d/([A-Za-z0-9_-]+)")
ALT_FILE_ID_RE = re.compile(r"(?:[?&]id=)([A-Za-z0-9_-]+)")
ALLOWED_IMAGE_EXTENSIONS = {
    ".webp",
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".avif",
    ".heif",
    ".heic",
}


STATE = {
    "skus": [],
    "drive_link": "",
    "report_rows": [],
    "initialized": False,
}


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def progress(value):
    emit({"type": "progress", "id": "PROGRESS", "value": max(0, min(100, int(value)))})


def status(text):
    emit({"type": "status", "id": "STATUS", "text": text})


def error(text="Failed"):
    message = ("Please Update Access to Anyone with Link"
               if "Please Update Access to Anyone with Link" in str(text)
               else "Failed")
    emit({"type": "error", "id": "ERROR", "text": message})


def button_status(button_id, clickable):
    emit({"type": "button_status", "id": button_id, "clickable": bool(clickable)})


def parse_skus(value):
    # Initial Electron input uses comma-separated SKUs. Newlines are also accepted.
    parts = re.split(r"[,\n]", value or "")
    return [p.strip() for p in parts if p.strip()]


def extract_drive_folder_id(url):
    url = (url or "").strip()
    parsed = urlparse(url)
    if "drive.google.com" not in parsed.netloc.lower():
        return None
    match = FOLDER_ID_RE.search(parsed.path)
    if match:
        return match.group(1)
    query = parse_qs(parsed.query)
    if query.get("id"):
        return query["id"][0]
    return None


def direct_file_link(file_id):
    return f"https://drive.google.com/uc?export=download&id={file_id}"



class DriveHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.current_href = None
        self.current_text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.current_href = href
            self.current_text = []

    def handle_data(self, data):
        if self.current_href is not None:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.current_href is not None:
            text = " ".join("".join(self.current_text).split())
            self.links.append((self.current_href, text))
            self.current_href = None
            self.current_text = []


def parse_embedded_folder(html):
    parser = DriveHTMLParser()
    parser.feed(html)
    children = []
    seen = set()
    for href, name in parser.links:
        href = unquote(href)
        folder_match = FOLDER_ID_RE.search(href)
        if folder_match:
            item_id = folder_match.group(1)
            key = ("folder", item_id)
            if item_id and key not in seen:
                seen.add(key)
                children.append({"id": item_id, "name": name, "type": "folder"})
            continue
        file_match = FILE_ID_RE.search(href)
        if file_match:
            item_id = file_match.group(1)
            key = ("file", item_id)
            if item_id and key not in seen:
                seen.add(key)
                children.append({"id": item_id, "name": name, "type": "file"})
            continue
        if "/file" in href or "open?id=" in href:
            id_match = ALT_FILE_ID_RE.search(href)
            if id_match:
                item_id = id_match.group(1)
                key = ("file", item_id)
                if item_id and key not in seen:
                    seen.add(key)
                    children.append({"id": item_id, "name": name, "type": "file"})
    return children


def scan_public_drive(root_id, required_skus):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36"
    })
    folders, files = [], []
    q = [(root_id, "", None)]
    queued, scanned = {root_id}, set()
    total_to_scan = 1
    completed = 0

    def owner_for(name, inherited):
        for sku in required_skus:
            if name == sku:
                return sku
        return inherited

    while q:
        folder_id, folder_name, inherited_owner = q.pop(0)
        if folder_id in scanned:
            continue
        scanned.add(folder_id)
        owner = owner_for(folder_name, inherited_owner)
        response = session.get(
            f"https://drive.google.com/embeddedfolderview?id={folder_id}",
            timeout=60,
        )
        response.raise_for_status()
        children = parse_embedded_folder(response.text)
        folders.append({"id": folder_id, "name": folder_name, "sku_owner": owner})

        for child in children:
            if child["type"] == "folder":
                child_id = child["id"]
                if child_id not in queued:
                    queued.add(child_id)
                    q.append((child_id, child["name"], owner))
                    total_to_scan += 1
            elif child["type"] == "file" and owner:
                # Accept only the specified image formats.
                extension = os.path.splitext(child["name"])[1].lower()
            
                if extension not in ALLOWED_IMAGE_EXTENSIONS:
                    continue
            
                files.append({
                    "folder_id": folder_id,
                    "folder_name": child["name"],
                    "sku_owner": owner,
                    "file_id": child["id"],
                    "file_name": child["name"],
                    "url": direct_file_link(child["id"]),
                })

        completed += 1
        pct = int((completed / max(total_to_scan, 1)) * 100)
        if q:
            pct = min(pct, 99)
        progress(pct)

    progress(100)
    return folders, files


def build_results(required_skus, folders, files):
    image_rows = sorted(
        [[f["sku_owner"], f["url"]] for f in files if f.get("sku_owner")],
        key=lambda row: (row[0].casefold(), row[0], row[1]),
    )
    counts = {}
    for sku, _url in image_rows:
        counts[sku] = counts.get(sku, 0) + 1

    searchable = [f for f in folders if f["name"]]
    report_rows = []
    for sku in required_skus:
        exact = [f for f in searchable if f["name"] == sku]
        if exact:
            count = counts.get(sku, 0)
            if INVALID_WINDOWS_CHARS.search(sku):
                remark = "SKU has Special Char"
            elif " " in sku:
                remark = "SKU has space"
            elif count <= 2:
                remark = "Need more Images"
            else:
                remark = "OK"
            report_rows.append([sku, remark])
            continue
        mismatch = [f for f in searchable if f["name"].lower() == sku.lower() and f["name"] != sku]
        report_rows.append([mismatch[0]["name"], "SKU not Matching"] if mismatch else [sku, "Missing"])

    return report_rows, image_rows


def write_csv(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(rows)


def handle_scan():
    folder_id = extract_drive_folder_id(STATE["drive_link"])
    if not folder_id:
        error("Failed")
        button_status("REPORT_CSV", False)
        return

    status("Scanning Google Drive...")
    try:
        folders, files = scan_public_drive(folder_id, STATE["skus"])
    except requests.HTTPError as exc:
        response = getattr(exc, "response", None)
        if response is not None and response.status_code in (401, 403, 404):
            error("Please Update Access to Anyone with Link")
        else:
            error("Failed")
        button_status("REPORT_CSV", False)
        return
    except Exception:
        error("Failed")
        button_status("REPORT_CSV", False)
        return

    report_rows, _image_rows = build_results(STATE["skus"], folders, files)
    STATE["report_rows"] = report_rows

    report_clickable = any(remark != "OK" for _sku, remark in report_rows)
    button_status("SCAN", True)
    button_status("REPORT_CSV", report_clickable)
    status("Scan completed.")
    emit({"type": "complete", "id": "SCAN_COMPLETE"})


def next_report_path():
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    os.makedirs(downloads, exist_ok=True)
    index = 1
    while True:
        path = os.path.join(downloads, f"Report_{index}.csv")
        if not os.path.exists(path):
            return path
        index += 1


def handle_report_csv():
    if not STATE["report_rows"]:
        status("No report data available. Click Process first.")
        emit({"type": "complete", "id": "REPORT_CSV_COMPLETE", "success": False})
        return
    path = next_report_path()
    status("Creating report in your Downloads folder...")
    write_csv(path, ["Folder Name", "Remark"], STATE["report_rows"])
    progress(100)
    status(f"Report saved: {os.path.basename(path)}")
    emit({"type": "complete", "id": "REPORT_CSV_COMPLETE", "path": path})

def handle_button(button):
    if button == "SCAN":
        handle_scan()
    elif button == "REPORT_CSV":
        handle_report_csv()
    else:
        error("Failed")


def initialize(data):
    if not isinstance(data, dict):
        raise ValueError("Initial input must be a JSON object.")
    skus = parse_skus(data.get("SKU", ""))
    drive_link = str(data.get("drive_link", "")).strip()
    if not skus:
        raise ValueError("SKU is required.")
    if not drive_link:
        raise ValueError("drive_link is required.")
    STATE["skus"] = skus
    STATE["drive_link"] = drive_link
    STATE["initialized"] = True


def main():
    first = sys.stdin.readline()
    if not first:
        return
    try:
        # Decode the initial payload robustly and give a clearer error if the
        # launcher accidentally appends a second JSON object on the same line.
        decoder = json.JSONDecoder()
        initial, end = decoder.raw_decode(first.lstrip())
        trailing = first.lstrip()[end:].strip()
        if trailing:
            try:
                extra, extra_end = decoder.raw_decode(trailing)
                if trailing[extra_end:].strip() or not isinstance(initial, dict) or not isinstance(extra, dict):
                    raise ValueError("Unexpected extra data after the initial JSON configuration.")
                initial = {**initial, **extra}
            except json.JSONDecodeError:
                raise ValueError("Invalid startup configuration: extra text follows the JSON object. Check the launcher input.")
        initialize(initial)
    except Exception as exc:
        error("Failed")
        return

    emit({"type": "ready", "id": "BACKEND_READY"})
    button_status("SCAN", True)
    button_status("REPORT_CSV", False)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        # Be tolerant of launchers that accidentally concatenate multiple JSON
        # command objects onto one line (the source of "Extra data ... char 160").
        decoder = json.JSONDecoder()
        offset = 0
        while offset < len(line):
            while offset < len(line) and line[offset].isspace():
                offset += 1
            if offset >= len(line):
                break
            try:
                command, end = decoder.raw_decode(line, offset)
                offset = end
                if not isinstance(command, dict) or "button" not in command:
                    error("Failed")
                    continue
                handle_button(command["button"])
            except Exception as exc:
                error("Failed")
                break


if __name__ == "__main__":
    main()
