import pdfplumber
import re
from sqlalchemy import create_engine, Column, Integer, Float, String
from sqlalchemy.orm import declarative_base, sessionmaker

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

# Fungsi untuk memisahkan data 
def parse_row(row_text):
    parts = row_text.strip().split()

    # Cek jika baris terlalu pendek
    if len(parts) < 5 or not parts[0].isdigit():
        return None

    try:
        # Ambil line_total dan unit_price dari belakang
        line_total = parts[-1]
        unit_price = parts[-3] + parts[-2]

        # Cari quantity
        try:
            float(parts[-3])  # Jika -3 adalah angka
            quantity = parts[-4]
            desc_end_index = -4
        except ValueError:
            quantity = parts[-3]
            desc_end_index = -3

        product_number = parts[0]
        description = " ".join(parts[1:desc_end_index])

        # Validasi quantity, unit_price, line_total harus angka valid
        if not (quantity.replace('.', '', 1).isdigit() and 
                unit_price.replace('.', '', 1).isdigit() and 
                line_total.replace('.', '', 1).isdigit()):
            return None  # Jika ada yang bukan angka, skip row ini

        return (product_number, description, quantity, unit_price, line_total)

    except Exception as e:
        print(f"Gagal parsing baris: {row_text}. Error: {e}")
        return None



# Fungsi untuk mengekstrak tabel dari PDF
def extract_table_from_pdf(pdf_path):

    if not pdf_path.endswith('.pdf'):
        print(f"File bukan PDF : {pdf_path}")
        return

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            # Ekstrak teks dari halaman
            text = page.extract_text()
            if not text:
                print(f"Tidak ada teks di halaman: {page_number}")
                continue
            
            # Pisahkan baris dalam teks
            rows = text.split("\n")
            for row in rows:
                try:
                    # Parsing baris dengan regex
                    parsed_row = parse_row(row)
                    if not parsed_row:
                        continue

                    # Unpack hasil parsing
                    product_number, description, quantity, unit_price, line_total = parsed_row

                    # Parsing dan simpan ke database
                    product = ProductTable(
                        product_number=parse_value(product_number, str),
                        description=parse_value(description, str),
                        quantity=parse_value(quantity, int),
                        unit_price=parse_value(unit_price, float),
                        line_total=parse_value(line_total, float),
                    )

                    session.add(product)
                    session.commit()
                    print(f"Baris berhasil disimpan: {product_number}, {description}, {quantity}, {unit_price}, {line_total}")
                except Exception as e:
                    print(f"Kesalahan pada baris: {row}. Error: {e}")
    print("Data berhasil ditambahkan ke database.")

# Jalankan fungsi untuk file PDF
extract_table_from_pdf("sample/wholesale-produce-distributor-invoice.pdf")
