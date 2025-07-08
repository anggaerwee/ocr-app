import pdfplumber
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
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

def login_user(db_session: SQLSession, username: str, password: str):

    user = db_session.query(Msuser).filter_by(usernm=username).first()

    if not user:
        return None

    if user.pswd == password:
        return user

    return None

# def parse_row(row_text, full_text, filename):
#     try:
#         row_text = re.sub(r"[“![|~=j__—]", "", row_text)
#         row_text = re.sub(r"\s{2,}", " ", row_text).strip() 
#         parts = row_text.split()
#         if len(parts) < 5:
#             return None

#         line_total_str = parts[-1]
#         possible_discount_str = parts[-2]

#         if "%" in possible_discount_str:
#             description_end_index = -4
#             quantity_str = parts[-4]
#             unit_price_str = parts[-3]
#             discount_str = possible_discount_str
#         else:
#             description_end_index = -3
#             quantity_str = parts[-3]
#             unit_price_str = parts[-2]
#             discount_str = None

#         if re.match(r"^p\S*$", parts[0], re.IGNORECASE) or re.match(r"^\d{4,6}$", parts[0]):
#             product_number = parts[0]
#             description_parts = parts[1:description_end_index]
#         else:
#             product_number = ""
#             description_parts = parts[0:description_end_index]

#         description = " ".join(description_parts).strip().lstrip('/')

#         quantity = int(re.sub(r"[^\d]", "", quantity_str))
#         unit_price = float(re.sub(r"[^\d.]", "", unit_price_str))
#         line_total = float(re.sub(r"[^\d.]", "", line_total_str))
#         discount = float(re.sub(r"[^\d.]", "", discount_str)) if discount_str else None

#         return (
#             product_number,
#             description,
#             quantity,
#             "{:.2f}".format(unit_price),
#             "{:.2f}".format(discount) if discount is not None else None,
#             "{:.2f}".format(line_total),
#             full_text,
#             filename,
#         )
    
#     except Exception as e:
#         print(f"Baris gagal di parsing: {e}")
#         return None
    
# def safe_int(value):
#     try:
#         return int(re.sub(r"[^\d]", "", value))
#     except:
#         return 0

# def safe_float(value):
#     try:
#         return float(re.sub(r"[^\d.]", "", value))
#     except:
#         return 0.0

def parse_row(row_text, full_text, filename):
    try:
        # Bersihkan karakter aneh dan whitespace berlebih
        row_text = re.sub(r"[“![|~=j__—]", "", row_text)
        row_text = re.sub(r"\s{2,}", " ", row_text).strip()

        # Split baris jadi bagian
        parts = row_text.split()
        if len(parts) < 5:
            print(f"[PARSE SKIP] Jumlah bagian terlalu sedikit: {parts}")
            return None

        line_total_str = parts[-1]
        possible_discount_str = parts[-2]

        if "%" in possible_discount_str:
            description_end_index = -4
            quantity_str = parts[-4]
            unit_price_str = parts[-3]
            discount_str = possible_discount_str
        else:
            description_end_index = -3
            quantity_str = parts[-3]
            unit_price_str = parts[-2]
            discount_str = None

        if re.match(r"^p\S*$", parts[0], re.IGNORECASE) or re.match(r"^\d{4,6}$", parts[0]):
            product_number = parts[0]
            description_parts = parts[1:description_end_index]
        else:
            product_number = ""
            description_parts = parts[0:description_end_index]

        description = " ".join(description_parts).strip().lstrip('/')

        # Konversi angka
        quantity = int(re.sub(r"[^\d]", "", quantity_str) or "0")
        unit_price = float(re.sub(r"[^\d.]", "", unit_price_str) or "0")
        line_total = float(re.sub(r"[^\d.]", "", line_total_str) or "0")
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

        print(f"[PARSE OK] {parsed_data}")
        return parsed_data

    except Exception as e:
        print(f"[PARSE FAIL] Baris gagal di parsing: '{row_text}' | Error: {e}")
        return None

def extract_text_with_ocr(file_path, page_number):
    try:
        images = convert_from_path(file_path, first_page=page_number, last_page=page_number, dpi=500)

        if not images:
            print(f"Tidak ada halaman yang dapat diproses dari file {file_path}")
            return None
        
        extracted_text = ""
        for image in images:
            
            custom_config = r'--oem 3 --psm 6'
            page_text = pytesseract.image_to_string(image, config=custom_config, lang='eng+ind')
            extracted_text += page_text 
        
        return extracted_text.strip()
    except Exception as e:
        print(f"Error extracting text with OCR: {e}")
        return None

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

        image = cv2.fastNlMeansDenoisingColored(image, None, 5, 5, 7, 21)

        height, width = image.shape[:2]
        image = cv2.resize(image, (int(width * 2.5), int(height * 2.5)), interpolation=cv2.INTER_CUBIC)

        output_folder = "output"
        os.makedirs(output_folder, exist_ok=True)
        filename = os.path.basename(image_path)
        filename_no_ext, ext = os.path.splitext(filename)
        enhanced_path = os.path.join(output_folder, f"{filename_no_ext}_enhanced.webp")
        cv2.imwrite(enhanced_path, image)

        pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).convert("L")
        pil_img = pil_img.point(lambda p: 255 if p > 128 else 0)


        custom_config = r'--oem 3 --psm 6' 
        extracted_text = pytesseract.image_to_string(pil_img, config=custom_config, lang='eng+ind')

        original_image = Image.open(image_path).convert("L")
        original_text = pytesseract.image_to_string(original_image, config=custom_config, lang='eng+ind') 

        ocr_wer = wer(original_text, extracted_text) 

        print(f"Original = {original_text}") 
        print(f"Ekstrak = {extracted_text}") 
        print(f"Improvement WER (vs original image): {ocr_wer:.2%}") 
        return extracted_text, ocr_wer

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

# def process_file(file_path, mode="product", text_override=None, useracid=None):
#     if not os.path.exists(file_path):
#         print(f"File {file_path} tidak ditemukan")
#         return

#     all_rows = []
#     full_text = ""

#     if text_override:
#         full_text = text_override
#         rows = text_override.split("\n")
#     elif file_path.endswith('.pdf'):
#         with pdfplumber.open(file_path) as pdf:
#             for page_number, page in enumerate(pdf.pages, start=1):
#                 try:
#                     text = extract_text_with_ocr(file_path, page_number)
#                     if text:
#                         full_text += text + "\n"
#                 except Exception as e:
#                     print(f"Error reading page {page_number}: {e}")
#         rows = full_text.split("\n")
#     elif file_path.endswith('.webp'):
#         text, ocr_wer = extract_image_with_ocr(file_path)
#         # print(f"Ekstrak Teks {text}")
#         full_text = text
#         rows = text.split("\n") if text else []
#     else:
#         print(f"File {file_path} tidak didukung")
#         return ""

#     filename = os.path.basename(file_path)
#     for row in rows:
#         row = row.strip()
#         if not row:
#             continue
#         parsed = parse_row(row, full_text, filename)
#         if parsed:
#             all_rows.append(parsed)
#             print(parsed)
#         else:
#             print(f"[PARSE FAIL] Gagal parsing baris: {row}")
 
#     if not all_rows:
#         if text_override and mode == "blur":
#             print("[INFO] Tidak ada parsing valid, simpan seluruh text ke invoiceblur.")
#             try:
#                 session = Session()
#                 dummy = InvoiceBlur(
#                     product_number="-",
#                     description="no row data available",
#                     quantity=0,
#                     unit_price=0.0,
#                     discount=0.0,
#                     line_total=0.0,
#                     text=full_text,
#                     filename=filename,
#                     useracid=useracid
#                 )
#                 session.add(dummy)
#                 session.commit()
#                 print("[SAVED] Raw text berhasil disimpan ke invoiceblur.")
#                 return os.path.splitext(filename)[0] + '.csv'
#             except Exception as e:
#                 session.rollback()
#                 print(f"[ERROR] Gagal simpan raw text ke invoiceblur: {e}")
#                 return "error_blur"
#         else:
#             print("[ERROR] Parsing gagal total, tanpa override.")
#             return "error_blur"

#     try:
#         if mode == "blur":
#             process_row_blur(all_rows)
#         else:
#             process_row(all_rows)
#     except Exception as e:
#         print(f"[ERROR] Gagal menyimpan hasil parsing ke database: {e}")
#         return "error_blur"

#     try:
#         csv_rows = [row[:6] for row in all_rows]
#         folder = os.path.dirname(file_path)
#         csvname = os.path.splitext(filename)[0] + '.csv'
#         csv_path = os.path.join(folder, csvname)
#         write_csv_with_delimiter(csv_path, csv_rows, ";")
#         print(f"[CSV] Disimpan ke: {csv_path}")
#         return csvname
#     except Exception as e:
#         print(f"[ERROR] Gagal menyimpan CSV: {e}")
#         return "error_blur"

def process_file(file_path, mode="product", text_override=None, useracid=None):
    if not os.path.exists(file_path):
        print(f"File {file_path} tidak ditemukan")
        return

    all_rows = []
    full_text = ""

    if text_override:
        full_text = text_override
        rows = text_override.split("\n")
    elif file_path.endswith('.pdf'):
        with pdfplumber.open(file_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                try:
                    text = extract_text_with_ocr(file_path, page_number)
                    if text:
                        full_text += text + "\n"
                except Exception as e:
                    print(f"Error reading page {page_number}: {e}")
        rows = full_text.split("\n")
    elif file_path.endswith('.webp'):
        text, ocr_wer = extract_image_with_ocr(file_path)
        full_text = text
        rows = text.split("\n") if text else []
    else:
        print(f"File {file_path} tidak didukung")
        return "error_blur"

    filename = os.path.basename(file_path)
    for row in rows:
        row = row.strip()
        if not row:
            continue
        parsed = parse_row(row, full_text, filename)
        if parsed:
            all_rows.append(parsed)
            print(parsed)
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


# def write_csv_with_delimiter(filename, allrows, delimiter):
#     with open(filename, mode="w", newline="", encoding="utf-8") as file:
#         df = pd.DataFrame(columns=["Product Number", "Description", "Quantity", "Unit Price", "Discount", "Line Total"]) 
#         df.to_csv(file, index=False, sep=delimiter, header=True)
#         writer = csv.writer(file, delimiter=delimiter,)
#         writer.writerows(allrows)
        
def write_csv_with_delimiter(filename, allrows, delimiter):
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, delimiter=delimiter)
        writer.writerow(["Product Number", "Description", "Quantity", "Unit Price", "Discount", "Line Total"])
        writer.writerows(allrows)

# def process_row(rows, useracid):
#     session = Session()
#     for parsed_row in rows:
#         if not parsed_row:
#             continue

#         try:
#             product_number, description, quantity, unit_price, discount, line_total, text, filename  = parsed_row

#             product = ProductTable(
#                 product_number=str(product_number).strip(),
#                 description=str(description).strip(),
#                 quantity=quantity,
#                 unit_price=unit_price,
#                 line_total=line_total,
#                 discount=discount,
#                 text=text,
#                 filename=filename,
#                 useracid=useracid
#             )
                        
#             session.add(product)
#             session.commit()
#             print(f"Data berhasil disimpan: {product_number}, {description}, {quantity}, {unit_price}, {discount} ,{line_total}")
#         except Exception as e:
#             session.rollback()
#             print(f"Kesalahan pada baris: {parsed_row}. Error: {e}")

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

# def process_row_blur(rows,useracid):
#     print(f"[DEBUG] total rows untuk blur: { len(rows)}")
#     session = Session()
#     for parsed_row in rows:
#         if not parsed_row:
#             continue
#         try:
#             product_number, description, quantity, unit_price, discount, line_total, text, filename = parsed_row

#             product_blur = InvoiceBlur(
#                 product_number=str(product_number).strip(),
#                 description=str(description).strip(),
#                 quantity=quantity,
#                 unit_price=unit_price,
#                 line_total=line_total,
#                 discount=discount,
#                 text=text,
#                 filename=filename,
#                 useracid=useracid
#             )

#             session.add(product_blur)
#             session.commit()
#             print(f"[BLUR] Data berhasil disimpan ke invoiceblur: {product_number}, {description}, {quantity}, {unit_price}, {discount} ,{line_total}")
#         except Exception as e:
#             session.rollback()
#             print(f"[BLUR] Gagal simpan ke invoiceblur untuk baris: {parsed_row}. Error: {e}")

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
