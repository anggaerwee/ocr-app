import pdfplumber
import pytesseract
from PIL import Image
import re
import io
from sqlalchemy import create_engine, Column, Integer, Float, String
from sqlalchemy.orm import declarative_base, sessionmaker

# Konfigurasi database
DATABASE_URL = "mysql+pymysql://root:@localhost/python"
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

# Fungsi untuk parsing tabel secara fleksibel
def parse_table(rows):
    parsed_data = []
    product_row_pattern = re.compile(r'^(\d+)\s+(.+?)\s+(\d+)\s+([\d\.]+)\s+([\d.]+)$')

    for row in rows:
        match = product_row_pattern.match(row)
        if match:
            product_number = match.group(1)
            description = match.group(2)
            quantity = match.group(3)
            unit_price = match.group(4)
            line_total = match.group(5)

            parsed_data.append([
                product_number,
                description,
                quantity,
                unit_price,
                line_total
            ])
    
    return parsed_data

# Fungsi untuk mengekstrak teks dari gambar menggunakan OCR
def extract_text_with_ocr(image):
    return pytesseract.image_to_string(image, lang='eng')

# Fungsi utama untuk ekstraksi tabel dari PDF
def extract_table_from_pdf(pdf_path):
    if not pdf_path.endswith('.pdf'):
        print(f"File bukan PDF: {pdf_path}")
        return

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            if page.width and page.height:
                # Ekstraksi teks langsung
                text = page.extract_text()
                if not text:
                    print(f"Tidak ada teks, menggunakan OCR untuk halaman: {page_number}")
                    with io.BytesIO(page.to_image(resolution=300).original_image) as image_bytes:
                        image = Image.open(image_bytes)
                        text = extract_text_with_ocr(image)

                rows = text.split("\n")
                parsed_rows = parse_table(rows)
                for parsed_row in parsed_rows:
                    try:
                        product_number = parse_value(parsed_row[0], str)
                        description = parse_value(" ".join(parsed_row[1:-3]), str)
                        quantity = parse_value(parsed_row[-3], int)
                        unit_price = parse_value(parsed_row[-2], float)
                        line_total = parse_value(parsed_row[-1], float)

                        # Parsing dan simpan ke database
                        product = ProductTable(
                            product_number=product_number,
                            description=description,
                            quantity=quantity,
                            unit_price=unit_price,
                            line_total=line_total,
                        )

                        session.add(product)
                        session.commit()
                        # print(f"Data berhasil disimpan: {product_number}, {description}, {quantity}, {unit_price}, {line_total}")
                    except Exception as e:
                        print(f"Kesalahan pada baris: {parsed_row}. Error: {e}")

# Jalankan fungsi untuk file PDF
extract_table_from_pdf("sample/wholesale-produce-distributor-invoice.pdf")
