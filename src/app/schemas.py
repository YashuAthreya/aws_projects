# app/auth/schemas.py

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    mobile: str
    password: str = Field(
        min_length=4,
        max_length=128,
    )


class LoginRequest(BaseModel):
    email: EmailStr

    password: str = Field(
        min_length=1,
        max_length=128,
    )


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    user_name: str | None = None
    user_email: str | None = None
    is_active: bool | None = None
