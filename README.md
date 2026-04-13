# Agent-SDK-PageIndex

## Project Structure
Agent-SDK-PageIndex/
├── main.py                # Core logic of the agent and database
├── ocr_tool.py            # OCR processing loop and Supabase storage management
├── requirements.txt       # Python dependencies
├── prompt.yaml            # Home Along persona & Telegram rules
└── uploaded_docs.json     # Stored the id files from Supabase

## Supabase 
Supabase_Key = Settings -> API -> Legacy anon, servive_role
Supabase_URL = Settings -> DATA API -> API URL

## OCR Tools
- poppley 25.12.0       # Translator
- tesseract.exe         # Reader
- PyPDF2                # Assembler
