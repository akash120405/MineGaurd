from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class Inspection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mine: str = Field(min_length=2,max_length=100)
    location: str = Field(min_length=2,max_length=100)
    inspector: str = Field(min_length=2,max_length=100)
    observed_at: str = Field(min_length=10,max_length=40)
    notes: str = Field(min_length=10,max_length=12000)
    methane_pct: float | None = Field(None,ge=0,le=100)
    airflow_m3_s: float | None = Field(None,ge=0,le=10000)
    dust_mg_m3: float | None = Field(None,ge=0,le=10000)

class Login(BaseModel):
    username: str = Field(max_length=80)
    password: str = Field(max_length=256)

class Decision(BaseModel):
    decision: Literal['approved','rejected']
    note: str = Field(min_length=10,max_length=2000)

class Question(BaseModel):
    question: str = Field(min_length=3,max_length=2000)

class UserCreate(BaseModel):
    username: str = Field(pattern=r'^[a-zA-Z0-9_.-]{3,40}$')
    password: str = Field(min_length=12,max_length=128)
    role: Literal['inspector','reviewer','admin','viewer']

class Rule(BaseModel):
    id: str = Field(pattern=r'^[A-Z0-9-]{3,50}$')
    title: str = Field(min_length=3,max_length=150)
    category: str = Field(min_length=3,max_length=80)
    text: str = Field(min_length=30,max_length=8000)
    metric: Literal['methane_pct','airflow_m3_s','dust_mg_m3']
    minimum: float | None = Field(None,ge=0)
    maximum: float | None = Field(None,ge=0)
    unit: str = Field(max_length=30)
