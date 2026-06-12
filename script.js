document.addEventListener("DOMContentLoaded", () => {
  const SESSION_STORAGE_KEY = "neoNovaSessionId";
  let sessionId = localStorage.getItem(SESSION_STORAGE_KEY);

  if (!sessionId) {
    if (window.crypto?.randomUUID) {
      sessionId = crypto.randomUUID();
    } else {
      sessionId = `sess-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
    }
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  }

  /* ------------------ HTML ELEMENTS ------------------ */
  const inputField = document.getElementById("user-input");
  const sendButton = document.getElementById("send-button");

  inputField.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendMessage();
  });

  sendButton.addEventListener("click", sendMessage);


  /* ============================================================
     MAIN SEND MESSAGE FUNCTION (uses Flask → /chat)
  ============================================================ */
  async function sendMessage() {
    const userInput = inputField.value.trim();
    if (!userInput) return;

    displayMessage(userInput, "user-message");
    inputField.value = "";

    const thinkingMsg = displayMessage("🤔 Responding...", "bot-message", true);

    try {
      const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userInput, session_id: sessionId })
      });

      const data = await response.json();
      thinkingMsg.remove();
      displayMessage(data.reply, "bot-message");

    } catch (error) {
      thinkingMsg.remove();
      console.error("Backend Error:", error);
      displayMessage("⚠ Error: Backend not responding!", "bot-message");
    }
  }


  /* ============================================================
     DISPLAY MESSAGE IN CHATBOX
  ============================================================ */
  function displayMessage(text, className, returnElement = false) {
    const chatBox = document.getElementById("chat-box");
    const div = document.createElement("div");

    div.className = className;
    div.innerHTML = convertMarkdownToHTML(text);

    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;

    return returnElement ? div : null;
  }


  /* ============================================================
     MARKDOWN → HTML
  ============================================================ */
  function convertMarkdownToHTML(md) {
    return md
      .replace(/^### (.*$)/gim, "<h3>$1</h3>")
      .replace(/^## (.*$)/gim, "<h2>$1</h2>")
      .replace(/^# (.*$)/gim, "<h1>$1</h1>")
      .replace(/\*\*(.*?)\*\*/gim, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/gim, "<em>$1</em>")
      .replace(/`(.*?)`/gim, "<code>$1</code>")
      .replace(/\[([^\]]+)\]\(([^)]+)\)/gim, '<a href="$2" target="_blank">$1</a>')
      .replace(/\n/gim, "<br>");
  }

});
