import pdfplumber
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import re
from pdf2image import convert_from_path
import os
import pandas as pd
import csv
import os

from database.db_config import Session, ProductTable

def parse_row(row_text):
    try:
        row_text = re.sub(r"[“![|~=_—j(]", "", row_text)
        row_text = re.sub(r"\s{2,}", " ", row_text).strip()
        parts = row_text.split()
        if len(parts) < 5:
            return None

        line_total_str = parts[-1]
        possible_discount_str = parts[-2]

        if "%" in possible_discount_str:
            # Format parts 6: dengan diskon
            description_parts = parts[1:-4]
            quantity_str = parts[-4]
            unit_price_str = parts[-3]
            discount_str = possible_discount_str
        else:
            # Format parts 5: tanpa diskon
            description_parts = parts[1:-3]
            quantity_str = parts[-3]
            unit_price_str = parts[-2]
            discount_str = None

        product_number = parts[0]
        description = " ".join(description_parts).strip().lstrip('/')
        product_number = product_number.replace("pl", "p1").replace("ps", "p3").replace("p+", "p4").replace("pd", "p5").replace("pé", "p6")
        # description = description.replace("IGRASS", "GRASS")
        # line_total_str = line_total_str.replace("7250.00", "772.20")
        quantity = int(re.sub(r"[^\d]", "", quantity_str))
        unit_price = float(re.sub(r"[^\d.]", "", unit_price_str))
        line_total = float(re.sub(r"[^\d.]", "", line_total_str))
        discount = float(re.sub(r"[^\d.]", "", discount_str)) if discount_str else None

        return product_number, description, quantity, unit_price,discount, line_total, 

    except Exception as e:
        print(f"Baris gagal di parsing: {e}")
        return None

def extract_text_with_ocr(file_path, page_number):
    try:
        images = convert_from_path(file_path, first_page=page_number, last_page=page_number, dpi=205)
        if not images:
            print(f"Tidak ada halaman yang dapat diproses dari file {file_path}")
            return None
        
        extracted_text = ""
        for image in images:
            custom_config = r'--oem 3 --psm 6'
            page_text = pytesseract.image_to_string(image, config=custom_config)
            extracted_text += page_text + "\n"
        
        return extracted_text.strip()
    except Exception as e:
        print(f"Error extracting text with OCR: {e}")
        return None

def extract_image_with_ocr(image_path): 
    try:
        # Load and preprocess the image
        image = Image.open(image_path)
        image = image.convert("L")  # Convert to grayscale

        # Enhance contrast and resize for better OCR accuracy
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)
        width, height = image.size
        image = image.resize((width * 4, height * 4), Image.Resampling.LANCZOS)

        # Apply filters to improve text recognition
        image = image.filter(ImageFilter.MedianFilter(size=3))
        image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=253, threshold=3))

        # Binarize the image
        threshold = 128
        image = image.point(lambda p: 255 if p > threshold else 0)

        # Extract text using Tesseract OCR
        custom_config = r'--oem 3 --psm 6'
        extracted_text = pytesseract.image_to_string(image, config=custom_config, lang='eng')

        # Apply replacements to fix common OCR errors
        replacements = {
            "pt": "p1",
            "pe": "p4",
            "pr": "p2",
            "ps": "p5",
            "soot.": "4.00%",
            "5.001": "5.00%",
            # "5.": "5.20",
            # "pl": "p1",
            # "pr": "p2",
            # "pe": "p4",
            # "ps": "p6",
            # "5.202": "5.20",
            # "100%.": "1.00%",
            # "200%": "2.00%",
            # "T7220": "772.20",
            # "S11.65": "211.68",
            # # "363.27": "3863.17"
        }
        for wrong, correct in replacements.items():
            extracted_text = extracted_text.replace(wrong, correct)

        # Clean up and normalize the text
        lines = extracted_text.splitlines()
        cleaned_lines = []
        for line in lines:
            # Remove unwanted characters and normalize spacing
            line = re.sub(r"[^\w\s.%,-]", "", line)
            line = re.sub(r"\s+", " ", line).strip()

            # Further refine line format (adjust as needed for specific patterns)
            line = re.sub(r"(\d)\s+([a-zA-Z])", r"\1 \2", line)  # Fix number and letter spacing
            cleaned_lines.append(line)

        # Return cleaned text as joined lines
        return "\n".join(cleaned_lines)

    except Exception as e:
        print(f"Error extracting text with OCR: {e}")
        return None

def process_file(file_path):

    if not os.path.exists(file_path):
        print(f"File {file_path} tidak ditemukan")
        return
    
    all_rows = []

    if file_path.endswith('.pdf'):
        with pdfplumber.open(file_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                
                if page.width and page.height:
                    text = extract_text_with_ocr(file_path, page_number)
                    print(text)
                rows = text.split("\n")
                for row in rows:
                    parsed = parse_row(row)
                    print(parsed)
                    if parsed:
                        all_rows.append(parsed)

    elif file_path.endswith('.webp'):
        text = extract_image_with_ocr(file_path)
        print(text)
        rows = text.split("\n")
        for row in rows:
            row = row.strip()
            if not row:
                continue

            parsed = parse_row(row)
            print(parsed)
            if parsed:
                all_rows.append(parsed)
    
    else:
        print(f"File {file_path} tidak didukung")
        return ""

    if all_rows:
        process_row(all_rows)
        folder = os.path.dirname(file_path)
        csvname = os.path.splitext(os.path.basename(file_path))[0] + '.csv'
        csv_path = os.path.join(folder, csvname)
        write_csv_with_delimiter(csv_path, all_rows, ";")
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

        try:
            product_number, description, quantity, unit_price, discount, line_total,  = parsed_row

            product = ProductTable(
                product_number=str(product_number).strip(),
                description=str(description).strip(),
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
                discount=discount
            )
                        
            session.add(product)
            session.commit()
            print(f"Data berhasil disimpan: {product_number}, {description}, {quantity}, {unit_price}, {line_total}")
        except Exception as e:
            session.rollback()
            print(f"Kesalahan pada baris: {parsed_row}. Error: {e}")

# process_file("sample/blurry_australiantaxinvoicetemplate.webp")