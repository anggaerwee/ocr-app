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

# Fungsi untuk mengekstrak tabel dari PDF
def extract_table_from_pdf(pdf_path):

    if not pdf_path.endswith('.pdf'):
        print(f"File bukan PDF : {pdf_path} ")
        return

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if table:

                for row in table[1:]:  # Skip header row
                    # Periksa apakah semua kolom dalam baris tidak kosong
                    
                    if all(row): # memastikan semua kolom memiliki nilai
                        product = ProductTable(
                        taxable=row[0],
                        description=row[1],
                        quantity=row[2],
                        unit_price=row[3],
                        discount=row[4],
                        line_total=row[5],
                        )
                        session.add(product)
                        session.commit()
    print("Data berhasil ditambahkan ke database.")

# Jalankan fungsi
extract_table_from_pdf("sample/nonblurry_australiantaxinvoicetemplate.pdf")
