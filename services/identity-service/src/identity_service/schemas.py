from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from teampulse_common.security import Role
from teampulse_common.validation import forbid_null

_PASSWORD_RULE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,72}$")
# bcrypt only uses the first 72 bytes of a password, and bcrypt 5 raises an error for longer input.
# Letters and digits are 1 byte each; some other characters (such as é or emoji) take 2-4 bytes.
BCRYPT_MAX_BYTES = 72


def _check_password(value: str) -> str:
    if not _PASSWORD_RULE.match(value) or len(value.encode()) > BCRYPT_MAX_BYTES:
        raise ValueError(
            "Password must be 8-72 characters (at most 72 bytes) and include upper-case, "
            "lower-case and a digit"
        )
    return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    team_id: uuid.UUID | None
    team_name: str | None = None
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class MeUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str

    _validate = field_validator("new_password")(_check_password)


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str
    role: Role = Role.EMPLOYEE
    team_id: uuid.UUID | None = None

    _validate = field_validator("password")(_check_password)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    role: Role | None = None
    team_id: uuid.UUID | None = Field(default=None, description="null = remove the user from their team")
    is_active: bool | None = None

    _no_nulls = forbid_null("full_name", "role", "is_active")


class TeamOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    manager_id: uuid.UUID | None
    manager_name: str | None
    member_count: int


class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    manager_id: uuid.UUID | None = None


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    manager_id: uuid.UUID | None = Field(default=None, description="null = the team has no manager")

    _no_nulls = forbid_null("name")


class MemberOut(BaseModel):
    id: uuid.UUID
    full_name: str
    role: Role
