from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = "postgresql://postgres:anggarizki@localhost:5432/python"
engine = create_engine(
    DATABASE_URL,
    connect_args={"options": "-c timezone=Asia/Jakarta"}
)
Base = declarative_base()

class ProductTable(Base):
    __tablename__ = 'tb_product'
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_number = Column(String(50))
    description = Column(String(255))
    quantity = Column(Integer)
    unit_price = Column(Float)
    line_total = Column(Float)
    discount = Column(Float)
    text = Column(String(255))
    filename = Column(String(255))
    createddate = Column(DateTime, default=datetime.now) 

    @classmethod
    def get_all(cls):
        return session.query(cls).all()
    @classmethod
    def delete(cls, id):
        product = session.query(cls).get(id)
        if product:
            session.delete(product)
            session.commit()
            return True
        return False

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()