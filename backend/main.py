from fastapi import FastAPI, HTTPException
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


class SummarizeRequest(BaseModel):
    text: str


@app.get("/")
def root():
    return {"message": "Backend работает"}


@app.post("/hello")
def hello(data: UserData):
    return {"message": f"Привет, {data.name}!"}


@app.post("/summarize")
def summarize(data: SummarizeRequest):
    if data.text.strip() == "":
        raise HTTPException(status_code=400, detail="Текст не должен быть пустым")

    return {"result": data.text[:100]}
