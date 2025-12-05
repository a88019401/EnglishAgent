# ✅ rag_utils.py
import os
import chromadb
from openai import OpenAI
from dotenv import load_dotenv
from prompt import format_quiz_prompt

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("請設定 .env 裡的 OPENAI_API_KEY")

client = OpenAI(api_key=api_key)
chroma_client = chromadb.PersistentClient(path="./chroma_db")

def get_manual_collection():
    return chroma_client.get_or_create_collection(name="manuals")

def get_question_collection():
    return chroma_client.get_or_create_collection(name="english_questions")

def get_embedding(text):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=[text]
    )
    return response.data[0].embedding

def search_question_bank(query_text, top_k=5):
    embedding = get_embedding(query_text)
    results = get_question_collection().query(
        query_embeddings=[embedding],
        n_results=top_k,
        include=["documents", "distances"]
    )
    documents = results["documents"][0] if results["documents"] else []
    return "\n---\n".join(documents)

# def run_agent1_retrieve_context(user_prompt):
#     manual = search_manual_chunks(user_prompt)
#     questions = search_question_bank(user_prompt)
#     return f"【教材內容】\n{manual}\n\n【題庫內容】\n{questions}"

# def run_agent2_generate_examples(user_prompt,  question_context):
#     followup_prompt = format_quiz_prompt(user_prompt,  question_context)
#     response = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[
#             {"role": "system", "content": "你是英文測驗題目設計老師，嚴格只能根據教師指定的【題庫內容】出題，禁止使用自身語言知識。"},
#             {"role": "user", "content": followup_prompt}
#         ]
#     )
#     return response.choices[0].message.content



def search_manual_chunks(query_text, top_k=3, file_filter=None):
    """
    file_filter: 如果使用者指定 "國二範圍"，可以傳入檔案名稱來過濾
    """
    embedding = get_embedding(query_text)
    
    #  修正點：預設為 None，而不是 {}
    where_clause = None 
    if file_filter:
        where_clause = {"source": file_filter}

    results = get_manual_collection().query(
        query_embeddings=[embedding],
        n_results=top_k,
        where=where_clause, # ⭐ 如果是 None，Chroma 就會搜尋全部，不會報錯
        include=["documents", "metadatas"]
    )
    
    # 格式化輸出
    formatted_results = []
    if results["documents"]:
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            formatted_results.append(f"[教材背景: {meta['source']}]\n{doc}")
            
    return "\n\n".join(formatted_results)