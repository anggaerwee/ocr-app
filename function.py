import pdfplumber
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import re
from pdf2image import convert_from_path
import os
from sqlalchemy import create_engine, Column, Integer, Float, String
from sqlalchemy.orm import declarative_base, sessionmaker
import pandas as pd
import csv

DATABASE_URL = "postgresql://postgres:achmad1312@localhost:5432/convertdata"
engine = create_engine(DATABASE_URL)
Base = declarative_base()

class ProductTable(Base):
    __tablename__ = 'invoice'
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

def parse_row(row_text):
    try:
        row_text = re.sub(r"[“![|/~=_—]", " ", row_text)
        row_text = re.sub(r"\s{2,}", " ", row_text).strip()
        row_text = re.sub(r"\d+\.\d+%\s*", "", row_text)
        
        parts = row_text.split()
        if len(parts) < 5:
            return None
        
        product_number = parts[0]
        description = " ".join(parts[1:-3]).strip()
        quantity = parts[-3]
        unit_price = parts[-2]
        line_total = parts[-1]
       
        quantity = int(re.sub(r"[^\d]", "", quantity))
        unit_price = float(re.sub(r"[^\d.]", "", unit_price))
        line_total = float(re.sub(r"[^\d.]", "", line_total))
        
        return product_number, description, quantity, unit_price, line_total
    except Exception as e:
       
        return None

def extract_text_with_ocr(file_path, page_number):
    try:
        images = convert_from_path(file_path, first_page=page_number, last_page=page_number, dpi=200)
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
        image = Image.open(image_path)

        image = image.convert("L")

        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)

        width, height = image.size
        image = image.resize((width * 4, height * 4), Image.Resampling.LANCZOS)

        image = image.filter(ImageFilter.MedianFilter(size=3))

        image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=250, threshold=3))

        threshold = 128
        image = image.point(lambda p: 255 if p > threshold else 0)

        replacements = {
            'soot.': '4.00%',
        }


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

                rows = text.split("\n")
                for row in rows:
                    parsed = parse_row(row)
                    if parsed:
                        all_rows.append(parsed)

    elif file_path.endswith('.webp'):
        text = extract_image_with_ocr(file_path)
        rows = text.split("\n")
        for row in rows:
            row = row.strip()
            if not row:
                continue

            parsed = parse_row(row)
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
        df = pd.DataFrame(columns=["Product Number", "Description", "Quantity", "Unit Price", "Line Total"])
        df.to_csv(file, index=False, sep=delimiter, header=True)
        writer = csv.writer(file, delimiter=delimiter)
        writer.writerows(allrows)  
        
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
        except Exception as e:
            session.rollback()
            print(f"Kesalahan pada baris: {parsed_row}. Error: {e}")