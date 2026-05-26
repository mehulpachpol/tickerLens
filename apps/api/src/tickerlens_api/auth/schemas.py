from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    user_id: str
    email: str
    role: str
    is_active: bool
    created_at: dt.datetime


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)


class LoginResponse(BaseModel):
    user: UserOut


class MeResponse(BaseModel):
    user: UserOut

