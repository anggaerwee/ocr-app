import pdfplumber
import pandas as pd

with pdfplumber.open('sample/nonblurry.pdf') as pdf:
    first_page = pdf.pages[0]

    # Ekstrak tabe/teks dari halaman pertama
    text = first_page.extract_table()

    # Ekstrak table/teks ke DataFrame
    table = pd.DataFrame(text[1:], columns=text[0])

    # Konvers Dataframe ke format yang di inginkan
    # Misal: JSON, CSV, dll
    result = table.to_csv(index=False)

    print(table)    