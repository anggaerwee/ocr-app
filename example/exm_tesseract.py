from PIL import Image
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

    # Open the image using PIL
image = Image.open('data/wholesale-produce.webp')

    # Use pytesseract to extract text from the image
extracted_text = pytesseract.image_to_string(image)

print(extracted_text)
