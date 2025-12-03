# ✅ Chroma.py (改良版)
import os
import glob
import json
from openai import OpenAI
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
# 改用 LangChain 的切割器會比自己寫迴圈更聰明
from langchain_text_splitters import RecursiveCharacterTextSplitter 
from PyPDF2 import PdfReader

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
chroma_client = chromadb.PersistentClient(path="./chroma_db") # 建議用 PersistentClient 比較穩定

def extract_text_with_metadata(pdf_path):
    """讀取 PDF 並回傳每一頁的文字與頁碼"""
    pages_content = []
    try:
        reader = PdfReader(pdf_path)
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                # 簡單的清洗：去除多餘換行，保留段落
                clean_text = text.replace('\n', ' ').replace('  ', ' ')
                pages_content.append({"text": clean_text, "page": i + 1})
    except Exception as e:
        print(f"❌ 讀取失敗：{pdf_path}, {e}")
    return pages_content

def get_embedding(text):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=[text]
    )
    return response.data[0].embedding

def build_manuals_collection():
    collection = chroma_client.get_or_create_collection(name="manuals")
    
    # 使用遞迴切割器，優先在句號、換行處切割，並設定重疊
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100, # 重疊 100 字，避免切斷文法規則
        separators=["\n\n", "\n", "。", "！", "？", ".", " ", ""]
    )

    pdf_files = glob.glob("data/user_manuals/*.pdf")
    
    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        print(f"📄 處理：{filename}")
        
        pages = extract_text_with_metadata(pdf_path)
        
        for page_data in pages:
            chunks = splitter.split_text(page_data["text"])
            
            for idx, chunk in enumerate(chunks):
                # ⭐ 這裡雖然會花一點錢，但如果可以由 AI 幫忙生成這段 chunk 的摘要當作 embedding 會更準
                # 目前先維持原始做法，但在 metadata 加入來源資訊
                embedding = get_embedding(chunk)
                
                collection.add(
                    ids=[f"{filename}_p{page_data['page']}_{idx}"],
                    documents=[chunk],
                    embeddings=[embedding],
                    metadatas=[{
                        "source": filename,
                        "page": page_data['page'],
                        "type": "textbook"
                    }] # ⭐ 關鍵：加入 Metadata
                )
    print("✅ 教材庫建立完成")

# build_questions_collection 維持你原本的邏輯即可，或是同樣加入 difficulty (難度) 的 metadata
if __name__ == "__main__":
    build_manuals_collection()