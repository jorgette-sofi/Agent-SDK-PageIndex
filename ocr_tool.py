import os
import pytesseract
from pdf2image import convert_from_path
from PyPDF2 import PdfWriter, PdfReader
import io

pytesseract.pytesseract.tesseract_cmd = r'C:\Users\Jorgette\Sofi-AI\OCR\tesseract.exe'
POPPLER_PATH = r'C:\Users\Jorgette\Downloads\poppler-25.12.0\Library\bin' 

def create_searchable_pdf(input_path, output_path):
    print(f" Converting: {os.path.basename(input_path)}...")
    
    try:
        # 1. Convert PDF pages to images
        pages = convert_from_path(input_path, poppler_path=POPPLER_PATH)
        pdf_writer = PdfWriter()

        for i, page in enumerate(pages):
            # 2. Get searchable PDF data for this specific page
            page_pdf_data = pytesseract.image_to_pdf_or_hocr(page, extension='pdf')
            
            # 3. Read the bytes into a PDF object and add to writer (NO TEMP FILES!)
            page_pdf_reader = PdfReader(io.BytesIO(page_pdf_data))
            pdf_writer.add_page(page_pdf_reader.pages[0])

        # 4. Save the final merged searchable PDF directly to the data folder
        with open(output_path, "wb") as f:
            pdf_writer.write(f)
            
        print(f" Created Searchable PDF: {output_path}")
        return True
        
    except Exception as e:
        print(f" OCR Error: {e}")
        return False
