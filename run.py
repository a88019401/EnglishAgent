# ✅ app run 重新改寫（main Flask 檔）
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
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
        if action == "fetch_detail":
            current_topic = session.get("current_topic")
            if isinstance(gas_data, list):
                # 1. 取出最後 3 筆 (或是你設定的對話輪數)
                # Python 的 [-3:] 會自動處理長度不足 3 的情況，非常安全
                recent_logs = gas_data[-3:] 
                
                # 2. 更新 Session
                session["recent_history"] = recent_logs
            
            # 3. 確保當前主題也被鎖定 (雙重保險，防止 /set_current_topic 沒跑完)
            if current_topic:
                session["current_topic"] = current_topic
            
            print(f"🔄 [Context Reloaded]: Topic '{current_topic}' loaded with {len(recent_logs)} turns.")
        
            return jsonify(gas_data)
        else:
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
        session.pop('current_topic', None) # 清除 Topic
        session.pop('recent_history', None) # 清除歷史紀錄
        
        return jsonify({"status": "success", "message": "對話狀態已重置"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
"""
    記錄過去對話的歷史資料
"""   
def format_chat_history(history_list):
    if not history_list:
        return ""
    
    formatted_str = "\n【近期對話紀錄 (越下面越新)】：\n"
    for item in history_list:
        formatted_str += f"User: {item['user']}\nAssistant: {item['agent']}\n---\n"
    return formatted_str
"""
    目前有個母agent負責指派其他子agent 來確定要做甚麼事情
    母agent會根據user的需求產生intent 並根據intent來判斷目前要由哪個agnet進行處理
"""
@app.route("/ask_multiagent_rag", methods=["POST"])
def ask_multiagent_rag():
    data = request.json
    user_prompt = data.get("prompt")
    id_value = request.args.get('studentId')
    
    if not user_prompt:
        return jsonify({"error": "請輸入問題"}), 400

    # 取得 Session 狀態
    current_topic = session.get("current_topic")
    last_questions_exist = bool(session.get("last_practice_questions"))

    recent_history = session.get("recent_history", [])

    # 確定目前是否有主題
    if not current_topic:
        current_topic = generate_chat_title(user_prompt)
        session["current_topic"] = current_topic
        print(f"🆕 [New Topic Created & Locked]: {current_topic}")
    else:
        print(f"🔒 [Using Existing Topic]: {current_topic}")

    chat_history_str = format_chat_history(recent_history)

    # 【Mother Agent】意圖識別
    router_prompt = format_router_prompt(user_prompt, last_questions_exist, chat_history_str)
    try:
        router_response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"}, # 強制 JSON
            messages=[{"role": "user", "content": router_prompt}]
        )
        router_result = json.loads(router_response.choices[0].message.content)

        reasoning = router_result.get("reasoning", "")
        intent = router_result.get("intent", "CHAT")
        search_term = router_result.get("search_term", "") # 拿到優化後的關鍵字

        print(f"[Router Thought]: {reasoning}") 
        print(f"[Router Intent]: {intent}, [Search Term]: {search_term}")
    except:
        intent = "CHAT" # Fallback

    # 3. 準備 RAG 資料 (如果是 CHAT 就不需要浪費搜尋資源)
    manual_context = ""
    question_context = ""
    if intent in ["LESSON", "QUIZ", "ANSWER"]:

        final_query = search_term if search_term else user_prompt
        print(f"[Searching]: {final_query}")

        manual_context = search_manual_chunks(final_query)
        question_context = search_question_bank(final_query)

        # 檢查手冊是否有查到足夠的資訊
        if manual_context and len(manual_context) > 10: 
            has_valid_material = True
        else:
            print(f"[Warning] No material found for: {final_query}")
        
    

    # --- 分流處理 ---

    # 情況 A: 解題 (ANSWER)
    if intent == "ANSWER" and last_questions_exist:
        prompt = format_answer_explanation_prompt(
            manual_context,
            session.get("last_practice_questions", ""),
            user_prompt,
            chat_history_str
        )

        agent_answer_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "你是英文助教兼解題老師。請根據【教材內容】【題庫內容】【5題英文題目】提供每題正確答案與詳細解析。格式：1. 答案：（選項字母）+解析。如果有學生答案，你必須要協助批改"},
                {"role": "user", "content": prompt}
            ]
        )
        agent_answer = agent_answer_response.choices[0].message.content

        save_to_sheet(id_value, intent.lower(), current_topic, user_prompt, agent_answer)
        recent_history.append({"user": user_prompt, "agent": agent_answer})

        if len(recent_history) > 3:
            recent_history.pop(0) # 移除最舊的
        session["recent_history"] = recent_history

        return jsonify({
            "type": "answer",
            "question": user_prompt,
            "assistant_answer": agent_answer,
            "practice_questions": "(上一題練習題，未重複提供)",
            "topic": current_topic # 回傳給前端更新 UI
        })

    # 情況 B: 純教學 (LESSON)
    elif intent == "LESSON" and not has_valid_material:
        # 這裡不呼叫 Agent 1，而是直接呼叫一個道歉/引導 Agent，或者直接回傳
        fallback_msg = f"抱歉，我目前的教材資料庫中好像還沒有關於「{search_term if search_term else user_prompt}」的詳細內容。我們可以先從其他基礎主題開始嗎？"
        
        # 寫入歷史並回傳
        recent_history.append({"user": user_prompt, "agent": fallback_msg})
        save_to_sheet(id_value, "chat", current_topic, user_prompt, fallback_msg)

        if len(recent_history) > 3:
            recent_history.pop(0) # 移除最舊的
        session["recent_history"] = recent_history
        
        return jsonify({
            "type": "chat",
            "assistant_answer": fallback_msg,
            "topic": current_topic
        })
    elif intent == "LESSON":
        agent1_prompt = format_lesson_prompt(
            user_prompt, 
            manual_context,
            chat_history_str, 
            session.get("last_practice_questions", ""),
            search_term
        )
        agent1_res = client.chat.completions.create(
            model="gpt-4o",
             messages=[
            {"role": "system", "content": "你是英文助教，要協助台灣國中的英文老師，僅嚴格的【教材內容】內的內容，提供教師要求的文法筆記或上課內容講義。絕對不能脫離【教材內容】的內容需簡潔、符合國中程度"},
            {"role": "user", "content": agent1_prompt}
        ]
        )
        lesson_content = agent1_res.choices[0].message.content
        save_to_sheet(id_value, intent.lower(), current_topic, user_prompt, lesson_content)

        recent_history.append({"user": user_prompt, "agent": lesson_content})

        if len(recent_history) > 3:
            recent_history.pop(0) # 移除最舊的
        session["recent_history"] = recent_history

        # ★ 這裡可以做一個聰明的設計：
        # 如果使用者問的是很明確的主題，通常教完馬上出題效果最好。
        # 你可以讓 Mother Agent 決定是否要 "LESSON_AND_QUIZ"，或者是這裡做一個簡易判斷。
        # 假設我們先回傳教學內容，並在 UI 上給一個「產生練習題」的按鈕引導使用者。
        
        return jsonify({
            "type": "lesson",
            "assistant_answer": lesson_content,
            "topic": current_topic
        })

    # 情況 C: 出題 (QUIZ) - 包含資料一致性處理
    elif intent == "QUIZ":

        agent2_prompt = format_quiz_prompt(
            user_prompt, 
            question_context, 
            manual_context,
            chat_history_str
        )
        agent2_res = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "你是英文測驗題目設計老師，要協助台灣國中的英文老師。根據嚴格的依照【題庫內容】篩選5題英文單選題（a/b/c/d），不得超出主題。只提供題目，不提供答案。"},
                {"role": "user", "content": agent2_prompt}
            ]
        )
        quiz_content = agent2_res.choices[0].message.content

        recent_history.append({"user": user_prompt, "agent": quiz_content})

        if len(recent_history) > 3:
            recent_history.pop(0) # 移除最舊的
        session["recent_history"] = recent_history
        
        session["last_practice_questions"] = quiz_content
        save_to_sheet(id_value, intent.lower(), current_topic, user_prompt, quiz_content)

        return jsonify({
            "type": "quiz",
            "practice_questions": quiz_content,
            "topic": current_topic
        })

    # 情況 D: 閒聊 (CHAT)
    else:
        chat_res = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "你是一個親切的英文助教。請用簡短繁體中文回應使用者的閒聊，並引導他們開始學習英文。"},
                {"role": "user", "content": user_prompt}
            ]
        )

        chat_content = chat_res.choices[0].message.content
        save_to_sheet(id_value, intent.lower(), current_topic, user_prompt, chat_content)
        return jsonify({
            "type": "chat",
            "assistant_answer": chat_content,
            "topic": current_topic
        })
    
"""
    將資料儲存至資料庫
"""   
def save_to_sheet(student_id, category, topic, user_msg, agent_msg, sheet_name="student_data"):
    """
    通用儲存函式
    sheet_name: 預設存入 student_data，但可以指定存入 chat_logs
    """
    try:
        payload = {
            "sheetName": sheet_name, 
            "action": "add", 
            "data": [{
                "student": student_id,
                "category": category,
                "topic": topic, 
                "user": user_msg, 
                "agent": agent_msg
            }]
        }
        # 這裡建議用非同步處理 (Threading) 以免卡住回應時間，但簡單起見先直接呼叫
        data2sheet.doPost(payload)
    except Exception as e:
        print(f"❌ 儲存失敗 ({sheet_name}): {e}")    
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
            
            print(f"✅ 主題已切換至: {topic}")
            return jsonify({"status": "success", "message": f"Topic set to {topic}"})
        
        return jsonify({"error": "No topic provided"}), 400
    except Exception as e:
        print(f"❌ 切換主題失敗: {e}")
        return jsonify({"error": str(e)}), 500
    

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=False)
