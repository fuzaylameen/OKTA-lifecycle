from pydantic import BaseModel
from typing import List

class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: str


class BulkDeactivateRequest(BaseModel):
    user_ids: List[str]