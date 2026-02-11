import asyncio
from fastapi import WebSocket

async def run_bill_help_flow(ws: WebSocket):
    # 1) agent message
    await ws.send_json({
        "type": "agent_message",
        "text": "No worries — I’ll guide you. First, click the “Pay Bills” button. I’m highlighting it now."
    })

    # 2) highlight a button
    await ws.send_json({
        "type": "highlight",
        "target": "#payBillsBtn"
    })

    await asyncio.sleep(1.0)

    # 3) open a modal
    await ws.send_json({
        "type": "open_modal",
        "target": "#billModal"
    })

    await ws.send_json({
        "type": "agent_message",
        "text": "Great. Now select your biller and enter the amount. If you want, tell me the bill type (electric/internet/etc)."
    })
