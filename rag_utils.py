import os
import json
import boto3
import chromadb
from dotenv import load_dotenv

load_dotenv()

# --- 初始化 AWS 用戶端 ---
# 確保 EC2 的 IAM Role 具備 Bedrock 存取權限
bedrock_runtime = boto3.client(service_name='bedrock-runtime', region_name='ap-southeast-2')

# --- 初始化 Vector DB ---
chroma_client = chromadb.PersistentClient(path="./chroma_db")

def get_manual_collection():
    return chroma_client.get_or_create_collection(name="manuals")

def get_question_collection():
    return chroma_client.get_or_create_collection(name="english_questions")

def get_embedding(text):
    """
    將原本的 OpenAI Embedding 替換為 AWS Bedrock Titan Embedding
    """
    model_id = "amazon.titan-embed-text-v1"
    
    body = json.dumps({
        "inputText": text,
    })

    try:
        response = bedrock_runtime.invoke_model(
            body=body, 
            modelId=model_id, 
            accept='application/json', 
            contentType='application/json'
        )
        response_body = json.loads(response.get('body').read())
        # Titan 回傳的欄位名稱是 embedding
        return response_body['embedding']
    except Exception as e:
        print(f"❌ Embedding 生成失敗: {e}")
        # 回傳一個空向量或報錯，視您的邏輯而定
        return [0] * 1536  # 注意：Titan V1 的維度是 1536，與 OpenAI 相同

# --- 搜尋邏輯 (保持不變) ---

def search_question_bank(query_text, top_k=5):
    embedding = get_embedding(query_text)
    results = get_question_collection().query(
        query_embeddings=[embedding],
        n_results=top_k,
        include=["documents", "distances"]
    )
    documents = results["documents"][0] if results["documents"] else []
    return "\n---\n".join(documents)

def search_manual_chunks(query_text, top_k=8, file_filter=None):
    embedding = get_embedding(query_text)
    
    where_clause = None 
    if file_filter:
        where_clause = {"source": file_filter}

    results = get_manual_collection().query(
        query_embeddings=[embedding],
        n_results=top_k,
        where=where_clause,
        include=["documents", "metadatas"]
    )
    
    formatted_results = []
    if results["documents"]:
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            formatted_results.append(f"[教材背景: {meta['source']}]\n{doc}")
            
    return "\n\n".join(formatted_results)