import os
import re
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
    limit_type: str
    limit_value: int
    mode: str = "precise"


def count_units(text: str, limit_type: str) -> int:
    if limit_type == "chars":
        return len(text)

    return len(text.split())


def trim_to_limit(text: str, limit_type: str, limit_value: int) -> str:
    if count_units(text, limit_type) <= limit_value:
        return text.strip()

    if limit_type == "words":
        return " ".join(text.split()[:limit_value]).strip()

    trimmed_text = text[:limit_value].rstrip()
    last_space_index = trimmed_text.rfind(" ")

    if last_space_index > 0:
        return trimmed_text[:last_space_index].rstrip()

    return trimmed_text


def split_sentences(text: str) -> list[str]:
    sentences = re.findall(r"[^.!?…]+[.!?…]*", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def split_adjustment_parts(text: str, limit_type: str, difference: int) -> tuple[str, str]:
    sentences = split_sentences(text)

    if len(sentences) <= 1:
        return "", text.strip()

    tail_sentences = [sentences[-1]]

    if difference > 0:
        for sentence in reversed(sentences[:-1]):
            tail_size = count_units(" ".join(tail_sentences), limit_type)
            minimum_tail_size = difference + (5 if limit_type == "words" else 30)

            if tail_size >= minimum_tail_size or len(tail_sentences) >= 3:
                break

            tail_sentences.insert(0, sentence)

    prefix_sentences = sentences[:len(sentences) - len(tail_sentences)]
    return " ".join(prefix_sentences).strip(), " ".join(tail_sentences).strip()


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

    if data.limit_type not in ("chars", "words"):
        raise HTTPException(status_code=400, detail="Неверный тип лимита")

    if data.mode not in ("precise", "fast"):
        raise HTTPException(status_code=400, detail="Неверный режим сокращения")

    if data.limit_value <= 0:
        raise HTTPException(status_code=400, detail="Лимит должен быть больше нуля")

    text_length = len(data.text)
    word_count = len(data.text.split())

    if data.limit_type == "chars" and data.limit_value > text_length:
        raise HTTPException(status_code=400, detail="Лимит символов больше длины текста")

    if data.limit_type == "words" and data.limit_value > word_count:
        raise HTTPException(status_code=400, detail="Лимит слов больше количества слов в тексте")

    if client is None:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY не найден в .env")

    limit_prompt = (
        f"Ответ должен быть не длиннее {data.limit_value} символов."
        if data.limit_type == "chars"
        else f"Ответ должен быть не длиннее {data.limit_value} слов."
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=(
                "Сократи текст, сохранив основные мысли. "
                f"{limit_prompt} Верни только готовый текст без пояснений и заголовков. "
                "Перед ответом проверь длину.\n\n"
                f"Текст:\n{data.text}"
            )
        )

        result_text = response.text.strip()
        result_size = count_units(result_text, data.limit_type)

        if data.mode == "precise" and result_size != data.limit_value:
            difference = abs(result_size - data.limit_value)
            prefix_text, tail_text = split_adjustment_parts(result_text, data.limit_type, difference)
            target_tail_size = data.limit_value - count_units(prefix_text, data.limit_type)

            if target_tail_size > 0 and tail_text:
                unit_name = "символов" if data.limit_type == "chars" else "слов"
                adjustment_response = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=(
                        "Перепиши фрагмент так, чтобы он естественно продолжал предыдущий текст. "
                        f"Фрагмент должен быть ровно на {target_tail_size} {unit_name}. "
                        "Не добавляй заголовки, пояснения или списки, если их не было во фрагменте. "
                        "Верни только переписанный фрагмент.\n\n"
                        f"Предыдущий текст:\n{prefix_text}\n\n"
                        f"Фрагмент:\n{tail_text}"
                    )
                )
                adjusted_tail = adjustment_response.text.strip()
                result_text = f"{prefix_text} {adjusted_tail}".strip() if prefix_text else adjusted_tail

        result_text = trim_to_limit(result_text, data.limit_type, data.limit_value)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Ошибка Gemini API: {error}")

    return {"result": result_text}
