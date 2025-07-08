from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "postgresql://postgres:achmad1312@localhost:5432/convertdata"
engine = create_engine(
    DATABASE_URL,
    connect_args={"options": "-c timezone=Asia/Jakarta"}
)
Base = declarative_base()

class Msrole(Base):
    __tablename__ = 'msrole'
    groupid = Column(Integer, primary_key=True, autoincrement=True)
    rolenm = Column(String(100))
    createdate = Column(DateTime, default=datetime.now)
    updateddate = Column(DateTime, default=datetime.now)

    users = relationship("Msuser", back_populates="role")

    @classmethod
    def get_all(cls, session):
        return session.query(cls).all()
class Msuser(Base):
    __tablename__ = 'msuser'
    userid = Column(Integer, primary_key=True, autoincrement=True)
    usernm = Column(String(100), unique=True)
    pswd = Column(String(255))
    email = Column(String(100), unique=True)
    createddate = Column(DateTime, default=datetime.now)
    updateddate = Column(DateTime, default=datetime.now)
    groupid = Column(Integer, ForeignKey('msrole.groupid'))
    isactive = Column(Boolean)

    role = relationship("Msrole", back_populates="users")
    access = relationship("Msuseraccess", back_populates="user", uselist=False)

    @classmethod
    def get_all(cls, session):
        return session.query(cls).all()
class Msuseraccess(Base):
    __tablename__ = 'msuseraccess'
    useracid = Column(Integer, primary_key=True, autoincrement=True)
    userid = Column(Integer, ForeignKey('msuser.userid'))
    createddate = Column(DateTime, default=datetime.now)
    updateddate = Column(DateTime, default=datetime.now)

    user = relationship("Msuser", back_populates="access")
    invoices = relationship("ProductTable", back_populates="accessor")
    invoiceblurs = relationship("InvoiceBlur", back_populates="accessor")

    @classmethod
    def get_all(cls, session):
        return session.query(cls).all()
class ProductTable(Base):
    __tablename__ = 'invoice'
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
    useracid = Column(Integer, ForeignKey('msuseraccess.useracid'))

    accessor = relationship("Msuseraccess", back_populates="invoices")
    @classmethod
    def get_all(cls, session):
        return session.query(cls).all()
    @classmethod
    def delete(cls, id):
        product = session.query(cls).get(id)
        if product:
            session.delete(product)
            session.commit()
            return True
        return False

class InvoiceBlur(Base):
    __tablename__ = 'invoiceblur'
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
    useracid = Column(Integer, ForeignKey('msuseraccess.useracid'))

    accessor = relationship("Msuseraccess", back_populates="invoiceblurs")
    @classmethod
    def get_all(cls, session):
        return session.query(cls).all()

    @classmethod
    def delete(cls, id):
        record = session.query(cls).get(id)
        if record:
            session.delete(record)
            session.commit()
            return True
        return False
   
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()