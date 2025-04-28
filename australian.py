import pdfplumber
from sqlalchemy import create_engine, Column, Integer, Float, String
from sqlalchemy.orm import declarative_base, sessionmaker

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

# Fungsi untuk mengekstrak tabel dari PDF
def extract_table_from_pdf(pdf_path):
    if not pdf_path.endswith('.pdf'):
        print(f"File bukan PDF : {pdf_path}")
        return

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                for row in table[1:]:  # Skip header
                    if all(row):
                        try:
                            quantity = int(clean_number(row[2]))
                            unit_price = float(clean_number(row[3]))
                            discount = float(clean_number(row[4]))
                            line_total = float(clean_number(row[5]))

                            product = ProductTable(
                                taxable=row[0],
                                description=row[1],
                                quantity=quantity,
                                unit_price=unit_price,
                                discount=discount,   
                                line_total=line_total  
                            )
                            session.add(product)
                            session.commit()

                        except Exception as e:
                            print(f"Error processing row {row}: {e}")

    print("Data berhasil ditambahkan ke database.")

# Jalankan fungsi
extract_table_from_pdf("sample/nonblurry_australiantaxinvoicetemplate.pdf")
