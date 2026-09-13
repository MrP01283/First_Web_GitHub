from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserData(BaseModel):
    name: str


@app.get("/")
def root():
    return {"message": "Backend работает"}


@app.post("/hello")
def hello(data: UserData):
    return {"message": f"Привет, {data.name}!"}