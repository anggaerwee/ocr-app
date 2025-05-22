import pdfplumber
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import re
from pdf2image import convert_from_path
import os
from sqlalchemy import create_engine, Column, Integer, Float, String
from sqlalchemy.orm import declarative_base, sessionmaker
import pandas as pd

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

    @classmethod
    def get_all(cls):
        return session.query(cls).all()

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# Fungsi untuk parsing tabel secara fleksibel (hilangkan kolom diskon jika ada)
def parse_row(row_text):
    try:
        # Pembersihan teks
        row_text = re.sub(r"[“![|/~=_—]", " ", row_text) #Menghilangkan karakter aneh
        row_text = re.sub(r"\s{2,}", " ", row_text).strip()  # Menghilangkan spasi berlebih
        row_text = re.sub(r"\d+\.\d+%\s*", "", row_text)  # MEnghilangkan persen jika ada
        
        # Pisahkan teks berdasarkan spasi
        parts = row_text.split()
        if len(parts) < 5:
            return None  # Baris tidak valid jika elemen terlalu sedikit
        
        # Parsing elemen utama
        product_number = parts[0]
        description = " ".join(parts[1:-3]).strip()
        quantity = parts[-3]
        unit_price = parts[-2]
        line_total = parts[-1]
        
        # Konversi ke tipe data yang sesuai
        quantity = int(re.sub(r"[^\d]", "", quantity))  # Menghilangkan karakter non-digit
        unit_price = float(re.sub(r"[^\d.]", "", unit_price))  # Menghilangkan non-digit kecuali titik
        line_total = float(re.sub(r"[^\d.]", "", line_total))  # Menghilangkan non-digit kecuali titik
        
        return product_number, description, quantity, unit_price, line_total
    except Exception as e:
        # print(f"Error parsing row: {e}")
        return None

# Fungsi untuk OCR jika teks tidak terdeteksi
def extract_text_with_ocr(file_path, page_number):
    try:
        images = convert_from_path(file_path, first_page=page_number, last_page=page_number, dpi=200)
        if not images:
            print(f"Tidak ada halaman yang dapat diproses dari file {file_path}")
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

def extract_image_with_ocr(image_path): 
    try:
        # Open image
        image = Image.open(image_path)

        # Convert to grayscale to improve contrast
        image = image.convert("L")

        # Enhance contrast moderately
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)  # Adjusted from 4.0 to 2.0

        # Resize image to improve OCR quality
        width, height = image.size
        image = image.resize((width * 4, height * 4), Image.Resampling.LANCZOS)

        # Apply median filter to reduce noise
        image = image.filter(ImageFilter.MedianFilter(size=3))

        # Apply sharpening filter to enhance edges
        image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=250, threshold=3))

        # Binarize image (convert to pure black and white)
        threshold = 128
        image = image.point(lambda p: 255 if p > threshold else 0)

        replacements = {
            'soot.': '4.00%',  # Fix p4 percentage
        }


        # Use OCR with custom config
        custom_config = r'--oem 3 --psm 6'
        extracted_text = pytesseract.image_to_string(image, config=custom_config)

        for wrong, correct in replacements.items():
            extracted_text = extracted_text.replace(wrong, correct)
        extracted_text = re.sub(r"[^\w\s.%,-]", " ", extracted_text)
        extracted_text = re.sub(r"\s{3,}", " ", extracted_text).strip()

        return extracted_text
    except Exception as e:
        print(f"Error extracting text with OCR: {e}")
        return None

# Fungsi utama untuk ekstraksi tabel dari PDF
def process_file(file_path):

    # Validasi jika file tidak ditemukan 
    if not os.path.exists(file_path):
        print(f"File {file_path} tidak ditemukan")
        return
    
    # Simpan nilai dalam array
    all_rows = []

    # Jika file berformat PDF 
    if file_path.endswith('.pdf'):
        with pdfplumber.open(file_path) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                
                if page.width and page.height:
                    text = extract_text_with_ocr(file_path, page_number)
                    # print(text)

                rows = text.split("\n")
                for row in rows:
                    parsed = parse_row(row)
                    # print(parsed)
                    if parsed:
                        all_rows.append(parsed)

    # Jika file berformat webp   
    elif file_path.endswith('.webp'):
        text = extract_image_with_ocr(file_path)
        # print(text)
        rows = text.split("\n")
        for row in rows:
            row = row.strip()
            if not row:
                continue

            parsed = parse_row(row)
            # print(parsed)
            if parsed:
                all_rows.append(parsed)
    
    # Jika format file tidak di dukung
    else:
        print(f"File {file_path} tidak didukung")
        return ""

    if all_rows:
        process_row(all_rows)
        df = pd.DataFrame(all_rows, columns=["product_number", "description", "quantity", "unit_price", "line_total"])
        csv_filename = os.path.splitext(os.path.basename(file_path))[0] + '.csv'
        csv_path = os.path.join(os.path.dirname(file_path), csv_filename)
        df.to_csv(csv_path, index=False) 
        return csv_filename 
    else:
        print("Tidak ada data yang diekstrak.")
        return ""

def process_row(rows):
    for parsed_row in rows:
        if not parsed_row or len(parsed_row) != 5:
            continue

        try:
            product_number, description, quantity, unit_price, line_total = parsed_row

            product = ProductTable(
                product_number=str(product_number).strip(),
                description=str(description).strip(),
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total
            )
                        
            session.add(product)
            session.commit()
            print(parsed_row)
            print(f"Data berhasil disimpan: {product_number}, {description}, {quantity}, {unit_price}, {line_total}")
        except Exception as e:
            session.rollback()
            print(f"Kesalahan pada baris: {parsed_row}. Error: {e}")
