from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import boto3
import json
import requests
import re
import os

# 匯入原本的輔助工具與 Prompt 範本
from prompt import (
    format_lesson_prompt,
    format_quiz_prompt,
    format_answer_explanation_prompt,
    format_router_prompt
)
from rag_utils import (
    search_manual_chunks,
    search_question_bank
)
import data2sheet

# --- AWS RDS 配置 ---
app = Flask(__name__)
app.secret_key = "aws_agent_secure_key"

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://admin:12345678@database-1.cpmu2i0isc0x.ap-southeast-2.rds.amazonaws.com:3306/database-1'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
CORS(app)

# 1. 對應 image_5708e6.png (使用者資料)
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    student = db.Column(db.String(50), unique=True, nullable=False)
    pwd = db.Column(db.String(50), nullable=False)

# 2. 對應 image_5708c9.png (對話紀錄)
class StudentLog(db.Model):
    __tablename__ = 'student_logs'
    id = db.Column(db.Integer, primary_key=True)
    student = db.Column(db.String(50), index=True)
    category = db.Column(db.String(50))
    topic = db.Column(db.String(255))
    user_input = db.Column(db.Text)
    agent_output = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.now)

# 初始化資料表
with app.app_context():
    db.create_all()

with app.app_context():
    if not User.query.filter_by(student='admin').first():
        admin_user = User(student='admin', pwd='admin')
        db.session.add(admin_user)
        db.session.commit()

# --- AWS Bedrock 初始化 ---
# 注意：請確保您的 EC2 區域與 Bedrock 區域一致 (例如 ap-southeast-2)
# 且已經在 Bedrock Console 開通了 Claude 3 的存取權限
bedrock_runtime = boto3.client(service_name='bedrock-runtime', region_name='ap-southeast-2')

def call_bedrock(system_prompt, user_content, model_type="sonnet"):
    """
    通用 AWS Bedrock 呼叫函數
    model_type: "sonnet" (高品質) 或 "haiku" (快速低成本)
    """
    if model_type == "sonnet":
        model_id = "us.anthropic.claude-3-5-sonnet-20240620-v1:0"
    else:
        model_id = "anthropic.claude-3-haiku-20240307-v1:0"

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.5
    })

    try:
        response = bedrock_runtime.invoke_model(body=body, modelId=model_id)
        response_body = json.loads(response.get('body').read())
        return response_body['content'][0]['text']
    except Exception as e:
        print(f"❌ Bedrock 呼叫失敗: {e}")
        return "抱歉，目前 AI 服務暫時無法回應，請稍後再試。"

# Google Sheet 串接網址
gas_url = "https://script.google.com/macros/s/AKfycbyJFFavEZajjACFuQPphh21YjvdU4OloU7LNfowRWEdj-Bvvc-2Nk3rbFKclVjB61XS/exec"

def is_answer_pattern(text): 
    return bool(re.fullmatch(r"[abcdABCD]{3,10}", text.strip()))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    
    # 查詢資料庫是否存在該用戶且密碼正確
    user = User.query.filter_by(student=username, pwd=password).first()
    
    if user:
        return jsonify({"status": "success", "message": "Login successful"})
    else:
        return jsonify({"status": "fail", "message": "Invalid username or password"}), 401

@app.route("/englishAgent")
def englishAgent():
    student_id = request.args.get("studentId")
    return render_template("englishAgent.html", studentId=student_id)

@app.route("/fetchHistoryData", methods=["POST"])
def fetchHistoryData():

    payload = request.json
    student_id = payload.get("data")
    action = payload.get("action")

    # 從 RDS 撈取資料
    logs = StudentLog.query.filter_by(student=student_id).order_by(StudentLog.timestamp.asc()).all()
    
    # 格式化為原本程式預期的 list
    history_data = [
        {
            "student": l.student,
            "category": l.category,
            "topic": l.topic,
            "user": l.user_input,
            "agent": l.agent_output
        } for l in logs
    ]

    if action in ["fetch_topics", "fetch_detail"]:
        if action == "fetch_detail":
            current_topic = session.get("current_topic")
            if isinstance(history_data, list):
                # 1. 取出最後 3 筆 (或是你設定的對話輪數)
                # Python 的 [-3:] 會自動處理長度不足 3 的情況，非常安全
                recent_logs = history_data[-3:] 
                
                # 2. 更新 Session
                session["recent_history"] = recent_logs
            
            # 3. 確保當前主題也被鎖定 (雙重保險，防止 /set_current_topic 沒跑完)
            if current_topic:
                session["current_topic"] = current_topic
            
            print(f"🔄 [Context Reloaded]: Topic '{current_topic}' loaded with {len(recent_logs)} turns.")
        
            return jsonify(history_data)
        else:
            return jsonify(history_data)
    
    print(json.dumps(history_data, ensure_ascii=False, indent=2))    
    # 情況 A: 沒有歷史紀錄 - 使用 Bedrock 生成歡迎詞
    if history_data == True or not history_data:
        system_msg = (
            "你是一個英文助理專注於提供英文的相關知識，user的content為你要服務對象的名稱，負責的任務為幫助老師進行出題、解題以及製作教材。"
                "請你以一個第一次使用的狀態介紹說明並請老師輸入要進行的活動的關鍵字，如: 現在簡單式。"
                "agent範例: 您好！我是您的英文助理，可以協助您製作教材、出題及解題。請告訴我您需要幫助的英文主題或語法重點，例如：「現在簡單式」、「被動語態」等，我將竭誠協助您！"
                "【重要規則】："
                "1. 請「嚴格使用繁體中文」回答，即使歷史資料是英文，也要用中文進行總結。"
                "2. 格式請使用 Markdown (如條列點、粗體)，不要使用純文字長篇大論。"
                "3. 針對最新的學習內容（資料列後方）給予較高權重。"
                "4. 結尾請給予老師一個簡短的後續教學建議。"
        )
        user_msg = f"用戶名稱為 {student_id}"
        agent_answer = call_bedrock(system_msg, user_msg, model_type="haiku")
        
        return jsonify({
            "assistant_answer": agent_answer,
            "raw_history": []
        })
    
    # 情況 B: 有歷史紀錄 - 使用 Bedrock 生成學習總結
    else:
        system_msg = (
            "你是一個專業的英文教學助理。請根據提供的學生歷史資料，"
                        "為老師總結該學生的學習狀況。"
                        "請以親切的口吻進行說明並且user的content為你要服務對象的名稱"
                        "【重要規則】："
                        "1. 請「嚴格使用繁體中文」回答，即使歷史資料是英文，也要用中文進行總結。"
                        "2. 格式請使用 Markdown (如條列點、粗體)，不要使用純文字長篇大論。"
                        "3. 針對最新的學習內容（資料列後方）給予較高權重。"
                        "4. 結尾請給予老師一個簡短的後續教學建議。"
        )
        user_msg = f"學生姓名：{student_id}\n歷史資料：\n{json.dumps(history_data, ensure_ascii=False)}"
        agent_answer = call_bedrock(system_msg, user_msg, model_type="sonnet")
        
        return jsonify({
            "assistant_answer": agent_answer,
            "raw_history": history_data 
        })

def generate_chat_title(user_text):
    system_msg = "你是一個對話紀錄摘要員。請將輸入概括為一個「5到10個字以內」的繁體中文標題。直接輸出標題即可。"
    return call_bedrock(system_msg, user_text, model_type="haiku").strip()

@app.route("/new_conversation", methods=["POST"])
def new_conversation():
    session.pop('last_practice_questions', None)
    session.pop('current_topic', None)
    session.pop('recent_history', None)
    return jsonify({"status": "success"})

def format_chat_history(history_list):
    if not history_list: return ""
    formatted_str = "\n【近期對話紀錄】：\n"
    for item in history_list:
        formatted_str += f"User: {item['user']}\nAssistant: {item['agent']}\n---\n"
    return formatted_str

@app.route("/ask_multiagent_rag", methods=["POST"])
def ask_multiagent_rag():
    data = request.json
    user_prompt = data.get("prompt")
    id_value = request.args.get('studentId')
    
    if not user_prompt:
        return jsonify({"error": "請輸入問題"}), 400

    current_topic = session.get("current_topic")
    last_questions_exist = bool(session.get("last_practice_questions"))

    recent_history = session.get("recent_history", [])
    if not current_topic:
        current_topic = generate_chat_title(user_prompt)
        session["current_topic"] = current_topic
        print(f"🆕 [New Topic Created & Locked]: {current_topic}")
    else:
        print(f"🔒 [Using Existing Topic]: {current_topic}")

    chat_history_str = format_chat_history(recent_history)

    # 【Mother Agent】意圖識別 - 強制 JSON
    router_prompt = format_router_prompt(user_prompt, last_questions_exist, chat_history_str)
    router_system = "你是一個意圖分析助手。請根據用戶輸入，分析其意圖為 LESSON (教學), QUIZ (出題), ANSWER (解題) 或 CHAT (閒聊)。必須回傳 JSON 格式。"
    
    try:
        router_raw = call_bedrock(router_system, router_prompt, model_type="haiku")
        # 清除可能存在的 Markdown 標籤
        router_raw = router_raw.replace("```json", "").replace("```", "").strip()
        router_result = json.loads(router_raw)
        reasoning = router_result.get("reasoning", "")
        intent = router_result.get("intent", "CHAT")
        search_term = router_result.get("search_term", "")
        print(f"[Router Thought]: {reasoning}") 
        print(f"[Router Intent]: {intent}, [Search Term]: {search_term}")
    except:
        intent = "CHAT"

    # RAG 檢索
    manual_context = ""
    question_context = ""
    has_valid_material = False
    
    if intent in ["LESSON", "QUIZ", "ANSWER"]:
        final_query = search_term if search_term else user_prompt
        print(f"[Searching]: {final_query}")

        manual_context = search_manual_chunks(final_query)
        question_context = search_question_bank(final_query)
        has_valid_material = bool(manual_context and len(manual_context) > 10)

    # 分流處理
    agent_answer = ""
    resp_type = "chat"

    # A: 解題
    if intent == "ANSWER" and last_questions_exist:
        system_msg = "你是英文解題老師。請根據教材與題目提供正確答案與詳細解析。如果學生有答案，請協助批改。"
        prompt = format_answer_explanation_prompt(manual_context, session.get("last_practice_questions"), user_prompt, chat_history_str)
        agent_answer = call_bedrock(system_msg, prompt, model_type="sonnet")
        resp_type = "answer"

    # B: 教學
    elif intent == "LESSON" and not has_valid_material:
        system_msg = "你是英文助教，當教材資料不足時，請用簡單的方式告知學生，並引導他們提供更多資訊。"
        prompt = f"目前我找不到關於「{user_prompt}」的相關教材內容。請用簡短的繁體中文回應，並引導我提供更多資訊或更換主題。"
        agent_answer = call_bedrock(system_msg, prompt, model_type="haiku")
        resp_type = "lesson"
    elif intent == "LESSON":
        if not has_valid_material:
            agent_answer = f"抱歉，我目前的教材資料庫中好像還沒有關於「{search_term or user_prompt}」的內容。我們可以先討論其他主題嗎？"
        else:
            system_msg = "你是英文助教，嚴格根據提供之【教材內容】提供文法講義。內容需簡潔、符合國中程度。"
            prompt = format_lesson_prompt(user_prompt, manual_context, chat_history_str, session.get("last_practice_questions", ""), search_term)
            agent_answer = call_bedrock(system_msg, prompt, model_type="sonnet")
            resp_type = "lesson"

    # C: 出題
    elif intent == "QUIZ":
        system_msg = "你是英文測驗老師。篩選 5 題英文單選題。只提供題目，不提供答案。"
        prompt = format_quiz_prompt(user_prompt, question_context, manual_context, chat_history_str)
        agent_answer = call_bedrock(system_msg, prompt, model_type="sonnet")
        session["last_practice_questions"] = agent_answer
        resp_type = "quiz"

    # D: 閒聊
    else:
        system_msg = "你是一個親切的英文助教。請用簡短繁體中文回應，並引導使用者開始學習。"
        agent_answer = call_bedrock(system_msg, user_prompt, model_type="haiku")

    # 更新歷史與儲存
    save_to_sheet(id_value, intent.lower(), current_topic, user_prompt, agent_answer)
    recent_history.append({"user": user_prompt, "agent": agent_answer})
    session["recent_history"] = recent_history[-3:]
    
    return jsonify({
        "type": resp_type,
        "assistant_answer": agent_answer,
        "topic": current_topic
    })

def save_to_sheet(student_id, category, topic, user_msg, agent_msg, sheet_name="student_data"):
    try:
        new_log = StudentLog(
            student=student_id,
            category=category,
            topic=topic,
            user_input=user_msg,
            agent_output=agent_msg
        )
        db.session.add(new_log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"❌ 儲存至 RDS 失敗: {e}")

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
            
            print(f"✅ 主題已切換至: {topic}")
            return jsonify({"status": "success", "message": f"Topic set to {topic}"})
        
        return jsonify({"error": "No topic provided"}), 400
    except Exception as e:
        print(f"❌ 切換主題失敗: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # 在 EC2 部署時建議關閉 debug
    app.run(host="0.0.0.0", port=5000, debug=False)