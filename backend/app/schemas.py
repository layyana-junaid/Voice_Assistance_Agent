from typing import List, Optional, Literal
from pydantic import BaseModel, Field

ActionType = Literal[
    "agent_message",
    "highlight",
    "open_modal",
    "close_modal",
    "set_field",
    "toast",
    "wait_for_click",
]

class UIAction(BaseModel):
    type: ActionType
    text: Optional[str] = None
    target: Optional[str] = None
    value: Optional[str] = None

class AgentResponse(BaseModel):
    actions: List[UIAction] = Field(default_factory=list)
