from typing import Optional

from pydantic import BaseModel


class PlantUMLRenderRequest(BaseModel):
    code: str
    timeout_s: Optional[float] = None
