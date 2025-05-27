# ✅ prompt.py
# 我在agent 1 上面留下了 question_context 來讓講義更完美 他會提供一些題目跟答案提醒學生考點!超棒
def format_agent1_prompt(user_prompt, manual_context, question_context, last_questions=""):
    return f"""教師要求：{user_prompt}

【教材內容】
{manual_context}

【題庫內容】
{question_context}

【歷史題目】
{last_questions}"""

def format_agent2_prompt(user_prompt,  question_context):
    return f"""教師要求：{user_prompt}



題庫內容：{question_context}

"""

def format_answer_explanation_prompt(user_prompt, manual_context, question_context, last_questions, student_answers):
    return f"""教師要求：{user_prompt}

【教材內容】
{manual_context}

【題庫內容】
{question_context}

5題英文題目：
{last_questions}
學生答案：{student_answers}"""
