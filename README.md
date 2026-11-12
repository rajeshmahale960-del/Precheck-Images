# Images Precheck

**Images Precheck** is a desktop application designed to automate product image validation using Google Drive.

## What It Does

The application scans Google Drive folders and subfolders against a provided list of SKUs. It validates folder names, identifies missing or mismatched SKUs, checks image availability, and flags folders that do not meet the minimum image requirements.

It automatically categorizes validation results to help identify product image issues quickly and reduce manual verification.

## Supported File Types

The application supports the following image formats:

- JPG / JPEG
- PNG
- WEBP
- BMP
- AVIF
- HEIF / HEIC

## Why Tkinter?

Tkinter was chosen for its simplicity and lightweight nature. It is included with Python, requires minimal setup, and provides all the essential components needed to build a straightforward desktop interface without introducing unnecessary complexity.

## Report Structure

The generated CSV report contains two columns:

| Column | Description |
|---|---|
| Folder Name | SKU or folder name identified during validation |
| Remark | Validation result or issue associated with the folder |

The report identifies the following results:

- **OK** – SKU folder exists and contains more than two images.
- **Missing** – SKU folder does not exist.
- **SKU not Matching** – Folder name differs in capitalization from the provided SKU.
- **SKU has Special Char** – SKU contains special characters that are invalid in Windows folder names.
- **SKU has space** – SKU contains spaces.
- **Need more Images** – SKU folder contains two or fewer images.

## Report Download Location

CSV reports are automatically saved to the user's **Downloads** folder.

Each report receives a sequential filename:

- `Report_1.csv`
- `Report_2.csv`
- `Report_3.csv`

Existing reports are preserved, and the next available filename is used.
