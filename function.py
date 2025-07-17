import pdfplumber
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import re
from pdf2image import convert_from_path
import os
import pandas as pd
import csv
import cv2
import numpy as np
from jiwer import wer
from sqlalchemy.orm import Session as SQLSession
from werkzeug.security import check_password_hash
from database.db_config import Session, ProductTable, InvoiceBlur, Msuser

def parse_row(row_text, full_text, filename):
    try:
        row_text = re.sub(r"[“![|~=j__—]", "", row_text)
        row_text = re.sub(r"\s{2,}", " ", row_text).strip()
        parts = row_text.split()
        if len(parts) < 5:
            return None

        line_total_str = parts[-1]

        if len(parts) >= 6 and "%" in parts[-2]:
            discount_str = parts[-2]
            unit_price_str = parts[-3]
            quantity_str = parts[-4]
            desc_parts = parts[1:-4]
        else:
            discount_str = "0%"
            unit_price_str = parts[-2]
            quantity_str = parts[-3]
            desc_parts = parts[1:-3]

        def is_product_number(token):
            return re.match(r"^(?=.*\d)[a-zA-Z0-9\-]{2,}$", token) is not None

        if parts and is_product_number(parts[0]):
            product_number = parts[0]
            description = " ".join(desc_parts).strip().lstrip('/')
        else:
            product_number = ""
            if len(parts) >= 6 and "%" in parts[-2]:
                description = " ".join(parts[:-4]).strip().lstrip('/')
            else:
                description = " ".join(parts[:-3]).strip().lstrip('/')

        quantity = int(re.sub(r"[^\d]", "", quantity_str)) if quantity_str else 0
        unit_price = float(re.sub(r"[^\d.]", "", unit_price_str)) if unit_price_str else 0.0
        line_total = float(re.sub(r"[^\d.]", "", line_total_str)) if line_total_str else 0.0
        discount = float(re.sub(r"[^\d.]", "", discount_str)) if discount_str else 0.0

        parsed_data = {
            'product_number': product_number,
            'description': description,
            'quantity': quantity,
            'unit_price': unit_price,
            'discount': discount,
            'line_total': line_total,
            'text': full_text,
            'filename': filename
        }

        return parsed_data

    except Exception as e:
        print(f"Baris gagal di parsing: '{row_text}' | Error: {e}")
        return None

def extract_text_with_ocr(image):
    try:
        custom_config = r'--oem 3 --psm 6'

        open_cv_image = np.array(image)
        if open_cv_image.ndim == 3:
            open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)

        height, width = open_cv_image.shape[:2]
        open_cv_image = cv2.resize(open_cv_image, (int(width * 2.5), int(height * 2.5)), interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)

        kernel = np.ones((5, 5), np.uint8)
        cleaned = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(cleaned)

        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        denoised = cv2.fastNlMeansDenoising(binary, h=30)

        final_image = Image.fromarray(denoised)

        page_text = pytesseract.image_to_string(final_image, config=custom_config, lang='eng')

        original_text = pytesseract.image_to_string(image, config=custom_config, lang='eng')
        ocr_wer = wer(original_text, page_text) if original_text.strip() else 1.0
        line_wer = wer_per_line(original_text, page_text)

        print(f"Original = {original_text}")
        print(f"Ekstrak = {page_text}")
        print(f"Improvement WER (vs original image): {ocr_wer:.2%}")

        return page_text, ocr_wer, line_wer

    except Exception as e:
        print(f"Error extracting text with OCR: {e}")
        return None, None

def extract_image_with_ocr(image_path):
    try:
        image = cv2.imread(image_path)

        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        merged = cv2.merge((cl, a, b))
        image = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

        sharpen_kernel = np.array([[-1, -1, -1], [-1, 9.5, -1], [-1, -1, -1]])
        image = cv2.filter2D(image, -1, sharpen_kernel)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        height, width = image.shape[:2]
        image = cv2.resize(image, (int(width * 2.5), int(height * 2.5)), interpolation=cv2.INTER_CUBIC)
        image = cv2.fastNlMeansDenoisingColored(image, None, 5, 5, 7, 21)

        output_folder = "output"
        os.makedirs(output_folder, exist_ok=True)
        filename = os.path.basename(image_path)
        filename_no_ext, ext = os.path.splitext(filename)
        enhanced_path = os.path.join(output_folder, f"{filename_no_ext}_enhanced.webp")
        cv2.imwrite(enhanced_path, image)

        pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).convert("L")
        pil_img = pil_img.point(lambda p: 255 if p > 128 else 0)

        # OCR
        custom_config = r'--oem 3 --psm 6'
        extracted_text = pytesseract.image_to_string(pil_img, config=custom_config, lang='eng')

        # Original WER comparison
        original_image = Image.open(image_path).convert("L")
        original_text = pytesseract.image_to_string(original_image, config=custom_config, lang='eng')

        ocr_wer = wer(original_text, extracted_text)
        wer_line = wer_per_line(original_text, extracted_text)

        print(f"Original = {original_text}")
        print(f"Ekstrak  = {extracted_text}")
        print(f"Improvement WER (vs original image): {ocr_wer:.2%}")

        return extracted_text, ocr_wer, wer_line

    except Exception as e:
        print(f"Error extracting text with OCR: {e}")
        return None, None
def wer_per_line(original_text, extracted_text):
    """
    Menghitung WER per baris antara original_text dan extracted_text.
    Return: list of (original, extracted, wer_value)
    """
    original_lines = [line.strip() for line in original_text.splitlines() if line.strip()]
    extracted_lines = [line.strip() for line in extracted_text.splitlines() if line.strip()]
    max_len = max(len(original_lines), len(extracted_lines))
    results = []
    for i in range(max_len):
        orig = original_lines[i] if i < len(original_lines) else ""
        extr = extracted_lines[i] if i < len(extracted_lines) else ""
        wer_value = wer(orig, extr)
        results.append((orig, extr, wer_value))
    return results

def process_file(file_path, mode="product", text_override=None, useracid=None, wer_per_line=None):
    if not os.path.exists(file_path):
        print(f"File {file_path} tidak ditemukan")
        return

    all_rows = []
    full_text = ""

    if text_override and wer_per_line:
        print("[INFO] Menggunakan wer_per_line hasil edit (tanpa OCR ulang)")
        try:
            # Ambil baris hasil edit dari wer_per_line
            rows = [row[1].strip() for row in wer_per_line if len(row) >= 2 and row[1].strip()]
            full_text = text_override  # tetap gunakan untuk konteks global di parse_row
        except Exception as e:
            print(f"[ERROR] Gagal parsing wer_per_line: {e}")
            return "error_blur"

    elif file_path.endswith('.pdf'):
        images = convert_from_path(file_path, dpi=500)
        for img in images:
            text, ocr_wer, wer_per_line = extract_text_with_ocr(img)
            if text:
                full_text += f"\n{text}"
        rows = full_text.split("\n") if full_text else []

    elif file_path.endswith('.webp'):
        text, ocr_wer, wer_per_line = extract_image_with_ocr(file_path)
        full_text = text
        rows = text.split("\n") if text else []
    else:
        print(f"File {file_path} tidak didukung")
        return "error_blur"

    filename = os.path.basename(file_path)
    print(f"[All ROWS] {all_rows}")
    for row in rows:
        row = row.strip()
        if not row:
            continue
        parsed = parse_row(row, full_text, filename)
        if parsed:
            all_rows.append(parsed)
        else:
            print(f"[PARSE FAIL] Gagal parsing baris: {row}")

    if not all_rows:
        if text_override and mode == "blur":
            print("[INFO] Tidak ada parsing valid, simpan seluruh text ke invoiceblur.")
            try:
                session = Session()
                dummy = InvoiceBlur(
                    product_number="-",
                    description="no row data available",
                    quantity=0,
                    unit_price=0.0,
                    discount=0.0,
                    line_total=0.0,
                    text=full_text,
                    filename=filename,
                    useracid=useracid
                )
                session.add(dummy)
                session.commit()
                return os.path.splitext(filename)[0] + '.csv'
            except Exception as e:
                session.rollback()
                print(f"[ERROR] Gagal simpan raw text ke invoiceblur: {e}")
                return "error_blur"
        else:
            print("[ERROR] Parsing gagal total.")
            return "error_blur"

    try:
        if mode == "blur":
            process_row_blur(all_rows, useracid)
        else:
            process_row(all_rows, useracid)
    except Exception as e:
        print(f"[ERROR] Gagal menyimpan hasil parsing ke database: {e}")
        return "error_blur"

    try:
        csv_rows = [[
            row['product_number'],
            row['description'],
            row['quantity'],
            row['unit_price'],
            row['discount'],
            row['line_total']
        ] for row in all_rows]

        folder = os.path.dirname(file_path)
        csvname = os.path.splitext(filename)[0] + '.csv'
        csv_path = os.path.join(folder, csvname)
        write_csv_with_delimiter(csv_path, csv_rows, ";")
        print(f"[CSV] Disimpan ke: {csv_path}")
        return csvname
    except Exception as e:
        print(f"[ERROR] Gagal menyimpan CSV: {e}")
        return "error_blur"

def write_csv_with_delimiter(filename, allrows, delimiter):
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, delimiter=delimiter)
        writer.writerow(["Product Number", "Description", "Quantity", "Unit Price", "Discount", "Line Total"])
        writer.writerows(allrows)

def process_row(rows, useracid):
    session = Session()
    for row in rows:
        if not row:
            continue

        try:
            product = ProductTable(
                product_number=row['product_number'],
                description=row['description'],
                quantity=row['quantity'],
                unit_price=row['unit_price'],
                discount=row.get('discount', 0.0),
                line_total=row['line_total'],
                text=row['text'],
                filename=row['filename'],
                useracid=useracid
            )
            session.add(product)
            session.commit()
            print(f"[SAVED] Product: {product.product_number}, {product.description}")
        except Exception as e:
            session.rollback()
            print(f"[ERROR] Gagal simpan product row: {row}. Error: {e}")
    session.close()

def process_row_blur(rows, useracid):
    print(f"[DEBUG] total rows untuk blur: {len(rows)}")
    session = Session()
    for row in rows:
        if not row:
            continue
        try:
            product_blur = InvoiceBlur(
                product_number=row['product_number'],
                description=row['description'],
                quantity=row['quantity'],
                unit_price=row['unit_price'],
                discount=row.get('discount', 0.0),
                line_total=row['line_total'],
                text=row['text'],
                filename=row['filename'],
                useracid=useracid
            )
            session.add(product_blur)
            session.commit()
            print(f"[BLUR SAVED] {product_blur.product_number}, {product_blur.description}")
        except Exception as e:
            session.rollback()
            print(f"[BLUR ERROR] Gagal simpan row: {row}. Error: {e}")
    session.close()
