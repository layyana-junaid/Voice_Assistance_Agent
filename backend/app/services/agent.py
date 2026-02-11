import os
from typing import Optional

try:
    from groq import Groq
except Exception:
    Groq = None

SYSTEM = """You are JS Bank’s in-app voice assistant.
Style: warm, human, confident, short sentences.
Vary phrasing naturally. If user is stressed, respond empathetically.
Never mention code, files, backend, selectors, or “modal”.
Be helpful and natural, like a real bank rep.
"""

def llm_text(user_text: str, context: str = "") -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or not Groq:
        # fallback (still avoids “robotic” repeats)
        return "Got it. I can guide you step by step. Tell me what you want to do next."

    client = Groq(api_key=api_key)
    prompt = f"Context: {context}\nUser: {user_text}\nReply:"
    resp = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile"),
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.75,
        max_tokens=140,
    )
    return (resp.choices[0].message.content or "").strip()

def is_question(text: str) -> bool:
    t = (text or "").strip().lower()
    return (
        t.endswith("?")
        or t.startswith(("why", "how", "where", "what", "can you", "could you"))
        or "where can i" in t
        or "how do i" in t
    )
