# Agent-SDK-PageIndex

## Project Structure
```
Agent-SDK-PageIndex/
├── main.py                # Core logic of the agent and database
├── ocr_tool.py            # OCR processing loop and Supabase storage management
├── requirements.txt       # Python dependencies
├── prompt.yaml            # Home Along persona & Telegram rules
└── uploaded_docs.json     # Stored the id of files from Supabase for PageIndex
```

## Supabase 
- Supabase_Key = Settings -> API -> Legacy anon, servive_role
- Supabase_URL = Settings -> DATA API -> API URL

## OCR Tools
- poppley 25.12.0       # Translator
- tesseract.exe         # Reader
- PyPDF2                # Assembler

## PROs and CONs of PageIndex

### PROs
- Ang way nya ng pagbabasa ng files or documents ay gumagawa sya ng Hierarchical Tree (Table of Contents -> Chapters -> Sections)
- So hindi sya naliligaw sa paghahanap ng sagot sa tanong ni User
- Less to None and hallucination dahil alam ng AI and structure ng files
- Built in OCR 

### CONs
- Currently PDF palang ang tinatanggap na file
- May mahigpit na page limit and may limit din sa file size
- Ang performance ng OCR ay naka depende sa Tier and hindi sya working sa FREE TIER
- Ang OCR performance ay nakabased pa rin sa subscription
