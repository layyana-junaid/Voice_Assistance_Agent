const user = { name: "Layyana Junaid", balance: 128450 };
const FEE = 30;

const statusEl = document.getElementById("status");
const micBtn = document.getElementById("micBtn");
const micLabel = document.getElementById("micLabel");
const toastEl = document.getElementById("toast");

const userName = document.getElementById("userName");
const balanceText = document.getElementById("balanceText");

const tileBills = document.getElementById("tileBills");
const tileTopups = document.getElementById("tileTopups");
const tileFraud = document.getElementById("tileFraud");
const tileCard = document.getElementById("tileCard");

const quickHintBtn = document.getElementById("quickHintBtn");

const closeBillModalBtn = document.getElementById("closeBillModalBtn");
const billerSelect = document.getElementById("billerSelect");
const amountInput = document.getElementById("amountInput");
const continueBillBtn = document.getElementById("continueBillBtn");

const closeConfirmModalBtn = document.getElementById("closeConfirmModalBtn");
const cancelPayBtn = document.getElementById("cancelPayBtn");
const confirmPayBtn = document.getElementById("confirmPayBtn");
const confirmBiller = document.getElementById("confirmBiller");
const confirmAmount = document.getElementById("confirmAmount");
const confirmFee = document.getElementById("confirmFee");

const closeInfoModalBtn = document.getElementById("closeInfoModalBtn");
const infoOkBtn = document.getElementById("infoOkBtn");

const confettiCanvas = document.getElementById("confetti");
const ctx = confettiCanvas.getContext("2d");

let ws;
let waitingForClick = null;

// ---------------- Render ----------------
function renderUser() {
  userName.textContent = user.name;
  balanceText.textContent = `Rs ${user.balance.toLocaleString("en-PK")}`;
}
renderUser();

// ---------------- Toast ----------------
function showToast(text) {
  toastEl.textContent = text;
  toastEl.classList.add("show");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toastEl.classList.remove("show"), 2400);
}

// ---------------- Modals ----------------
function openModal(selector) {
  const el = document.querySelector(selector);
  if (!el) return;
  el.classList.add("open");
  el.setAttribute("aria-hidden", "false");
}
function closeModal(selector) {
  const el = document.querySelector(selector);
  if (!el) return;
  el.classList.remove("open");
  el.setAttribute("aria-hidden", "true");
}

// ---------------- UI helpers ----------------
function highlight(selector) {
  const el = document.querySelector(selector);
  if (!el) return;
  el.classList.add("highlight");
  setTimeout(() => el.classList.remove("highlight"), 2200);
}

function setField(selector, value) {
  const el = document.querySelector(selector);
  if (!el) return;
  if (el.tagName === "SELECT") {
    const found = [...el.options].find(o => o.value.toLowerCase() === String(value).toLowerCase());
    if (found) el.value = found.value;
  } else {
    el.value = value;
  }
  highlight(selector);
}

// ---------------- WS ----------------
function connectWS() {
  const WS_URL = `${location.protocol === "https:" ? "wss" : "ws"}://${location.hostname}:8000/ws`;
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    statusEl.textContent = "Connected";
    showToast("Assistant ready. Press the microphone to talk.");
    speak("Hi. Press the microphone and tell me what you want to do.");
  };

  ws.onclose = () => {
    statusEl.textContent = "Disconnected";
    setTimeout(connectWS, 900);
  };

  ws.onmessage = (event) => {
    let msg;
    try { msg = JSON.parse(event.data); } catch { return; }

    if (msg.type === "agent_message") {
      showToast(msg.text);
      speak(msg.text);
      return;
    }
    if (msg.type === "toast") { showToast(msg.text || "Done"); return; }
    if (msg.type === "highlight") { highlight(msg.target); return; }
    if (msg.type === "open_modal") { openModal(msg.target); return; }
    if (msg.type === "close_modal") { closeModal(msg.target); return; }
    if (msg.type === "set_field") { setField(msg.target, msg.value); return; }
    if (msg.type === "wait_for_click") { setWaitForClick(msg.target); return; }
  };
}

function sendUserText(text) {
  if (!text?.trim()) return;
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "user_message", text }));
  } else {
    showToast("Reconnecting. Try again.");
  }
}

function sendClickEvent(selector) {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "ui_event", event: "clicked", target: selector }));
  }
}

// ---------------- Coach wait-for-click ----------------
function setWaitForClick(selector) {
  waitingForClick = selector;
  highlight(selector);
  showToast("Click the highlighted element to continue.");
}

document.addEventListener("click", (e) => {
  if (!waitingForClick) return;
  const match = e.target.closest(waitingForClick);
  if (!match) return;
  const target = waitingForClick;
  waitingForClick = null;
  sendClickEvent(target);
});

// Tile clicks
tileBills.addEventListener("click", () => sendClickEvent("#tileBills"));
tileTopups.addEventListener("click", () => sendClickEvent("#tileTopups"));
tileFraud.addEventListener("click", () => sendClickEvent("#tileFraud"));
tileCard.addEventListener("click", () => sendClickEvent("#tileCard"));

// Help
quickHintBtn.addEventListener("click", () => openModal("#infoModal"));
closeInfoModalBtn.addEventListener("click", () => closeModal("#infoModal"));
infoOkBtn.addEventListener("click", () => closeModal("#infoModal"));

// Bills modal
closeBillModalBtn.addEventListener("click", () => closeModal("#billModal"));

continueBillBtn.addEventListener("click", () => {
  const biller = billerSelect.value;
  const amount = amountInput.value;

  confirmBiller.textContent = biller || "—";
  confirmAmount.textContent = amount ? `Rs ${Number(amount).toLocaleString("en-PK")}` : "—";
  confirmFee.textContent = `Rs ${FEE}`;

  openModal("#confirmModal");
  sendClickEvent("#continueBillBtn");
});

closeConfirmModalBtn.addEventListener("click", () => closeModal("#confirmModal"));
cancelPayBtn.addEventListener("click", () => closeModal("#confirmModal"));

confirmPayBtn.addEventListener("click", () => {
  const amt = Number(amountInput.value || 0);
  const total = amt + FEE;

  if (amt <= 0) { showToast("Enter a valid amount."); speak("Please enter a valid amount."); return; }
  if (total > user.balance) { showToast("Insufficient balance."); speak("Insufficient balance."); return; }

  user.balance = Math.max(0, user.balance - total);
  renderUser();

  closeModal("#confirmModal");
  closeModal("#billModal");

  burstConfetti();
  showToast(`Payment successful. Deducted Rs ${total.toLocaleString("en-PK")}`);
  speak("Payment successful.");
  sendClickEvent("#confirmPayBtn");
});

// ---------------- Voice: toggle ----------------
let recognition = null;
let isListening = false;

function setupVoice() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    showToast("Voice is not supported in this browser. Use Chrome or Edge.");
    micBtn.disabled = true;
    return;
  }

  recognition = new SR();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onresult = (event) => {
    const transcript = event.results?.[0]?.[0]?.transcript || "";
    if (transcript.trim()) sendUserText(transcript);
    try { recognition.stop(); } catch {}
  };

  recognition.onend = () => {
    isListening = false;
    micBtn.classList.remove("listening");
    micLabel.classList.remove("show");
  };

  recognition.onerror = () => {
    isListening = false;
    micBtn.classList.remove("listening");
    micLabel.classList.remove("show");
    showToast("Microphone error. Try again.");
  };

  micBtn.addEventListener("click", () => {
    if (!recognition) return;

    if (!isListening) {
      isListening = true;
      micBtn.classList.add("listening");
      micLabel.classList.add("show");
      micLabel.textContent = "Listening";
      showToast("Listening.");
      try { recognition.start(); } catch {}
    } else {
      isListening = false;
      micBtn.classList.remove("listening");
      micLabel.classList.remove("show");
      showToast("Stopped.");
      try { recognition.stop(); } catch {}
    }
  });
}

// ---------------- TTS ----------------
function speak(text) {
  try {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();

    const u = new SpeechSynthesisUtterance(text);

    const voices = window.speechSynthesis.getVoices();
    const preferred =
      voices.find(v => /Google UK English Female/i.test(v.name)) ||
      voices.find(v => /Google US English/i.test(v.name)) ||
      voices.find(v => (v.lang || "").startsWith("en"));
    if (preferred) u.voice = preferred;

    u.rate = 0.98 + Math.random() * 0.08;
    u.pitch = 0.95 + Math.random() * 0.10;

    window.speechSynthesis.speak(u);
  } catch {}
}
window.speechSynthesis.onvoiceschanged = () => {};

// ---------------- Confetti ----------------
function resizeCanvas() {
  confettiCanvas.width = window.innerWidth;
  confettiCanvas.height = window.innerHeight;
}
window.addEventListener("resize", resizeCanvas);
resizeCanvas();

function burstConfetti() {
  const pieces = Array.from({ length: 70 }).map(() => ({
    x: window.innerWidth / 2,
    y: window.innerHeight / 3,
    vx: (Math.random() - 0.5) * 10,
    vy: (Math.random() - 1.2) * 10,
    g: 0.25 + Math.random() * 0.25,
    r: 2 + Math.random() * 3,
    life: 70 + Math.random() * 30
  }));

  let frame = 0;
  function tick() {
    frame++;
    ctx.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);
    pieces.forEach(p => {
      p.x += p.vx; p.y += p.vy; p.vy += p.g; p.life -= 1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
    });
    if (frame < 85) requestAnimationFrame(tick);
    else ctx.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);
  }
  tick();
}

// init
setupVoice();
connectWS();
setTimeout(() => sendUserText("hello"), 600);
