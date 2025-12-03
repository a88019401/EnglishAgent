# ✅ app run 重新改寫（main Flask 檔）
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
from prompt import (
    format_agent1_prompt,
    format_agent2_prompt,
    format_answer_explanation_prompt
)
from rag_utils import (
    search_manual_chunks,
    search_question_bank
)
import os
import data2sheet
import requests
import re
import json



app = Flask(__name__)
app.secret_key = "supersecretkey"
CORS(app)
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
gas_url = "https://script.google.com/macros/s/AKfycbyJFFavEZajjACFuQPphh21YjvdU4OloU7LNfowRWEdj-Bvvc-2Nk3rbFKclVjB61XS/exec"
# 檢測答案選項
def is_answer_pattern(text): 
    return bool(re.fullmatch(r"[abcdABCD]{3,10}", text.strip()))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["POST"])
def login():
    payload = request.json
    
    res = requests.post(gas_url, json=payload)
    return res.text, res.status_code

@app.route("/englishAgent")
def englishAgent():
    student_id = request.args.get("studentId")
    return render_template("englishAgent.html", studentId=student_id)

@app.route("/fetchHistoryData", methods=["POST"])
def fetchHistoryData():
    payload = request.json
    
    # 從 Google Sheet (GAS) 取得資料
    res = requests.post(gas_url, json=payload)

    if res.status_code != 200:
        return jsonify({"error": "GAS Error", "details": res.text}), 500

    try:
        gas_data = res.json()
    except:
        return jsonify({"error": "GAS returned invalid JSON", "content": res.text}), 500
    

    student_id = payload.get("data")
    action = payload.get("action")

    if action in ["fetch_topics", "fetch_detail"]:
        return jsonify(gas_data)
    
    history_data = gas_data
    
    print(json.dumps(history_data, ensure_ascii=False, indent=2))

    # 情況 A: 沒有歷史紀錄 (history_data 為布林值 true 或空 list)
    if history_data == True or not history_data:
        user_content = f"用戶名稱為{student_id}"
        agent_answer_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "你是一個英文助理專注於提供英文的相關知識，user的content為你要服務對象的名稱，負責的任務為幫助老師進行出題、解題以及製作教材。"
                        "請你以一個第一次使用的狀態介紹說明並請老師輸入要進行的活動的關鍵字，如: 現在簡單式。"
                        "agent範例: 您好！我是您的英文助理，可以協助您製作教材、出題及解題。請告訴我您需要幫助的英文主題或語法重點，例如：「現在簡單式」、「被動語態」等，我將竭誠協助您！"
                        "【重要規則】："
                        "1. 請「嚴格使用繁體中文」回答，即使歷史資料是英文，也要用中文進行總結。"
                        "2. 格式請使用 Markdown (如條列點、粗體)，不要使用純文字長篇大論。"
                        "3. 針對最新的學習內容（資料列後方）給予較高權重。"
                        "4. 結尾請給予老師一個簡短的後續教學建議。"
                    )
                },
                {"role": "user", "content": user_content}
            ]
        )
        agent_answer = agent_answer_response.choices[0].message.content
        return jsonify({
            "assistant_answer": agent_answer,
            "raw_history": [] # 回傳空陣列
        })
    
    # 情況 B: 有歷史紀錄
    else:
        content_str = f"""
            學生姓名：{student_id}
            歷史資料：
            {json.dumps(history_data, ensure_ascii=False, indent=2)} 
        """
        
        agent_answer_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "你是一個專業的英文教學助理。請根據提供的學生歷史資料，"
                        "為老師總結該學生的學習狀況。"
                        "請以親切的口吻進行說明並且user的content為你要服務對象的名稱"
                        "【重要規則】："
                        "1. 請「嚴格使用繁體中文」回答，即使歷史資料是英文，也要用中文進行總結。"
                        "2. 格式請使用 Markdown (如條列點、粗體)，不要使用純文字長篇大論。"
                        "3. 針對最新的學習內容（資料列後方）給予較高權重。"
                        "4. 結尾請給予老師一個簡短的後續教學建議。"
                    )
                },
                {"role": "user", "content": content_str}
            ]
        )
        agent_answer = agent_answer_response.choices[0].message.content
        
        return jsonify({
            "assistant_answer": agent_answer,
            "raw_history": history_data 
        })
    
"""
專門用來生成簡短標題的 Agent
"""   
def generate_chat_title(user_text):

    try:
        response = client.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": "你是一個對話紀錄摘要員。請將使用者的輸入概括為一個「5到10個字以內」的繁體中文標題。直接輸出標題即可，不要加引號。"},
                {"role": "user", "content": user_text}
            ],
            max_tokens=20, # 限制輸出長度
            temperature=0.5
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Title generation failed: {e}")
        return user_text[:10] + "..." # 失敗時的回退方案    

"""
    進行新的對話內容
"""
@app.route("/new_conversation", methods=["POST"])
def new_conversation():
    try:
        session.pop('last_practice_questions', None)
        session.pop('last_topic', None)
        session.pop('current_mode', None)
        session.pop('current_topic', None) # ✅ 清除 Topic
        
        return jsonify({"status": "success", "message": "對話狀態已重置"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

"""
回答教材內容的說明（Agent1）

提供練習題（Agent2）

若學生問的是答案或解釋，則依照歷史資料進行答題解析（Answer模式）

category: 1. 教材  2. 練習題   3. 回答解析
"""
@app.route("/ask_multiagent_rag", methods=["POST"])
def ask_multiagent_rag():
    data = request.json
    user_prompt = data.get("prompt")
    id_value = request.args.get('studentId')
    
    if not user_prompt:
        return jsonify({"error": "請輸入問題"}), 400

    print(f"[User] {user_prompt}")

    # --- ✅ 新增：處理 Topic (主題) 邏輯 ---
    # 1. 嘗試從 Session 拿當前主題
    current_topic = session.get("current_topic")
    
    # 2. 如果沒有主題 (新對話) 且不是在回答問題模式，就生成新標題
    #    或是簡單判斷：只要 Session 沒 Topic 就生成
    if not current_topic:
        current_topic = generate_chat_title(user_prompt)
        session["current_topic"] = current_topic
        print(f"[New Topic] {current_topic}")
    # -------------------------------------

    # RAG 處理
    manual_context = search_manual_chunks(user_prompt)
    question_context = search_question_bank(user_prompt)

    if not manual_context: manual_context = "⚠️ 找不到教材資料"
    if not question_context: question_context = "⚠️ 找不到題庫資料"

    last_questions = session.get("last_practice_questions", "（目前尚無歷史題目）")

    # ✅ 模式 1: 解題解析 (Answer Mode)
    if ("答案" in user_prompt or is_answer_pattern(user_prompt)) and session.get("last_practice_questions"):
        prompt = format_answer_explanation_prompt(
            session.get("last_topic", ""),
            manual_context,
            question_context,
            session.get("last_practice_questions", ""),
            user_prompt
        )

        agent_answer_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "你是英文助教兼解題老師。請根據【教材內容】【題庫內容】【5題英文題目】提供每題正確答案與詳細解析。格式：1. 答案：（選項字母）+解析。如果有學生答案，你必須要協助批改"},
                {"role": "user", "content": prompt}
            ]
        )
        agent_answer = agent_answer_response.choices[0].message.content
        session["current_mode"] = None

        # ✅ 修正：Payload 加入 topic
        payload = {
            "sheetName": "student_data",
            "action": "add", 
            "data": [{
                "student": id_value,
                "category": "answer",
                "topic": current_topic,  # <--- 加入這行
                "user": user_prompt, 
                "agent": agent_answer
            }]
        }
        data2sheet.doPost(payload)

        return jsonify({
            "question": user_prompt,
            "assistant_answer": agent_answer,
            "practice_questions": "(上一題練習題，未重複提供)",
            "topic": current_topic # 回傳給前端更新 UI
        })

    # ... (省略中間的「回顧」邏輯，這部分如果是純讀取 fetch，不需要寫入 topic) ...

    # ✅ 模式 2: 正常出題 (Lesson & Question Mode)
    
    ## (1) Agent 1: 教材
    agent1_prompt = format_agent1_prompt(user_prompt, manual_context, last_questions)
    agent1_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "你是英文助教，要協助台灣國中的英文老師，僅嚴格的【教材內容】內的內容，提供教師要求的文法筆記或上課內容講義。絕對不能脫離【教材內容】的內容需簡潔、符合國中程度"},
            {"role": "user", "content": agent1_prompt}
        ]
    )
    agent1_answer = agent1_response.choices[0].message.content

    # ✅ 修正：Payload 加入 topic
    payload = {
        "sheetName": "student_data",
        "action": "add", 
        "data": [{
            "student": id_value,
            "category": "lesson",
            "topic": current_topic, 
            "user": user_prompt, 
            "agent": agent1_answer
        }]
    }
    data2sheet.doPost(payload)

    ## (2) Agent 2: 出題
    agent2_prompt = format_agent2_prompt(user_prompt, question_context, manual_context)
    agent2_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "你是英文測驗題目設計老師，要協助台灣國中的英文老師。根據嚴格的依照【題庫內容】篩選5題英文單選題（a/b/c/d），不得超出主題。只提供題目，不提供答案。"},
            {"role": "user", "content": agent2_prompt}
        ]
    )
    agent2_answer = agent2_response.choices[0].message.content

    # ✅ 修正：Payload 加入 topic
    payload = {
        "sheetName": "student_data",
        "action": "add", 
        "data": [{
            "student": id_value,
            "category": "question",
            "topic": current_topic, # <--- 加入這行
            "user": user_prompt, 
            "agent": agent2_answer
        }]
    }
    data2sheet.doPost(payload)

    session["last_practice_questions"] = agent2_answer
    session["last_topic"] = user_prompt
    session["current_mode"] = "waiting_for_answer"

    return jsonify({
        "question": user_prompt,
        "assistant_answer": agent1_answer,
        "practice_questions": agent2_answer,
        "topic": current_topic # 回傳給前端
    })

"""
用設置當前的主題

"""
@app.route("/set_current_topic", methods=["POST"])
def set_current_topic():
    try:
        data = request.json
        topic = data.get("topic")
        
        if topic:
            # 1. 更新當前主題
            session["current_topic"] = topic
            
            # 2. 切換主題時，務必清除「上一題」的暫存狀態
            # 避免使用者在 A 主題答題，卻被判定為回答 B 主題的題目
            session.pop('last_practice_questions', None)
            session.pop('last_topic', None)
            session["current_mode"] = None 
            
            print(f"✅ 主題已切換至: {topic}")
            return jsonify({"status": "success", "message": f"Topic set to {topic}"})
        
        return jsonify({"error": "No topic provided"}), 400
    except Exception as e:
        print(f"❌ 切換主題失敗: {e}")
        return jsonify({"error": str(e)}), 500
    

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=False)
