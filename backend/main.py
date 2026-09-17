import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from google import genai
from pydantic import BaseModel

from backend.database import (
    clear_history_entries,
    delete_history_entry,
    get_history_items,
    init_db,
    save_history_entry,
)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
app = FastAPI()

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key, http_options={"timeout": 120000}) if api_key else None
WORD_PATTERN = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-'][A-Za-zА-Яа-яЁё0-9]+)*")
MAX_PRECISE_ATTEMPTS = 3

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
    return len(WORD_PATTERN.findall(text))


def trim_to_word_limit(text: str, limit_value: int) -> str:
    if count_words(text) <= limit_value:
        return text.strip()

    matches = list(WORD_PATTERN.finditer(text))

    if len(matches) <= limit_value:
        return text.strip()

    return text[:matches[limit_value - 1].end()].strip()


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


init_db()


@app.get("/")
def frontend():
    return FileResponse(BASE_DIR / "frontend" / "index.html")


@app.post("/hello")
def hello(data: UserData):
    return {"message": f"Привет, {data.name}!"}


@app.get("/history")
def get_history():
    return {"items": get_history_items()}


@app.delete("/history")
def clear_history():
    clear_history_entries()
    return {"message": "История очищена"}


@app.delete("/history/{history_id}")
def delete_history_item(history_id: int):
    if not delete_history_entry(history_id):
        raise HTTPException(status_code=404, detail="Запись истории не найдена")

    return {"message": "Запись удалена"}


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

    limit_prompt = f"Ответ должен быть ровно на {data.limit_value} слов."

    try:
        debug_tail = ""
        debug_reason = ""
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=(
                "Сократи текст, сохранив основные мысли. "
                f"{limit_prompt} Верни только готовый текст без пояснений и заголовков. "
                "Не делай ответ короче или длиннее заданного лимита. Перед ответом проверь количество слов.\n\n"
                f"Текст:\n{data.text}"
            )
        )

        result_text = response.text.strip()

        if data.mode == "precise":
            for _ in range(MAX_PRECISE_ATTEMPTS):
                result_size = count_words(result_text)

                if result_size == data.limit_value:
                    break

                if result_size > data.limit_value:
                    overflow_size = result_size - data.limit_value
                    prefix_text, tail_text = split_overflow_parts(result_text, overflow_size)
                    target_tail_size = count_words(tail_text) - overflow_size
                    debug_tail = tail_text
                    debug_reason = "too_many"

                    if target_tail_size <= 0 or not tail_text:
                        break

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
                    continue

                prefix_text, tail_text = split_overflow_parts(result_text, 0)
                target_tail_size = data.limit_value - count_words(prefix_text)
                debug_tail = tail_text
                debug_reason = "too_few"

                if target_tail_size <= count_words(tail_text) or not tail_text:
                    break

                adjustment_response = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=(
                        "Перепиши фрагмент так, чтобы он естественно завершал предыдущий текст. "
                        f"Фрагмент должен быть ровно на {target_tail_size} слов. "
                        "Сохрани смысл, не добавляй новую тему и не повторяй уже сказанное. "
                        "Верни только переписанный фрагмент без заголовков и пояснений.\n\n"
                        f"Предыдущий текст:\n{prefix_text}\n\n"
                        f"Фрагмент:\n{tail_text}"
                    )
                )
                adjusted_tail = adjustment_response.text.strip()
                result_text = f"{prefix_text} {adjusted_tail}".strip() if prefix_text else adjusted_tail

        result_text = trim_to_word_limit(result_text, data.limit_value)
    except Exception as error:
        error_message = f"Ошибка Gemini API: {error}"
        save_history_entry(
            source_text=data.text,
            result_text="",
            limit_value=data.limit_value,
            mode=data.mode,
            source_words=word_count,
            result_words=0,
            status="error",
            error_text=error_message,
        )
        raise HTTPException(status_code=502, detail=error_message)

    save_history_entry(
        source_text=data.text,
        result_text=result_text,
        limit_value=data.limit_value,
        mode=data.mode,
        source_words=word_count,
        result_words=count_words(result_text),
        status="success",
    )
    return {"result": result_text, "debug_tail": debug_tail, "debug_reason": debug_reason}
