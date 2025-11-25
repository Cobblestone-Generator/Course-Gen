# CourseGen

CourseGen — это локальная платформа для автоматической генерации структурированных образовательных курсов на основе видео. Проект ориентирован на разработку и тестирование: быстрый старт, локальные LLM-интеграции (LM Studio / Qwen) и простая база данных (SQLite).

## Features

- Генерация курса в JSON на основе транскрипта видео
- Сохранение пользователей и курсов в SQLite для быстрой разработки
- API на FastAPI и статический фронтенд
- Экспорт курса в HTML (подготовлено для PDF)
- Скрипты для инициализации БД и создания админ-аккаунта

## Requirements

- Python 3.11+
- (Опционально) Docker + Docker Compose
- Пакеты в `backend/requirements.txt`

## Installation

1. Клонируйте репозиторий

```powershell
git clone <your-repo-url>
cd coursegen
```

2. Установите зависимости

```powershell
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

3. Создайте `.env` на основе примера

```powershell
copy .env.example .env
notepad .env
```

4. Инициализируйте базу данных 

```powershell
python .\init_db.py
# или
python .\create_user.py    
```

5. Запустите сервер

```powershell
uvicorn start:app --reload --host 0.0.0.0 --port 8000
```

Откройте `http://localhost:8000` в браузере.

## Usage

- Регистрация и вход: фронтенд страницы `frontend/login.html`, `frontend/register.html`.
- Сгенерировать курс: POST `/api/generate-course` c полем `video_url`.
- Список курсов пользователя: GET `/api/courses`.
- Детали курса: GET `/api/courses/{course_id}`.

## Docker

Запуск с Docker Compose:

```powershell
docker-compose up --build
```
Приложение будет доступно на `http://localhost:8000`.
