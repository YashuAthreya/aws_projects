# app/admin/schemas.py

from pydantic import BaseModel, ConfigDict, Field


class AdminLoginRequest(BaseModel):
    admin_name: str
    admin_password: str = Field(
        min_length=1,
        max_length=128,
    )


class AdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    admin_id: int
    admin_name: str | None = None
