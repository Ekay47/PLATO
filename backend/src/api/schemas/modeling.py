from pydantic import BaseModel


class ModelingRequest(BaseModel):
    requirement_text: str
    diagram_type: str = "activity"
