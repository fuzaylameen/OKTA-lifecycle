from pydantic import BaseModel, Field
from typing import List


class BulkUserRequest(BaseModel):
    user_ids: List[str] = Field(..., min_length=1)