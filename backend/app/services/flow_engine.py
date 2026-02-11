from typing import Dict, Any, Optional
from app.schemas import AgentResponse, UIAction
from app.services.langchain_agent import extract_nlu, generate_coaching_text, TalkInput

SESSION: Dict[str, Dict[str, Any]] = {}

def _state(session_id: str) -> Dict[str, Any]:
    if session_id not in SESSION:
        SESSION[session_id] = {
            "mode": None,
            "step": "start",
            "biller": None,
            "amount": None,
            "last_assistant": None,
            "emotion": "neutral",
            "expected_click": None,   # <- key improvement
            "asked": set(),           # <- prevent repeated questions
        }
    return SESSION[session_id]

def _clicked_target(text: str) -> Optional[str]:
    if text.startswith("__clicked__:"):
        return text.split(":", 1)[1]
    return None

def _speak(st: Dict[str, Any], user_text: str, missing: Optional[str] = None) -> UIAction:
    msg = generate_coaching_text(TalkInput(
        user_text=user_text,
        mode=st.get("mode") or "unknown",
        step=st.get("step") or "unknown",
        missing=missing,
        biller=st.get("biller"),
        amount=str(st.get("amount")) if st.get("amount") else None,
        last_assistant=st.get("last_assistant"),
        emotion=st.get("emotion") or "neutral",
    ))
    st["last_assistant"] = msg
    return UIAction(type="agent_message", text=msg)

def _coach_click(st: Dict[str, Any], selector: str, user_text: str, missing: str) -> AgentResponse:
    """
    Force step-by-step guidance:
    - highlight
    - tell user
    - wait_for_click
    """
    st["expected_click"] = selector
    return AgentResponse(actions=[
        UIAction(type="highlight", target=selector),
        _speak(st, user_text, missing=missing),
        UIAction(type="wait_for_click", target=selector),
    ])

def handle_turn(session_id: str, text: str, user_name: str = "Layyana") -> AgentResponse:
    st = _state(session_id)
    t = (text or "").strip()
    clicked = _clicked_target(t)

    # reset
    if t.lower() in {"reset", "restart", "start over"}:
        SESSION[session_id] = {
            "mode": None,
            "step": "start",
            "biller": None,
            "amount": None,
            "last_assistant": None,
            "emotion": "neutral",
            "expected_click": None,
            "asked": set(),
        }
        st = _state(session_id)
        return AgentResponse(actions=[
            UIAction(type="agent_message", text=f"Reset done. What would you like to do, {user_name}?"),
            UIAction(type="highlight", target="#tileBills"),
        ])

    # If we are waiting for a click and user speaks instead -> re-coach
    if st.get("expected_click") and not clicked:
        # Still allow slot filling by voice while waiting
        nlu = extract_nlu(t) if t else None
        if nlu:
            st["emotion"] = nlu.emotion or "neutral"
            if nlu.biller: st["biller"] = nlu.biller
            if nlu.amount: st["amount"] = nlu.amount

        return _coach_click(
            st,
            st["expected_click"],
            user_text=t or "Okay",
            missing="click_to_continue",
        )

    # Handle click events
    if clicked:
        # clear expectation (only if it matches expected)
        if st.get("expected_click") == clicked:
            st["expected_click"] = None

        # tile click -> bills flow start
        if clicked == "#tileBills":
            st["mode"] = "bills"
            st["step"] = "bills_open"
            st["asked"].discard("biller")
            st["asked"].discard("amount")
            return AgentResponse(actions=[
                UIAction(type="open_modal", target="#billModal"),
                UIAction(type="highlight", target="#billerSelect"),
                _speak(st, "User opened bill payment.", missing="biller"),
            ])

        if clicked == "#continueBillBtn":
            st["step"] = "bills_confirm"
            return AgentResponse(actions=[
                UIAction(type="open_modal", target="#confirmModal"),
                UIAction(type="highlight", target="#confirmPayBtn"),
                _speak(st, "User is reviewing payment.", missing="confirm"),
                UIAction(type="wait_for_click", target="#confirmPayBtn"),
            ])

        if clicked == "#confirmPayBtn":
            st["step"] = "done"
            return AgentResponse(actions=[
                _speak(st, "Payment completed."),
                UIAction(type="toast", text="Payment completed"),
                UIAction(type="close_modal", target="#confirmModal"),
                UIAction(type="close_modal", target="#billModal"),
            ])

        # other tiles (optional)
        if clicked in {"#tileTopups", "#tileFraud", "#tileCard"}:
            return AgentResponse(actions=[
                _speak(st, "User selected another option."),
                UIAction(type="toast", text="Demo tip: try Bill Payment"),
                UIAction(type="highlight", target="#tileBills"),
            ])

    # NLU parse for normal speech
    if t:
        nlu = extract_nlu(t)
        st["emotion"] = nlu.emotion or "neutral"
        if nlu.biller: st["biller"] = nlu.biller
        if nlu.amount: st["amount"] = nlu.amount

        # route mode if not set
        if not st["mode"] and nlu.intent != "unknown":
            st["mode"] = nlu.intent
            st["step"] = "await_tile_click"

    # If no mode, push user to click bills (demo path)
    if not st["mode"] or st["mode"] == "unknown":
        st["mode"] = "bills"  # steer demo toward bills
        st["step"] = "await_tile_click"
        return _coach_click(st, "#tileBills", t or "Hello", "click_bill_tile")

    # ===== Bills mode =====
    if st["mode"] == "bills":
        # Step: must click tile first
        if st["step"] == "await_tile_click":
            return _coach_click(st, "#tileBills", t or "Start bill payment", "click_bill_tile")

        # Ensure modal is open and biller selected
        if st["step"] in {"bills_open", "choose_biller"}:
            st["step"] = "choose_biller"

            if not st.get("biller"):
                # ask once, then keep highlighting instead of repeating
                if "biller" not in st["asked"]:
                    st["asked"].add("biller")
                    return AgentResponse(actions=[
                        UIAction(type="open_modal", target="#billModal"),
                        UIAction(type="highlight", target="#billerSelect"),
                        _speak(st, t, missing="biller"),
                    ])
                return AgentResponse(actions=[
                    UIAction(type="open_modal", target="#billModal"),
                    UIAction(type="highlight", target="#billerSelect"),
                    UIAction(type="toast", text="Say: electricity / internet / gas / mobile"),
                ])

            # biller exists -> amount
            st["step"] = "enter_amount"
            return AgentResponse(actions=[
                UIAction(type="open_modal", target="#billModal"),
                UIAction(type="set_field", target="#billerSelect", value=st["biller"]),
                UIAction(type="highlight", target="#amountInput"),
                _speak(st, t, missing="amount"),
            ])

        # Amount
        if st["step"] == "enter_amount":
            if not st.get("amount"):
                if "amount" not in st["asked"]:
                    st["asked"].add("amount")
                    return AgentResponse(actions=[
                        UIAction(type="highlight", target="#amountInput"),
                        _speak(st, t, missing="amount"),
                    ])
                return AgentResponse(actions=[
                    UIAction(type="highlight", target="#amountInput"),
                    UIAction(type="toast", text="Say an amount like: 5000"),
                ])

            # amount exists -> must click continue
            st["step"] = "await_continue_click"
            return _coach_click(st, "#continueBillBtn", t, "continue")

        # Continue click enforcement
        if st["step"] == "await_continue_click":
            return _coach_click(st, "#continueBillBtn", t, "continue")

        # Confirm click enforcement
        if st["step"] == "bills_confirm":
            return _coach_click(st, "#confirmPayBtn", t, "confirm")

    return AgentResponse(actions=[_speak(st, t or "Okay")])
