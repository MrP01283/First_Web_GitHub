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
    limit_value: int
    mode: str = "precise"


def count_words(text: str) -> int:
    return len(text.split())


def trim_to_word_limit(text: str, limit_value: int) -> str:
    if count_words(text) <= limit_value:
        return text.strip()

    return " ".join(text.split()[:limit_value]).strip()


def split_sentences(text: str) -> list[str]:
    sentences = re.findall(r"[^.!?…]+[.!?…]*", text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def split_overflow_parts(text: str, overflow_size: int) -> tuple[str, str]:
    sentences = split_sentences(text)

    if len(sentences) <= 1:
        return "", text.strip()

    tail_sentences = [sentences[-1]]
    minimum_tail_size = overflow_size + 7

    for sentence in reversed(sentences[:-1]):
        tail_size = count_words(" ".join(tail_sentences))

        if tail_size >= minimum_tail_size:
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

    if data.mode not in ("precise", "fast"):
        raise HTTPException(status_code=400, detail="Неверный режим сокращения")

    if data.limit_value <= 0:
        raise HTTPException(status_code=400, detail="Лимит должен быть больше нуля")

    word_count = count_words(data.text)

    if data.limit_value > word_count:
        raise HTTPException(status_code=400, detail="Лимит слов больше количества слов в тексте")

    if client is None:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY не найден в .env")

    limit_prompt = f"Ответ должен быть не длиннее {data.limit_value} слов."

    try:
        debug_tail = ""
        debug_reason = ""
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
        result_size = count_words(result_text)

        if data.mode == "precise" and result_size > data.limit_value:
            overflow_size = result_size - data.limit_value
            prefix_text, tail_text = split_overflow_parts(result_text, overflow_size)
            target_tail_size = count_words(tail_text) - overflow_size
            debug_tail = tail_text
            debug_reason = "too_many"

            if target_tail_size > 0 and tail_text:
                adjustment_response = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=(
                        "Сократи фрагмент так, чтобы он естественно продолжал предыдущий текст. "
                        f"Фрагмент должен быть ровно на {target_tail_size} слов. "
                        "Не добавляй заголовки, пояснения или списки, если их не было во фрагменте. "
                        "Верни только переписанный фрагмент.\n\n"
                        f"Предыдущий текст:\n{prefix_text}\n\n"
                        f"Фрагмент:\n{tail_text}"
                    )
                )
                adjusted_tail = adjustment_response.text.strip()
                result_text = f"{prefix_text} {adjusted_tail}".strip() if prefix_text else adjusted_tail

        if data.mode == "precise" and result_size < data.limit_value:
            missing_size = data.limit_value - result_size
            debug_reason = "too_few"
            continuation_response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=(
                    "Продолжи этот сокращенный текст так, чтобы продолжение выглядело естественно "
                    "и не повторяло уже сказанное. "
                    f"Продолжение должно быть ровно на {missing_size} слов. "
                    "Верни только продолжение без заголовков и пояснений.\n\n"
                    f"Текст:\n{result_text}"
                )
            )
            continuation_text = continuation_response.text.strip()
            result_text = f"{result_text} {continuation_text}".strip()

        result_text = trim_to_word_limit(result_text, data.limit_value)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Ошибка Gemini API: {error}")

    return {"result": result_text, "debug_tail": debug_tail, "debug_reason": debug_reason}
