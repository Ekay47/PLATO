from pydantic import BaseModel


class RunCreateRequest(BaseModel):
    requirement_text: str
    diagram_type: str = "activity"
