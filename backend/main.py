import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from google import genai
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
app = FastAPI()

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key, http_options={"timeout": 120000}) if api_key else None

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
    style: str = "short"


@app.get("/")
def frontend():
    return FileResponse(BASE_DIR / "frontend" / "index.html")


@app.post("/hello")
def hello(data: UserData):
    return {"message": f"Привет, {data.name}!"}


@app.post("/summarize")
def summarize(data: SummarizeRequest):
    if data.text.strip() == "":
        raise HTTPException(status_code=400, detail="Текст не должен быть пустым")

    if client is None:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY не найден в .env")

    style_prompts = {
        "short": "Сократи текст очень кратко, сохранив основные мысли.",
        "detailed": "Сократи текст подробнее, сохранив важные детали и общий смысл.",
        "list": "Сократи текст в виде списка ключевых пунктов."
    }
    summarize_prompt = style_prompts.get(data.style, style_prompts["short"])

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=f"{summarize_prompt}\n\nТекст:\n{data.text}"
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Ошибка Gemini API: {error}")

    return {"result": response.text}
