# First Web App

Приложение для AI-сокращения текста: FastAPI отдает frontend, принимает текст на `/summarize`, отправляет его в Gemini API и возвращает результат.

## Технологии

- Frontend: HTML, CSS, JavaScript
- Backend: Python, FastAPI, Uvicorn
- AI: Gemini API
- Env: python-dotenv

## Локальный запуск

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Открой:

```text
http://127.0.0.1:8000
```

Документация API:

```text
http://127.0.0.1:8000/docs
```

## API ключ

Создай файл `.env` в корне проекта:

```env
GEMINI_API_KEY=твой_ключ
```

Ключ можно получить в Google AI Studio:

```text
https://aistudio.google.com/app/apikey
```

Файл `.env` не коммить в git.

## Render

Создай Web Service из GitHub-репозитория.

Настройки:

```text
Runtime: Python 3
Build Command: pip install -r requirements.txt
Start Command: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Environment Variables:

```text
GEMINI_API_KEY=твой_ключ
```

После деплоя frontend будет открываться прямо по Render-ссылке, например:

```text
https://first-web-github.onrender.com
```




АШИЛЬ КРАСАВЧИК ЧТО?