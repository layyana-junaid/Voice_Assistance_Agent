import os
from functools import lru_cache
from typing import Optional, Literal

from pydantic import BaseModel

from dotenv import load_dotenv
load_dotenv() 

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser


# ---------------------------
# 1) NLU (structured extraction)
# ---------------------------
class NLU(BaseModel):
    intent: Literal["bills", "topups", "fraud", "card", "unknown"] = "unknown"
    biller: Optional[Literal["Electricity", "Internet", "Gas", "Mobile"]] = None
    amount: Optional[int] = None
    emotion: Optional[Literal["stressed", "neutral", "happy"]] = "neutral"


@lru_cache(maxsize=1)
def _llm() -> ChatGroq:
    """
    Cached LLM client.
    Raises RuntimeError if GROQ_API_KEY is missing.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY missing (not loaded from env/.env).")

    return ChatGroq(
        groq_api_key=api_key,
        model=os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile"),
        temperature=0.7,
    )


def extract_nlu(user_text: str) -> NLU:
    """
    Uses LLM to extract intent/biller/amount/emotion from speech.
    If LLM isn't available, returns unknown.
    """
    try:
        parser = PydanticOutputParser(pydantic_object=NLU)

        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are an NLU extractor for a banking voice assistant. "
             "Return ONLY structured fields. Be robust to speech errors. "
             "If user asks how/where/what, infer intent based on topic. "
             "If unsure, use intent='unknown'."),
            ("user",
             "User text:\n{user_text}\n\n{format_instructions}")
        ])

        chain = prompt | _llm() | parser
        return chain.invoke({
            "user_text": user_text,
            "format_instructions": parser.get_format_instructions()
        })
    except Exception:
        # Safe fallback (never crash websocket)
        return NLU(intent="unknown", biller=None, amount=None, emotion="neutral")


# ---------------------------
# 2) Natural response generator
# ---------------------------
class TalkInput(BaseModel):
    user_text: str
    mode: str
    step: str
    missing: Optional[str] = None
    biller: Optional[str] = None
    amount: Optional[str] = None
    last_assistant: Optional[str] = None
    emotion: Optional[str] = "neutral"


def _fallback_coaching(inp: TalkInput) -> str:
    # Minimal, non-robotic fallback if LLM isn't available.
    if inp.emotion == "stressed":
        if inp.missing == "click_bill_tile":
            return "No worries — tap Bill Payment and I’ll walk you through it."
        if inp.missing == "biller":
            return "It’s okay. Which bill is it — electricity, internet, gas, or mobile?"
        if inp.missing == "amount":
            return "Got it. Tell me the amount you want to pay."
        if inp.missing == "continue":
            return "Perfect — tap Continue to review the payment."
        if inp.missing == "confirm":
            return "All set — tap Pay Now to complete it."
        return "I’m here with you. Tell me what you want to do next."

    # neutral/happy
    if inp.missing == "click_bill_tile":
        return "Tap Bill Payment and we’ll start."
    if inp.missing == "biller":
        return "Which bill type is it — electricity, internet, gas, or mobile?"
    if inp.missing == "amount":
        return "What amount would you like to pay?"
    if inp.missing == "continue":
        return "Great — tap Continue."
    if inp.missing == "confirm":
        return "Nice — tap Pay Now to confirm."
    return "Okay — what would you like to do?"


def generate_coaching_text(inp: TalkInput) -> str:
    """
    Makes the assistant sound human + avoids repeating the same line.
    Never crashes if GROQ key isn't loaded.
    """
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are JS Bank’s in-app voice assistant.\n"
             "Style: warm, natural, concise. Avoid repeating yourself.\n"
             "Never mention code, files, backend, websocket, selectors, or 'modal'.\n"
             "Guide step-by-step like a helpful bank representative.\n"
             "If emotion is stressed, be reassuring.\n"
             "Keep replies 1–2 short sentences.\n"),
            ("user",
             "Context:\n"
             "- mode={mode}\n"
             "- step={step}\n"
             "- missing={missing}\n"
             "- biller={biller}\n"
             "- amount={amount}\n"
             "- last_assistant={last_assistant}\n"
             "- emotion={emotion}\n\n"
             "User said: {user_text}\n\n"
             "Reply with what you will speak now (1–2 sentences).")
        ])

        chain = prompt | _llm()
        out = chain.invoke({
            "user_text": inp.user_text,
            "mode": inp.mode,
            "step": inp.step,
            "missing": inp.missing,
            "biller": inp.biller,
            "amount": inp.amount,
            "last_assistant": inp.last_assistant,
            "emotion": inp.emotion
        })
        text = (out.content or "").strip()

        # Extra safety: if model returns empty
        return text if text else _fallback_coaching(inp)

    except Exception:
        return _fallback_coaching(inp)
