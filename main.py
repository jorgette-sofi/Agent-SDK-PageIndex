import os
import re
import time
import json
import telebot
from dotenv import load_dotenv
from pageindex import PageIndexClient
from openai import OpenAI
from ocr_tool import create_searchable_pdf
from supabase import create_client, Client

load_dotenv()

# 1. SETUP CLIENTS

PAGEINDEX_API_KEY = os.environ.get("PAGEINDEX_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not all([PAGEINDEX_API_KEY, OPENAI_API_KEY, TELEGRAM_BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY]):
    print("\n[!] CRITICAL ERROR: Missing API Keys in .env!")
    exit()

try:
    pi_client = PageIndexClient(api_key=PAGEINDEX_API_KEY)
    llm_client = OpenAI(api_key=OPENAI_API_KEY)
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

    print("Successfully connected to Supabase!")
except Exception as e:
    print(f"[!] Error connecting to clients: {e}")
    exit()

# 2. INGESTION (OCR -> PAGEINDEX -> TREE BUILDING)

print("Initializing Ingestion Engine...")
BUCKET_NAME = "homalong-files" 
CACHE_FILE = "uploaded_docs.json"
TEMP_DIR = "temp_downloads/"

if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

uploaded_cache = {}
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        uploaded_cache = json.load(f)

# CLEANUP
print("Syncing local memory with Supabase processed folder...")
try:
    processed_items = supabase.storage.from_(BUCKET_NAME).list('processed')
    processed_files_in_supabase = [item['name'] for item in processed_items]
except Exception as e:
    print(f"[!] Cleanup Error: Could not list processed folder: {e}")
    processed_files_in_supabase = []

files_to_remove = []
for cached_file, doc_id in uploaded_cache.items():
    if cached_file.startswith("OCR_"):
        check_name = cached_file
    else:
        check_name = f"OCR_{cached_file}"

    if check_name not in processed_files_in_supabase:
        print(f" Detected deleted file in Supabase: {cached_file}. Cleaning up...")
        try:
            pi_client.delete_document(doc_id)
            print(f"  Removed {cached_file} from PageIndex.")
        except Exception as e:
            print(f"  [!] Failed to delete {cached_file} from PageIndex (might already be gone): {e}")
        files_to_remove.append(cached_file)
#-------------------------------------------------------

doc_ids = list(uploaded_cache.values())
new_uploads = False

print("Scanning Supabase 'uploads' folder for new raw PDFs...")
try:
    supabase_items = supabase.storage.from_(BUCKET_NAME).list('uploads')
    supabase_files = [item['name'] for item in supabase_items if item['name'].lower().endswith('.pdf')]
except Exception as e:
    print(f"\n[!] Failed to read from Supabase uploads folder: {e}")
    supabase_files = []

raw_files = supabase_files

if not raw_files:
    print(f"\n[!] No new raw PDF files in Supabase uploads folder.")

for file_name in raw_files:
    if file_name in uploaded_cache:
        print(f" Using cached ID for '{file_name}'")
        continue
    
    raw_supabase_path = f"uploads/{file_name}"
    ocr_file_name = f"OCR_{file_name}"
    ocr_supabase_path = f"processed/{ocr_file_name}"
    
    raw_temp_path = os.path.join(TEMP_DIR, file_name)
    ocr_temp_path = os.path.join(TEMP_DIR, ocr_file_name)

    try:
        print(f"\nDownloading raw file: {file_name}")
        with open(raw_temp_path, 'wb') as f:
            res = supabase.storage.from_(BUCKET_NAME).download(raw_supabase_path)
            f.write(res)
        
        print(f" Running OCR Tool on {file_name}...")
        success = create_searchable_pdf(raw_temp_path, ocr_temp_path)

        if success:
            print(f" Uploading processed {ocr_file_name} to 'processed/' folder...")
            with open(ocr_temp_path, 'rb') as f:
                supabase.storage.from_(BUCKET_NAME).upload(ocr_supabase_path, f)
            
            print(f" Uploading {ocr_file_name} to PageIndex...")
            upload_response = pi_client.submit_document(file_path=ocr_temp_path)
            doc_id = upload_response.get("doc_id")
            
            if doc_id:
                doc_ids.append(doc_id)
                uploaded_cache[file_name] = doc_id 
                new_uploads = True
                print(f" Success! Document ID: {doc_id}")
                
                # Cleanup Supabase: Delete raw file from uploads/
                supabase.storage.from_(BUCKET_NAME).remove([raw_supabase_path])
                print(f" Deleted raw file from Supabase uploads folder.")
            else:
                print(f" Failed to get ID from PageIndex for {file_name}")
        else:
            print(f" OCR failed for {file_name}. Skipping...")
            
        if os.path.exists(raw_temp_path):
            os.remove(raw_temp_path)
        if os.path.exists(ocr_temp_path):
            os.remove(ocr_temp_path)
            
    except Exception as e:
        print(f" Error processing {file_name}: {e}")

if new_uploads:
    with open(CACHE_FILE, "w") as f:
        json.dump(uploaded_cache, f, indent=4)
    print("\nLocal cache updated.")

print(f"\nBuilding trees for {len(doc_ids)} documents...")
for doc_id in doc_ids:
    while not pi_client.is_retrieval_ready(doc_id):
        time.sleep(5)
        print(f" PageIndex is thinking for ID {doc_id}...")

print("\nAll trees are ready! Moving to Telegram Bot logic.\n")

# 3. TOOLS & HELPERS

def search_module(query: str) -> str:
    print(f"\n[System: Bypassing slow search, fetching raw data for {len(doc_ids)} PDFs...]")
    all_contexts = []
    id_to_filename = {v: k for k, v in uploaded_cache.items()}
    
    for doc_id in doc_ids:
        try:
            tree_data = pi_client.get_tree(doc_id) 
            context = str(tree_data)
            
            if context and len(context) > 20:
                raw_file_name = id_to_filename.get(doc_id, "Unknown Document")
                clean_name = raw_file_name.replace(".pdf", "").replace("OCR_", "")
                doc_link = f"https://dash.pageindex.ai/documents?id={doc_id}"
                
                all_contexts.append(f"--- SOURCE: {clean_name} | URL: {doc_link} ---\n{context[:15000]}")
                print(f" Successfully grabbed text for {raw_file_name}")
                
        except Exception as e:
            print(f" [!] Error fetching doc {doc_id}: {e}")
            
    if not all_contexts:
        return "No relevant context found in any of the documents."
        
    print(" Done fetching! Handing data to OpenAI...")
    return "\n\n".join(all_contexts)

tools_menu = [{
    "type": "function",
    "function": {
        "name": "search_module",
        "description": "Searches all uploaded HomeAlong files for specific inquiries, discounts, or summaries.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "The specific question or search term."}},
            "required": ["query"]
        }
    }
}]

def read_text_file(filename, default_text="You are a helpful AI."):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as file:
            return file.read().strip()
    return default_text

system_prompt = read_text_file("system_prompt.txt", default_text="You are a helpful AI assistant.")
user_memories = {}

# 4. TELEGRAM BOT HANDLERS

def clean_markdown(text):
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    return text

@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda msg: msg.text.strip().lower() in ['hi', 'hello'])
def send_welcome(message):
    chat_id = message.chat.id
    user_memories[chat_id] = [{"role": "system", "content": system_prompt}]
    welcome_msg = (
        "Hello! I'm your Home Along assistant. I can help you with verifying documents, "
        "checking product prices, and providing details about installment requirements. "
        "What do you need assistance with today?"
    )
    bot.send_message(chat_id, welcome_msg)

@bot.message_handler(commands=['help'])
def send_help(message):
    chat_id = message.chat.id
    try:
        with open("helpPrompt.txt", "r", encoding="utf-8") as file:
            helpGuide = file.read()
        bot.send_message(chat_id, helpGuide, parse_mode='HTML')
    except Exception:
        bot.send_message(chat_id, "To view help, use the command: /help", parse_mode='HTML')

@bot.message_handler(func=lambda msg: msg.text.strip().lower() in ['#clear', '/clear'])
def clear_history(message):
    chat_id = message.chat.id
    user_memories[chat_id] = [{"role": "system", "content": system_prompt}]
    bot.send_message(chat_id, "<i>Chat history cleared.</i>", parse_mode='HTML')

# 5. THE MAIN AI CHAT LOGIC

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    user_input = message.text

    if chat_id not in user_memories:
        user_memories[chat_id] = [{"role": "system", "content": system_prompt}]

    user_memories[chat_id].append({"role": "user", "content": user_input})
    bot.send_chat_action(chat_id, 'typing')
    print(f"[Telegram] Message from {chat_id}: {user_input}")

    try:
        response = llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=user_memories[chat_id],
            tools=tools_menu,
            tool_choice="auto",
            temperature=0
        )
        
        response_message = response.choices[0].message
        
        if response_message.tool_calls:
            user_memories[chat_id].append(response_message)
            
            for tool_call in response_message.tool_calls:
                function_args = json.loads(tool_call.function.arguments)
                tool_result = search_module(query=function_args.get("query"))
                
                user_memories[chat_id].append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": tool_result
                })
            
            bot.send_chat_action(chat_id, 'typing')
            
            second_response = llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=user_memories[chat_id],
                temperature=0
            )
            
            raw_reply = second_response.choices[0].message.content
            final_reply = clean_markdown(raw_reply)
            
            user_memories[chat_id].append({"role": "assistant", "content": final_reply})
            bot.send_message(chat_id, final_reply, parse_mode="HTML")
            
        else:
            raw_reply = response_message.content
            final_reply = clean_markdown(raw_reply)
            
            user_memories[chat_id].append({"role": "assistant", "content": final_reply})
            bot.send_message(chat_id, final_reply, parse_mode="HTML")
            
    except Exception as e:
        error_msg = f"Oops, an error occurred: {e}"
        print(f"\n[!] {error_msg}")
        bot.send_message(chat_id, "Sorry, nahirapan akong i-process yan due to a system error.")

print("___________________________________________________")
print("AI Bot is Ready!")
print("Press Ctrl+C to stop.")
print("___________________________________________________")

if __name__ == "__main__":
    bot.infinity_polling()
