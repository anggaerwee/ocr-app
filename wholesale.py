import pdfplumber
import pytesseract
from sqlalchemy import create_engine, Column, Integer, Float, String
from sqlalchemy.orm import declarative_base, sessionmaker
import re

# Konfigurasi database
DATABASE_URL = "mysql+pymysql://root:@localhost/python"
engine = create_engine(DATABASE_URL)
Base = declarative_base()

# Model database
class ProductTable(Base):
    __tablename__ = 'wholesale_produce'
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_number = Column(String(50))
    description = Column(String(255))
    quantity = Column(Integer)
    unit_price = Column(Float)
    line_total = Column(Float)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# Fungsi parsing nilai dengan validasi
def parse_value(value, value_type, default=None):
    try:
        if value is None or value.strip() == "":
            return default
        if value_type == int:
            return int(value.replace(",", "").strip())
        elif value_type == float:
            return float(value.replace(",", "").strip())
        elif value_type == str:
            return value.strip()
    except (ValueError, AttributeError):
        return default

# Fungsi untuk parsing baris data
def parse_row(row_text):
    try:
        # Bersihkan karakter aneh
        row_text = re.sub(r"[|/~]", " ", row_text)
        parts = row_text.split()
        
        # Validasi minimal elemen dalam baris
        if len(parts) < 5 or not parts[0]:
            return None

        product_number = parts[0]
        line_total = parts[-1]

        # Coba mengidentifikasi quantity dan unit price
        try:
            # Asumsikan line_total selalu berada di posisi terakhir
            # dan quantity adalah angka mendekati akhir baris
            quantity = int(parts[-4])
            unit_price = float(parts[-3] + parts[-2])
            description = " ".join(parts[1:-4])
        except ValueError:
            # Penanganan jika quantity/unit_price tidak sesuai
            # Misal terjadi penggabungan dengan description
            quantity = int(parts[-3])
            unit_price = float(parts[-2])
            description = " ".join(parts[1:-3])

        return (product_number, description, str(quantity), str(unit_price), line_total)
    except Exception as e:
        print(f"Kesalahan parsing baris: {row_text}. Error: {e}")
        return None

# Fungsi OCR
def extract_text_with_ocr(page):
    try:
        page_image = page.to_image()
        pil_image = page_image.original
        config = "--psm 6"  # Mode untuk tabel sederhana
        return pytesseract.image_to_string(pil_image, config=config)
    except Exception as e:
        print(f"Kesalahan OCR: {e}")
        return ""

# Fungsi untuk ekstrak tabel
def extract_table_from_pdf(pdf_path):
    if not pdf_path.endswith('.pdf'):
        print(f"File bukan PDF: {pdf_path}")
        return
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                print(f"Halaman {page_number} menggunakan OCR karena tidak ada teks.")
                text = extract_text_with_ocr(page)
            if not text:
                print(f"Tidak ada teks di halaman {page_number}.")
                continue

            rows = text.split("\n")
            for row in rows:
                parsed_row = parse_row(row)

                if not parsed_row:
                    print(f"Baris tidak valid: {row}")
                    continue
                print(parsed_row)
                    
                try:
                    product_number, description, quantity, unit_price, line_total = parsed_row
                    
                    # Validasi sebelum menambah ke database
                    if quantity is None or unit_price is None or line_total is None:
                        print(f"Data tidak lengkap: {row}")
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
                except Exception as e:
                    print(f"Kesalahan saat menyimpan ke database: {e}")
                    session.rollback()
                    continue

# Jalankan fungsi untuk file PDF
extract_table_from_pdf("sample/wholesale_scan.pdf")
extract_table_from_pdf("sample/wholesale-produce-distributor-invoice.pdf")
