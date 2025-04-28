from pdf2image import convert_from_path, convert_from_bytes
from pdf2image.exceptions import (
    PDFInfoNotInstalledError,
    PDFPageCountError,
    PDFSyntaxError
)

import tempfile

try:
    # Menggunakan direktori sementara untuk menyimpan gambar yang dihasilkan
    with tempfile.TemporaryDirectory() as path:
        images_from_path = convert_from_path('data/nonblurry.pdf', output_folder=path)
        
        # Menyimpan setiap halaman sebagai file gambar
        for i, image in enumerate(images_from_path):
            output_file = f"output/page_{i + 1}.jpg"
            image.save(output_file, 'JPEG')
            print(f"Saved: {output_file}")

except PDFInfoNotInstalledError:
    print("PDFInfo is not installed. Please ensure that Poppler is installed and added to your PATH.")
except PDFPageCountError:
    print("Unable to get page count. The PDF file might be corrupted.")
except PDFSyntaxError:
    print("Syntax error in the PDF file.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")