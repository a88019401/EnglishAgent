// static/js/script.js

const params = new URLSearchParams(window.location.search);

const studentId = params.get("studentId");
const data = JSON.parse(sessionStorage.getItem("loginData"));
if (studentId && data) {
  fetchStudentHistory(studentId);
}
else {
  window.location.href = `/`;
}

async function fetchStudentHistory(studentId) {

  const chatBox = document.getElementById("chatBox");
  // 顯示思考中
  const thinkingId = `thinking-${Date.now()}`;
  chatBox.innerHTML += `<div class="bot" id="${thinkingId}">讀取過往資料...</div>`;


  try {
    const res = await fetch(`/fetchHistoryData`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sheetName: "student_data",
        action: "fetch",
        data: studentId
      })
    });

    const rawText = await res.text(); 
    const data = JSON.parse(rawText); // 轉成物件
    
    if (data.error) {
      console.log("錯誤訊息：", data.error);
    } else {
      const thinkingDiv = document.getElementById(thinkingId);
      thinkingDiv.innerHTML = `
        ${escapeHtml(data.assistant_answer).replaceAll("\n","<br>")}`;
    }
  } catch (error) {
    console.error("例外錯誤：", error);
  }
}


async function sendMessage() {
  const input = document.getElementById("input");
  const userInput = input.value.trim();
  if (!userInput) return;

  const chatBox = document.getElementById("chatBox");
  chatBox.innerHTML += `<div class="user">🙋‍♂️ ${escapeHtml(userInput)}</div>`;
  input.value = "";

  // 顯示思考中
  const thinkingId = `thinking-${Date.now()}`;
  chatBox.innerHTML += `<div class="bot" id="${thinkingId}">🤖 AI 正在思考中...</div>`;

  try {
    const res = await fetch(`/ask_multiagent_rag?studentId=${encodeURIComponent(studentId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: userInput }),
    });

    const data = await res.json();
    const thinkingDiv = document.getElementById(thinkingId);

    if (data.error) {
      thinkingDiv.innerHTML = `❌ 錯誤：${escapeHtml(data.error)}`;
    } else if (data.assistant_answer && data.practice_questions) {
      thinkingDiv.innerHTML = `
        <b>🎓 助教解答：</b><br>${escapeHtml(data.assistant_answer).replaceAll(
          "\n",
          "<br>"
        )}
        <br><br><b>📋 題目練習：</b><br>${escapeHtml(
          data.practice_questions
        ).replaceAll("\n", "<br>")}
      `;
    } else if(data.history) {
        thinkingDiv.innerHTML=data.history;
    }
      else {
      thinkingDiv.innerHTML = `❓ 無回應`;
    }
  } catch (error) {
    console.error(error);
    const thinkingDiv = document.getElementById(thinkingId);
    thinkingDiv.innerHTML = `❌ 發生錯誤：${escapeHtml(error.message)}`;
  }
}

// 避免 XSS 攻擊
function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
