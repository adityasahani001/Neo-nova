import os
from collections import defaultdict, deque
from flask import Flask, request, jsonify, send_from_directory, abort
from dotenv import load_dotenv

# GOOGLE & DIALOGFLOW
from google.cloud import dialogflow_v2 as dialogflow

# GEMINI
import google.generativeai as genai

# GOOGLE SEARCH
import requests


# ------------------ LOAD ENV ------------------
load_dotenv()

PROJECT_ID = os.getenv("DIALOGFLOW_PROJECT_ID")
GOOGLE_JSON = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
SEARCH_KEY = os.getenv("GOOGLE_SEARCH_KEY")
SEARCH_CX = os.getenv("GOOGLE_SEARCH_CX")

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_JSON
genai.configure(api_key=GEMINI_KEY)


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
FRONTEND_ASSETS = {"index.html", "script.js", "style.css", "N.jpg"}

SESSION_HISTORY_LIMIT = 10
conversation_history = defaultdict(lambda: deque(maxlen=SESSION_HISTORY_LIMIT))

app = Flask(__name__)


@app.get("/")
def serve_index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/<path:filename>")
def serve_static_files(filename):
    if filename in FRONTEND_ASSETS:
        return send_from_directory(BASE_DIR, filename)
    abort(404)


# ------------------ DIALOGFLOW ------------------
def detect_intent(text):
    session_client = dialogflow.SessionsClient()
    session = session_client.session_path(PROJECT_ID, "session-123")

    text_input = dialogflow.TextInput(text=text, language_code="en")
    query_input = dialogflow.QueryInput(text=text_input)

    response = session_client.detect_intent(
        request={"session": session, "query_input": query_input}
    )
    return response.query_result.fulfillment_text


# ------------------ GOOGLE SEARCH ------------------
def google_search(query):
    url = (
        f"https://www.googleapis.com/customsearch/v1?"
        f"key={SEARCH_KEY}&cx={SEARCH_CX}&q={query}"
    )

    data = requests.get(url).json()

    if "items" in data and data["items"]:
        r = data["items"][0]
        return f"🔎 {r['title']}\n{r['snippet']}\n{r['link']}"

    return "No search results found."


def clamp_reply(text, max_words=80):
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def record_interaction(session_id, user_text, reply_text):
    history = conversation_history[session_id]
    history.append({"user": user_text, "bot": reply_text})


def gemini_with_history(query, session_id):
    history = conversation_history[session_id]
    conversation_prompt = "\n".join(
        f"Student: {turn['user']}\nNeo Nova: {turn['bot']}"
        for turn in history
    )

    instruction = (
        "You are Neo Nova, an educational assistant. "
        "Stay strictly on academic topics aligned with school curricula. "
        "Respond conversationally but keep answers under 80 words."
    )

    prompt_parts = [instruction]
    if conversation_prompt:
        prompt_parts.append("Context from previous exchanges:\n" + conversation_prompt)
    prompt_parts.append(f"Student: {query}\nNeo Nova:")

    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content("\n\n".join(prompt_parts))
    return response.text.strip()


def send_reply(session_id, user_query, reply_text):
    concise = clamp_reply(reply_text)
    record_interaction(session_id, user_query, concise)
    return jsonify({"reply": concise})


@app.route("/chat", methods=["POST"])
def chat():
    payload = request.json or {}
    original_query = payload.get("query", "").strip()
    session_id = payload.get("session_id") or request.remote_addr or "session-123"
    query = original_query.lower()

    restricted_keywords = {
        "porn",
        "pornography",
        "nsfw",
        "sex",
        "sexual",
        "xxx",
        "nude",
        "nudity",
        "18+",
        "movie",
        "film",
        "anime",
        "manga",
        "celebrity",
        "gossip",
        "dating",
        "relationship",
        "gaming",
        "casino",
        "bet",
        "gambling",
        "violence",
        "weapon",
    }

    if any(keyword in query for keyword in restricted_keywords):
        return send_reply(
            session_id,
            original_query,
            "⚠️ Educational use only. Please ask curriculum-aligned questions.",
        )

    # Handle date
    if "date" in query or "today" in query:
        from datetime import datetime
        reply = datetime.now().strftime("📅 %A, %d %B %Y")
        return send_reply(session_id, original_query, reply)

    # Handle time
    if "time" in query:
        from datetime import datetime
        reply = datetime.now().strftime("⏰ %I:%M:%S %p")
        return send_reply(session_id, original_query, reply)

    # Real-time keywords → Google search
    rt_words = ["weather", "temperature", "score", "winner", "news"]
    if any(w in query for w in rt_words):
        return send_reply(session_id, original_query, google_search(query))

    # Try Dialogflow first
    try:
        df = detect_intent(query)
        if df.strip():
            return send_reply(session_id, original_query, df)
    except:
        pass

    # Otherwise fallback to Gemini
    reply = gemini_with_history(original_query, session_id)
    return send_reply(session_id, original_query, reply)


if __name__ == "__main__":
    app.run(debug=True)
