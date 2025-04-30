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
    __tablename__ = 'australian_taxi'
    id = Column(Integer, primary_key=True, autoincrement=True)
    taxable = Column(String(50))
    description = Column(String(255))
    quantity = Column(Integer)
    unit_price = Column(Float)
    discount = Column(Float)
    line_total = Column(Float)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# Fungsi untuk membersihkan angka
def clean_number(text):
    return text.replace(' ', '').replace(',', '').replace('%', '').strip()

# Fungsi untuk membersihkan teks hasil OCR
def clean_text(text):
    text = re.sub(r"[|/~]", " ", text)  # Hapus karakter aneh
    text = re.sub(r"\s+", " ", text)  # Ganti spasi berlebih dengan satu spasi
    return text.strip()

# Fungsi untuk mengekstrak teks dari gambar menggunakan OCR
def extract_text_with_ocr(page):
    try:
        page_image = page.to_image()
        pil_page = page_image.original
        config = "--psm 6"
        return pytesseract.image_to_string(pil_page, config=config)
    except Exception as e:
        print(f"Kesalahan OCR: {e}")
        return ""

# Fungsi untuk memeriksa apakah baris adalah data produk
def is_valid_row(parts):
    if len(parts) < 5:
        return False
    if not parts[0].startswith("p"):  # Baris data produk biasanya diawali dengan "p"
        return False
    if not parts[-1].replace('.', '', 1).isdigit():  # Line total harus berupa angka
        return False
    return True

# Fungsi untuk parsing baris data
def parse_row(row_text):
    try:
        row_text = clean_text(row_text)
        parts = row_text.split()

        # Validasi apakah baris adalah data produk
        if not is_valid_row(parts):
            return None

        taxable = parts[0]

        # Gabungkan bagian terakhir jika diperlukan untuk menghasilkan `line_total`
        if len(parts) >= 6 and parts[-2].replace('.', '').isdigit() and parts[-1].replace('.', '').isdigit():
            parts[-2:] = ["".join(parts[-2:])]

        line_total = clean_number(parts[-1])
        discount = clean_number(parts[-2])
        unit_price = clean_number(parts[-3])
        quantity = clean_number(parts[-4])
        description = " ".join(parts[1:-4])

        return (taxable, description, quantity, unit_price, discount, line_total)
    except Exception as e:
        print(f"Kesalahan parsing baris: {row_text}. Error: {e}")
        return None

# Fungsi untuk mengekstrak tabel dari PDF
def extract_table_from_pdf(pdf_path):
    if not pdf_path.endswith('.pdf'):
        print(f"File bukan PDF : {pdf_path}")
        return

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()

            if not text:
                print(f"Halaman {page.page_number} menggunakan OCR karena tidak ada teks.")
                text = extract_text_with_ocr(page)
            if not text:
                print(f"Tidak ada teks di halaman {page.page_number}.")
                continue

            rows = text.split("\n")
            for row in rows:
                parsed_row = parse_row(row)

                if not parsed_row:
                    print(f"Baris tidak valid: {row}")
                    continue
                print(parsed_row)

                try:
                    taxable, description, quantity, unit_price, discount, line_total = parsed_row

                    # Validasi sebelum menambah ke database
                    if quantity is None or unit_price is None or line_total is None:
                        print(f"Data tidak lengkap: {row}")
                        continue

                    product = ProductTable(
                        taxable=taxable,
                        description=description,
                        quantity=quantity,
                        unit_price=unit_price,
                        discount=discount,
                        line_total=line_total,
                    )
                    session.add(product)
                    session.commit()
                except Exception as e:
                    print(f"Kesalahan saat menyimpan ke database: {e}")
                    session.rollback()
                    continue

# Jalankan fungsi
extract_table_from_pdf("sample/nonblurry_australiantaxinvoicetemplate.pdf")
extract_table_from_pdf("sample/australian_scan.pdf")