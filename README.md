# EnglishAgent：Master-Sub Agent + Chroma RAG 英語學習助教系統

本專案建構了一套智慧英語學習平台，採用 **Master-Sub Agent（主從智能體）** 架構結合 **Chain of Thought (CoT)** 思維鏈技術。系統透過 Master Agent 進行意圖識別與任務分派，並結合 **Chroma 向量資料庫（RAG 技術）** 檢索國中教材，提供精準的教學、出題與翻譯服務。

## 目錄 Table of Contents

- [專案簡介](#englishagentmaster-sub-agent--chroma-rag-英語學習助教系統)
- [核心功能與特色](#核心功能與特色)
- [系統架構與 Master Agent 機制](#系統架構與-master-agent-機制)
- [文獻探討](#文獻探討)
- [資料儲存機制 (Google Sheets)](#資料儲存機制-google-sheets)
- [技術堆疊](#技術堆疊)
- [未來展望 (Roadmap)](#未來展望-roadmap)
- [出處](#出處)

---

## 核心功能與特色

### 🧠 Master Agent 智慧分派
引入 **母智能體 (Master Agent)** 作為中樞大腦，負責：
1.  **意圖識別**：分析使用者輸入，判斷需求屬於「教學」、「出題」還是「翻譯」。
2.  **CoT 思維鏈**：在分派任務前進行推理解析，確保任務傳遞給正確的子 Agent。
3.  **任務調度**：動態喚醒對應的 Sub-Agent (Teaching / Question / Answer)。

### 🗣️ CoT 多輪對話記憶
- **上下文感知**：系統具備 **3 輪對話紀錄 (Context Window)** 的短期記憶能力。
- **連續性互動**：使用者可以進行追問（例如：先問單字定義，接著追問例句，再要求出題），Agent 能理解上下文關聯，不會將每句話視為獨立事件。

### 📚 RAG 國中教材檢索
- **專屬知識庫**：透過 ChromaDB 檢索國中英語教材。
- **課綱對應**：生成的教學內容與題目嚴格貼合國中課綱範圍，避免產生超綱或不適用的內容。

---

## 系統架構與 Master Agent 機制


### 運作流程：
1.  **使用者輸入**：學生提出問題（例如：「請幫我解釋現在完成式並出題」）。
2.  **Master Agent (母智能體) 分析**：
    -   讀取最近 3 輪對話紀錄 (Memory)。
    -   執行 CoT 推理：「使用者想學習文法並練習，應優先調用教學 Agent，隨後可引導至出題 Agent。」
    -   決定啟動哪個 Sub-Agent。
3.  **Sub-Agent (子智能體) 執行**：
    -   **Teaching Agent**：檢索 RAG 教材，生成文法解說。
    -   **Question Agent**：根據該文法點生成選擇題。
    -   **Answer Agent**：處理過去問題的解答。
4.  **Response**：整合結果回傳給使用者，並更新對話記憶。

---

## 資料儲存機制 (Google Sheets)

系統將所有互動數據即時寫入 **Google Sheets**，欄位設計經過優化以符合教學追蹤需求。

### 資料表欄位結構 (Schema)：
| 欄位名稱 | 說明 | 範例 |
| :--- | :--- | :--- |
| **id** | 流水號 | `1` |
| **student** | 學生姓名或代號 | `Student_A` |
| **category** | 任務分類 (由 Master Agent 判斷) | `Grammar_Teaching` |
| **Topic** | 學習主題/關鍵字 | `Present Perfect Tense` |
| **User Input** | 使用者完整的提問內容 | `什麼是現在完成式？請給我例句` |
| **Agent Output** | 系統生成的完整回應 | `現在完成式表示過去發生但影響至今...` |
| **Timestamp** | 紀錄時間 | `2025-12-07 10:30:00` |

---

## 技術堆疊

| 類別 | 工具 / 技術 | 說明 |
| :--- | :--- | :--- |
| **Backend** | **Python Flask** | 處理路由、Session 與 Agent 調度邏輯 |
| **Agent Core** | **Master-Sub Architecture** | 自研主從式 Agent 協作框架 |
| **Memory** | **Sliding Window Buffer** | 實作 3 輪對話的 Context 記憶 |
| **LLM** | **OpenAI GPT-4o** | 支援 CoT 推理與內容生成 |
| **Vector DB** | **ChromaDB** | 儲存國中教材向量數據 (RAG) |
| **Database** | **Google Sheets API** | 學習歷程記錄 (Log) |
| **Data Source** | PDF / JSON | 國中英語教材  |

---

## 文獻探討

### AI 在英語教育中的應用潛力
- 教師端方面，AI 可協助備課與回饋回應的自動化，大幅降低教學工作負擔。
- 學習者端方面，AI 增強了學習動機、參與度與學習表現。

> *Koç, F. Ş., & Savaş, P. (2024). The use of artificially intelligent chatbots in English language learning...*

### AI Agents 在教育領域的發展潛力
- 結合「記憶模組」與「規劃模組」的 Agent 系統能即時追蹤學習進展。
- 本專案採用的 **Master-Slave 多智能體架構** 能有效解決單一模型在處理複雜教學任務時的錯亂問題。

> *Chu, Z., et al. (2025). LLM agents for education: Advances and applications.*

---

## 未來展望 (Roadmap)

   -   新增口說評測 Agent (Speech-to-Text)。
   -   導入學習歷程分析儀表板 (Dashboard)。

## 出處

此內容原作者來自於[Github](https://github.com/a88019401/ai_agents_homework_from-my-teammates)