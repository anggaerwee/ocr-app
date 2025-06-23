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

from database.db_config import Session, ProductTable, InvoiceBlur
def parse_row(row_text, full_text, filename):
    try:
        row_text = re.sub(r"[“![|~=j__—]", "", row_text)
        row_text = re.sub(r"\s{2,}", " ", row_text).strip() 
        parts = row_text.split()
        if len(parts) < 5:
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

        quantity = int(re.sub(r"[^\d]", "", quantity_str))
        unit_price = float(re.sub(r"[^\d.]", "", unit_price_str))
        line_total = float(re.sub(r"[^\d.]", "", line_total_str))
        discount = float(re.sub(r"[^\d.]", "", discount_str)) if discount_str else None

        return (
            product_number,
            description,
            quantity,
            "{:.2f}".format(unit_price),
            "{:.2f}".format(discount) if discount is not None else None,
            "{:.2f}".format(line_total),
            full_text,
            filename,
        )
    
    except Exception as e:
        print(f"Baris gagal di parsing: {e}")
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
        image = Image.open(image_path)
        image = image.convert("L")

        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)
        width, height = image.size
        image = image.resize((width * 4, height * 4), Image.Resampling.LANCZOS)

        image = image.filter(ImageFilter.MedianFilter(size=3))
        image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=253, threshold=3))

        threshold = 128
        image = image.point(lambda p: 255 if p > threshold else 0)

        output_folder = "output"
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        filename, file_extension = os.path.splitext(os.path.basename(image_path))
        output_path = os.path.join(output_folder, f"{filename}_enhanced{file_extension}")
        image.save(output_path)

        custom_config = r'--oem 3 --psm 6'
        extracted_text = pytesseract.image_to_string(image, config=custom_config, lang='eng')

        extracted_text = re.sub(r"[^\w\s.%,-/#]", " ", extracted_text)
        extracted_text = re.sub(r'([a-zA-Z])4([a-zA-Z]*)', r'\1e\2', extracted_text)
        lines = extracted_text.splitlines()
        cleaned_lines = []
        for line in lines:
            line = re.sub(r"[^\w\s.%,-/]", "", line)
            line = re.sub(r"\s+", " ", line).strip()

            line = re.sub(r"(\d)\s+([a-zA-Z])", r"\1 \2", line)
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    except Exception as e:
        print(f"Error extracting text with OCR: {e}")
        return None

def process_file(file_path, mode="product"):
    if not os.path.exists(file_path):
        print(f"File {file_path} tidak ditemukan")
        return

    all_rows = []
    full_text = ""

    if file_path.endswith('.pdf'):
        with pdfplumber.open(file_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                try:
                    text = extract_text_with_ocr(file_path, page_number)
                    if text:
                        full_text += text + "\n"
                except Exception as e:
                    print(f"Error reading page {page_number}: {e}")

        rows = full_text.split("\n")
        filename = os.path.basename(file_path)
        for row in rows:
            row = row.strip()
            if not row:
                continue
            parsed = parse_row(row, full_text, filename)
            if parsed:
                all_rows.append(parsed)

    elif file_path.endswith('.webp'):
        text = extract_image_with_ocr(file_path)
        filename = os.path.basename(file_path)
        rows = text.split("\n")
        for row in rows:
            row = row.strip()
            if not row:
                continue
            parsed = parse_row(row, text, filename)
            if parsed:
                all_rows.append(parsed)

    else:
        print(f"File {file_path} tidak didukung")
        return ""

    if all_rows:
        if mode == "blur":
            process_row_blur(all_rows)
        else:
            process_row(all_rows)

        csv_rows = [row[:6] for row in all_rows]
        folder = os.path.dirname(file_path)
        csvname = os.path.splitext(os.path.basename(file_path))[0] + '.csv'
        csv_path = os.path.join(folder, csvname)
        write_csv_with_delimiter(csv_path, csv_rows, ";")
        return csvname
    else:
        print("Tidak ada data yang diekstrak.")
        return ""

def write_csv_with_delimiter(filename, allrows, delimiter):
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        df = pd.DataFrame(columns=["Product Number", "Description", "Quantity", "Unit Price", "Discount", "Line Total"]) 
        df.to_csv(file, index=False, sep=delimiter, header=True)
        writer = csv.writer(file, delimiter=delimiter,)
        writer.writerows(allrows)
        
def process_row(rows):
    session = Session()
    for parsed_row in rows:
        if not parsed_row:
            continue

        try:
            product_number, description, quantity, unit_price, discount, line_total, text, filename  = parsed_row

            product = ProductTable(
                product_number=str(product_number).strip(),
                description=str(description).strip(),
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
                discount=discount,
                text=text,
                filename=filename,
            )
                        
            session.add(product)
            session.commit()
            print(f"Data berhasil disimpan: {product_number}, {description}, {quantity}, {unit_price}, {discount} ,{line_total}")
        except Exception as e:
            session.rollback()
            print(f"Kesalahan pada baris: {parsed_row}. Error: {e}")

def process_row_blur(rows):
    session = Session()
    for parsed_row in rows:
        if not parsed_row:
            continue
        try:
            product_number, description, quantity, unit_price, discount, line_total, text, filename = parsed_row

            product_blur = InvoiceBlur(
                product_number=str(product_number).strip(),
                description=str(description).strip(),
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
                discount=discount,
                text=text,
                filename=filename
            )

            session.add(product_blur)
            session.commit()
            print(f"[BLUR] Data berhasil disimpan ke invoiceblur: {product_number}, {description}, {quantity}, {unit_price}, {discount} ,{line_total}")
        except Exception as e:
            session.rollback()
            print(f"[BLUR] Gagal simpan ke invoiceblur untuk baris: {parsed_row}. Error: {e}")
