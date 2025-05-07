import pdfplumber
import pytesseract
from PIL import Image
import re
from pdf2image import convert_from_path
import os
from sqlalchemy import create_engine, Column, Integer, Float, String
from sqlalchemy.orm import declarative_base, sessionmaker

# Konfigurasi database
DATABASE_URL = "postgresql://postgres:anggarizki@localhost:5432/python"
engine = create_engine(DATABASE_URL)
Base = declarative_base()

# Model database
class ProductTable(Base):
    __tablename__ = 'tb_product'
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_number = Column(String(50))
    description = Column(String(255))
    quantity = Column(Integer)
    unit_price = Column(Float)
    line_total = Column(Float)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# Fungsi untuk parsing nilai dengan validasi
def parse_value(value, value_type, default=None):
    try:
        if value is None or value == "":
            return default
        if value_type == int:
            return int(value.replace(",", "").strip())
        elif value_type == float:
            return float(value.replace(",", "").strip())
        elif value_type == str:
            return value.strip()
    except (ValueError, AttributeError):
        return default

# Fungsi untuk parsing tabel secara fleksibel (hilangkan kolom diskon jika ada)
def parse_row(row_text):
    try: 
        row_text = re.sub(r"[|/~]", " ", row_text)
        row_text = re.sub(r"\d+\.\d+%\s*", "", row_text)
        parts = row_text.split()

        if len(parts) < 5 or not parts[0].isalnum():
            return None
        
        product_number = parts[0]
        line_total = parts[-1]

        try:
            quantity = int(parts[-4])
            unit_price = float(parts[-3] + parts[-2])
            description = " ".join(parts[1:-4])
        except ValueError:
            quantity = int(parts[-3])
            unit_price = float(parts[-2])
            description = " ".join(parts[1:-3])

        return (product_number, description, str(quantity), str(unit_price), line_total)
    except Exception as e:
        print(f"Error parsing row: {e}")
        return None

# Fungsi untuk OCR jika teks tidak terdeteksi
def extract_text_with_ocr(pdf_path, page_number):
    try:
        images = convert_from_path(pdf_path, first_page=page_number, last_page=page_number, dpi=300)
        if not images:
            print(f"Tidak ada halaman yang dapat diproses dari file {pdf_path}")
            return None
        
        extracted_text = ""
        for image in images:
            # Konfigurasi OCR untuk hasil yang lebih baik
            custom_config = r'--oem 3 --psm 6'
            page_text = pytesseract.image_to_string(image, config=custom_config)
            extracted_text += page_text + "\n"
        
        return extracted_text.strip()
    except Exception as e:
        print(f"Error extracting text with OCR: {e}")
        return None

def extract_image_with_ocr(pdf_path):
    try:
        # Buka PDF dan ekstrak halaman pertama
        image = Image.open(pdf_path)
        extracted_text = pytesseract.image_to_string(image)
        return extracted_text
    except Exception as e:
        print(f"Error extracting text with OCR: {e}")
        return None

# Fungsi utama untuk ekstraksi tabel dari PDF
def extract_table_from_pdf(pdf_path):

    # Validasi jika file tidak ditemukan 
    if not os.path.exists(pdf_path):
        print(f"File {pdf_path} tidak ditemukan")
        return

    # Jika file berformat PDF 
    if pdf_path.endswith('.pdf'):
        with pdfplumber.open(pdf_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                if page.width and page.height:
                    text = page.extract_text()
                
                if not text:
                    print(f"Tidak ada teks, menggunakan OCR untuk halaman: {page_number}")
                    text = extract_text_with_ocr(pdf_path, page_number)

                rows = text.split("\n")
                process_row(rows)

    # Jika file berformat webp   
    elif pdf_path.endswith('.webp'):
        text = extract_image_with_ocr(pdf_path)
        rows = text.split("\n")
        process_row(rows)

    # Jika format file tidak di dukung
    else:
        print(f"File {pdf_path} tidak didukung")

def process_row(rows):
    for row in rows:
        parsed_row = parse_row(row)

        try:
            product_number, description, quantity, unit_price, line_total = parsed_row

            if len(product_number) <= 1:
                print(f"Product number: {product_number} harus lebih dari 1 karakter")
                continue

            product = ProductTable(
                product_number=parse_value(product_number, str),
                description=parse_value(description, str),
                quantity=parse_value(quantity, int),
                unit_price=parse_value(unit_price, float),
                line_total=parse_value(line_total, float),
            )
                        
            session.add(product)
            session.commit()
            print(f"Data berhasil disimpan: {product_number}, {description}, {quantity}, {unit_price}, {line_total}")
        except Exception as e:
            session.rollback()
            print(f"Kesalahan pada baris: {parsed_row}. Error: {e}")


# Jalankan fungsi untuk file PDF
extract_table_from_pdf("sample/australian_scan.pdf")
