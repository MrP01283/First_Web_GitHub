# First Web App

Простой проект с frontend и backend: пользователь вводит большой текст, backend отправляет его в Gemini API, а frontend показывает сокращенную версию.

## Технологии

- Frontend: HTML, CSS, JavaScript
- Backend: Python, FastAPI
- AI: Gemini API
- Env: python-dotenv

## Установка

```
powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## API ключ

Создай файл `.env` в корне проекта:

```
env
GEMINI_API_KEY=твой_ключ
```

Ключ можно получить в Google AI Studio:

https://aistudio.google.com/app/apikey

Файл `.env` не коммить в git.

## Запуск

Запусти backend из корня проекта:

```
powershell
uvicorn backend.main:app --reload
```

Документация API:

```
text
http://127.0.0.1:8000/docs
```

Frontend открой в браузере:

```
text
frontend/index.html
```

Т.е. сначало запускаешь backend в терминале, а потом открываешь index.html в frontend