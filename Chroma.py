# ✅ Chroma.py (AWS Bedrock Titan Embeddings 版)
import os
import glob
import json
import boto3
import chromadb
from PyPDF2 import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# -------- Bedrock Runtime --------
REGION = "ap-southeast-2"
bedrock_runtime = boto3.client("bedrock-runtime", region_name=REGION)

# 建議用 v2（若你帳號沒開權限會報錯，要去 Bedrock Model access 勾 Titan）
TITAN_EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"  # 或 "amazon.titan-embed-text-v1:0"

# -------- Chroma --------
chroma_client = chromadb.PersistentClient(path="./chroma_db")

def extract_text_with_metadata(pdf_path):
    """讀取 PDF 並回傳每一頁的文字與頁碼"""
    pages_content = []
    try:
        reader = PdfReader(pdf_path)
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                clean_text = text.replace('\n', ' ').replace('  ', ' ')
                pages_content.append({"text": clean_text, "page": i + 1})
    except Exception as e:
        print(f"❌ 讀取失敗：{pdf_path}, {e}")
    return pages_content

def get_embedding(text: str):
    """使用 AWS Bedrock Titan Embeddings 產生向量"""
    body = {"inputText": text}

    resp = bedrock_runtime.invoke_model(
        modelId=TITAN_EMBED_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body, ensure_ascii=False)
    )
    data = json.loads(resp["body"].read())
    return data["embedding"]

def build_manuals_collection():
    # ⚠️ 重要：換 embedding 模型後維度會變，請用新 collection 名稱避免維度衝突
    collection = chroma_client.get_or_create_collection(name="manuals_titan_v2")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
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
                embedding = get_embedding(chunk)

                collection.add(
                    ids=[f"{filename}_p{page_data['page']}_{idx}"],
                    documents=[chunk],
                    embeddings=[embedding],
                    metadatas=[{
                        "source": filename,
                        "page": page_data["page"],
                        "type": "textbook",
                        "embed_model": TITAN_EMBED_MODEL_ID
                    }]
                )

    print("✅ 教材庫建立完成")

if __name__ == "__main__":
    build_manuals_collection()
