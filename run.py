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
gas_url = "https://script.google.com/macros/s/AKfycbx-Ca5biY12JxXfL2SEJvdieknqChjUxdZ4c5OtOp0a2phNm62edD7m6wH_ogYNFlHsqQ/exec"
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
    # student_id = request.args.get("studentId")
    payload = request.json
    
    res = requests.post(gas_url, json=payload)
    student_id = payload.get("data")
    history_data = res.json()
    #處理不含歷史紀錄的開頭
    if(history_data == "True"):
        agent_answer_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "你是一個英文助理專注於提供英文的相關知識，用來幫助老師進行出題、解題以及製作教材。提供老師建議關於出題、解題的方向。禁止提到與其他學科相關的內容。"},
                {"role": "user", "content": student_id}
            ]
        )
        agent_answer = agent_answer_response.choices[0].message.content
        print(f"[Agent1 Answer] {agent_answer}...")
        return jsonify({
            "assistant_answer": agent_answer
        })
    #處理含有歷史紀錄的開頭
    else:
        content_str = f"""
            學生姓名：{student_id}
            歷史資料：
            {json.dumps(history_data, ensure_ascii=False, indent=2)} """
        agent_answer_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "你是一個英文助理，用來幫助老師進行出題、解題以及製作教材,user的content中具有老師名字及歷史資料。請根據以上資料為老師提供過去知識以及建議學習方向的摘要。文字簡短較佳且資料越後面代表資料越新需較為重視"},
                {"role": "user", "content": content_str}
            ]
        )
        agent_answer = agent_answer_response.choices[0].message.content
        print(f"[Agent0 Answer] {agent_answer}...")
        return jsonify({
            "assistant_answer": agent_answer
        })
    

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

    # RAG 處理
    manual_context = search_manual_chunks(user_prompt)  # 教材
    question_context = search_question_bank(user_prompt) # 練習題

    if not manual_context:
        manual_context = "⚠️ 找不到教材資料"
    if not question_context:
        question_context = "⚠️ 找不到題庫資料"

    last_questions = session.get("last_practice_questions", "（目前尚無歷史題目）")

    # ✅ 模式為解題解析
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
        print(f"[Agent1+3 Answer] {agent_answer}...")
        session["current_mode"] = None

        payload = {"sheetName":"student_data",
                    "action": "add", 
                    "data":[{"student":id_value,
                            "category": "answer", "user": user_prompt, 
                            "agent":agent_answer}]}
        data2sheet.doPost(payload)

        return jsonify({
            "question": user_prompt,
            "assistant_answer": agent_answer,
            "practice_questions": "(上一題練習題，未重複提供)"
        })

    ## 回顧  應該要用agent 但我小懶
    keywords = ["回顧", "歷史", "紀錄", "學習紀錄", "練習回顧"]
    if any(kw in user_prompt for kw in keywords):
        payload = {"sheetName":"student_data",
                "action": "fetch", 
                "data":id_value}
        history_data = data2sheet.doPost(payload)
        content_str = f"""
            學生姓名：{id_value}
            歷史資料：{history_data} """
        # print(content_str)

        
        agent_answer_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "你是一個英文助理只專注於提供英文的相關知識並以中文進行回答，用來幫助老師進行出題、解題以及製作教材,user的content中具有歷史資料。請根據以上資料為老師提供過去知識以及建議學習方向的摘要。文字簡短較佳且資料越後面代表資料越新需較為重視"},
                {"role": "user", "content": content_str}
            ]
        )
        agent_answer = agent_answer_response.choices[0].message.content
        print(f"[Agent0 Answer] {agent_answer}...")
        return jsonify({
            "history": agent_answer
        })

    # ✅ 正常出題流程
    ## 教材
    agent1_prompt = format_agent1_prompt(user_prompt, manual_context,  last_questions)
    agent1_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "你是英文助教，要協助台灣國中的英文老師，僅嚴格的【教材內容】內的內容，提供教師要求的文法筆記或上課內容講義。絕對不能脫離【教材內容】的內容需簡潔、符合國中程度"},
            {"role": "user", "content": agent1_prompt}
        ]
    )
    agent1_answer = agent1_response.choices[0].message.content
    print(f"[Agent1 Explanation] {agent1_answer}...")

    payload = {"sheetName":"student_data",
                "action": "add", 
                "data":[{"student":id_value,
                        "category": "lesson", "user": user_prompt, 
                        "agent": agent1_answer}]}
    data2sheet.doPost(payload)

    ## 出題
    agent2_prompt = format_agent2_prompt(user_prompt,  question_context)
    agent2_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "你是英文測驗題目設計老師，要協助台灣國中的英文老師。根據嚴格的依照【題庫內容】篩選5題英文單選題（a/b/c/d），不得超出主題。只提供題目，不提供答案。"},
            {"role": "user", "content": agent2_prompt}
        ]
    )
    agent2_answer = agent2_response.choices[0].message.content
    print(f"[Agent2 Questions] {agent2_answer}...")

    payload = {"sheetName":"student_data",
                "action": "add", 
                "data":[{"student":id_value,
                        "category": "question", "user": user_prompt, 
                        "agent": agent2_answer}]}
    data2sheet.doPost(payload)

    session["last_practice_questions"] = agent2_answer
    session["last_topic"] = user_prompt
    session["current_mode"] = "waiting_for_answer"

    return jsonify({
        "question": user_prompt,
        "assistant_answer": agent1_answer,
        "practice_questions": agent2_answer
    })

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=False)
