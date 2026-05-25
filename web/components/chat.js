/*
INSTRUCTIONS:
1. Controls chat behavior.
2. Replace placeholder response with API call later.
*/

const input = document.getElementById("chatInput");
const btn = document.getElementById("sendBtn");
const chatWindow = document.getElementById("chatWindow");

function addMessage(text, isUser = false) {
  const div = document.createElement("div");
  div.className = "chat-message" + (isUser ? " chat-user" : "");
  div.textContent = text;

  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function sendMessage() {
  const msg = input.value.trim();
  if (!msg) return;

  addMessage(msg, true);
  input.value = "";

  // TODO: replace with real API call
  setTimeout(() => {
    addMessage("Agent response...");
  }, 500);
}

btn.addEventListener("click", sendMessage);

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage();
});
