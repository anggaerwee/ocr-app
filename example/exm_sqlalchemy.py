from sqlalchemy import create_engine
from sqlalchemy.sql import text
from sqlalchemy.orm import Session
from sqlalchemy import MetaData
metadata_obj = MetaData()
engine = create_engine("mysql+pymysql://root:@localhost/python", echo=True)

# Pastikan Anda menggunakan format URL koneksi yang benar   
# stmt = text("SELECT * FROM tb_produk WHERE price > :price ORDER BY name")
# edit = text("UPDATE tb_produk SET price = :price WHERE id = :id")
# with Session(engine) as session:
#     result = session.execute(edit, [{"price" : 40000, "id" : 3}])
#     session.commit()

    # ! Insert Data
    # conn.execute(text("CREATE TABLE IF NOT EXISTS tb_produk (id int, name varchar(255), price int)"))
    # conn.execute(
    #     text("INSERT INTO tb_produk (id, name, price) VALUES (:id, :name, :price)"),
    #     [{"id": 7, "name": 'Earphone', "price": 5000}, {"id": 8, "name": 'Charger HP', "price": 23000}]
    # )

    # ! Mengambil Baris
#     result = conn.execute(text("select * from tb_produk"))
# for row in result:
#     id = row["id"]
#     name = row["name"] 
#     price = row["price"]
#     print(f"id: {id} nama: {name} price: {price}")

    # ! MEngambil baris dari parameter
    # result = conn.execute(text("SELECT * FROM tb_produk WHERE price < :price"), {"price" : 5000 })
    # for row in result:
    #     print(f"name: {row.name} price: {row.price}")

    # ! Seperti hapus data yang mengambil parameter yaitu id
    # result = conn.execute(text("DELETE FROM tb_produk WHERE id = :id"), {"id" : 8})
    # print(result.rowcount)

    # ? Mengimplementasikan Meta Data Basis Data
    # from sqlalchemy import Table, Column, Integer, String
# user_table = Table(
#     "user_account",
#     metadata_obj,
#     Column("id", Integer, primary_key=True),
#     Column("name", String(30), nullable=False),
#     Column("fullname", String(30), nullable=False),
# )
# metadata_obj.create_all(engine)
