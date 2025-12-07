import uvicorn
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile, File
import os
import sys
import json
import sqlite3
from jose import jwt
import datetime
import hashlib
import requests
from typing import Optional

app = FastAPI(title="CourseGen")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend/static"))
app.mount("/static", StaticFiles(directory=static_dir), name="static")


def init_database():
    print("🔧 Инициализация базы данных...")
    conn = sqlite3.connect("coursegen.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            video_url TEXT,
            video_title TEXT,
            content TEXT,
            user_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """
    )
    conn.commit()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("📊 Таблицы в базе данных:", [table[0] for table in tables])
    conn.close()
    print("✅ База данных готова!")


init_database()

SECRET_KEY = os.getenv("SECRET_KEY", "coursegen-secret-key")
PASSWORD_SALT = os.getenv("PASSWORD_SALT", "coursegen-salt")


class QwenAIClient:
    def __init__(self, base_url: str = "http://127.0.0.1:1234/v1"):
        self.base_url = base_url

    def generate_course_content(
        self, video_title: str, transcript: str, video_description: str = ""
    ) -> dict:
        truncated_transcript = (
            transcript[:4000] if len(transcript) > 4000 else transcript
        )
        prompt = self._create_course_prompt(
            video_title, truncated_transcript, video_description
        )
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": "local-model",
                    "messages": [
                        {
                            "role": "system",
                            "content": """Ты — эксперт по составлению образовательных курсов. Создавай подробные, структурированные учебные материалы на русском языке. Возвращай только JSON-ответ.""",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 4000,
                    "temperature": 0.7,
                    "stream": False,
                },
                timeout=360,
            )
            if response.status_code == 200:
                return self._parse_ai_response(response.json(), video_title)
            else:
                print(f"❌ Ошибка API: {response.status_code}")
                return self._get_fallback_content(video_title)
        except requests.exceptions.Timeout:
            print("❌ Таймаут запроса к LM Studio")
            return self._get_fallback_content(video_title)
        except requests.exceptions.ConnectionError:
            print("❌ Не могу подключиться к LM Studio")
            return self._get_fallback_content(video_title)
        except Exception as e:
            print(f"❌ Неожиданная ошибка: {e}")
            return self._get_fallback_content(video_title)

    def _create_course_prompt(
        self, video_title: str, transcript: str, description: str
    ) -> str:
        return f"""
СОЗДАЙ ПОДРОБНЫЙ ОБРАЗОВАТЕЛЬНЫЙ КУРС НА РУССКОМ ЯЗЫКЕ ПО ЭТОМУ ВИДЕО ИЛИ PDF.
НАЗВАНИЕ: {video_title}
ОПИСАНИЕ: {description}

ИСТОЧНИК (транскрипт/текст):
{transcript}

Требования:
1. В description дай полноценное введение: мотивация, ценность темы (6-8 предложений).
2. В каждом sections.content — подробный текст (10-15 информативных предложений).
3. Блок quizzes: массив из 10 объектов, каждый из которых содержит:
   - "question": текст вопроса,
   - "options": список из 4 вариантов ответа,
   - "correct_answer": номер правильного варианта (индекс от 0 до 3).
4. Не добавляй поля, которых нет в JSON-примере ниже!
5. Не добавляй текстовых пояснений к правильным ответам — только номер индекса.
6. Если источник — PDF, не выводи ссылку на видео и поле "video_url" в JSON.

JSON пример:
{{
  "title": "Название курса",
  "description": "Введение...",
  "sections": [
    {{
      "title": "Название раздела 1",
      "content": "Развернутый текст по теме"
    }},
    ...
  ],
  "quizzes": [
    {{
      "question": "Сформулируй вопрос",
      "options": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"],
      "correct_answer": 1
    }},
    ... (ровно 10 объектов)
  ],
  "summary": "Итоговое резюме, 3-5 предложений, подытоживай идеи и выводы курса"
}}
Ответ только в JSON, без пояснений, картинок и лишнего текста!
"""

    def _parse_ai_response(self, response_data: dict, video_title: str) -> dict:
        try:
            content = response_data["choices"][0]["message"]["content"]
            content = content.strip()
            start_idx = content.find("{")
            end_idx = content.rfind("}") + 1
            if start_idx != -1 and end_idx != 0:
                json_str = content[start_idx:end_idx]
                course_data = json.loads(json_str)
                if "title" in course_data and "sections" in course_data:
                    print("✅ Курс успешно создан с помощью Qwen2.5-4B!")
                    return course_data
            print("⚠️  ИИ вернул некорректный формат, используем fallback")
            return self._get_fallback_content(video_title)
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            return self._get_fallback_content(video_title)
        except Exception as e:
            print(f"❌ Ошибка обработки ответа: {e}")
            return self._get_fallback_content(video_title)

    def _get_fallback_content(self, video_title: str) -> dict:
        return {
            "title": f"Курс: {video_title}",
            "description": f"Автоматически сгенерированный курс, подробное введение в тему.",
            "sections": [
                {
                    "title": "Введение",
                    "content": "В этом разделе рассматриваются базовые понятия темы. Приводится подробное объяснение задачи, методов и их значения для практики. Это автоматический fallback и пример содержания.",
                },
                {
                    "title": "Основные методы и примеры",
                    "content": "Здесь разбираются основные подходы к теме, их преимущества и недостатки, приводятся типовые примеры решения реальных задач с пояснением каждого шага.",
                },
            ],
            "quizzes": [
                {
                    "question": "Что является главной темой этого курса?",
                    "options": [
                        "Обзор методов",
                        "Практическое применение",
                        "История развития",
                        "Примеры из жизни",
                    ],
                    "correct_answer": 1,
                }
            ],
            "summary": "В итоговом разделе подытоживаются основные идеи курса и приводятся рекомендации для дальнейшего самостоятельного изучения темы.",
        }


def is_lm_studio_available():
    try:
        response = requests.get("http://127.0.0.1:1234/v1/models", timeout=5)
        return response.status_code == 200
    except:
        return False


def generate_course_content(
    video_title: str, transcript: str, video_description: str = ""
) -> dict:
    if is_lm_studio_available():
        print("🎯 Используем Qwen2.5-4B для создания курса...")
        ai_client = QwenAIClient()
        return ai_client.generate_course_content(
            video_title, transcript, video_description
        )
    else:
        print("⚠️  LM Studio недоступен, используем базовый шаблон")
        ai_client = QwenAIClient()
        return ai_client._get_fallback_content(video_title)


def hash_password(password):
    return hashlib.sha256((password + PASSWORD_SALT).encode()).hexdigest()


def create_access_token(email: str):
    token_data = {
        "sub": email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24),
    }
    token = jwt.encode(token_data, SECRET_KEY, algorithm="HS256")
    return token


def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.JWTError:
        return None


async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    user_email = verify_token(token)
    if not user_email:
        return None
    conn = sqlite3.connect("coursegen.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, email, first_name, last_name FROM users WHERE email = ?",
        (user_email,),
    )
    user = cursor.fetchone()
    conn.close()
    if user:
        return {
            "id": user[0],
            "email": user[1],
            "first_name": user[2],
            "last_name": user[3],
        }
    return None


@app.get("/")
async def serve_index():
    return FileResponse("frontend/index.html")


@app.get("/login")
async def serve_login():
    return FileResponse("frontend/login.html")


@app.get("/register")
async def serve_register():
    return FileResponse("frontend/register.html")


@app.get("/generator")
async def serve_generator():
    return FileResponse("frontend/generator.html")


@app.get("/my-courses")
async def serve_my_courses():
    return FileResponse("frontend/my-courses.html")


@app.get("/support")
async def serve_support():
    return FileResponse("frontend/support.html")


@app.get("/course-detail")
async def serve_course_detail():
    return FileResponse("frontend/course-detail.html")


@app.get("/{page_name}.html")
async def serve_html_pages(page_name: str):
    pages = [
        "index",
        "login",
        "register",
        "generator",
        "my-courses",
        "support",
        "course-detail",
    ]
    if page_name in pages:
        return FileResponse(f"frontend/{page_name}.html")
    return FileResponse("frontend/index.html")


@app.post("/api/register")
async def register_user(request: Request):
    try:
        form_data = await request.form()
        email = form_data.get("email")
        password = form_data.get("password")
        first_name = form_data.get("first_name")
        last_name = form_data.get("last_name")
        print(f"📝 Регистрация: {email}")
        if not email or not password or not first_name or not last_name:
            return JSONResponse(
                {"detail": "Все поля обязательны для заполнения"}, status_code=400
            )
        conn = sqlite3.connect("coursegen.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            conn.close()
            return JSONResponse({"detail": "Email already registered"}, status_code=400)
        hashed_password = hash_password(password)
        cursor.execute(
            """
            INSERT INTO users (email, hashed_password, first_name, last_name)
            VALUES (?, ?, ?, ?)
        """,
            (email, hashed_password, first_name, last_name),
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        token = create_access_token(email)
        print(f"✅ Пользователь зарегистрирован: {email}")
        return JSONResponse(
            {
                "access_token": token,
                "token_type": "bearer",
                "user_id": user_id,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
            }
        )
    except Exception as e:
        print(f"❌ Ошибка регистрации: {e}")
        return JSONResponse({"detail": str(e)}, status_code=500)


@app.post("/api/login")
async def login_user(request: Request):
    try:
        form_data = await request.form()
        email = form_data.get("email")
        password = form_data.get("password")
        print(f"🔐 Вход: {email}")
        if not email or not password:
            return JSONResponse(
                {"detail": "Email и пароль обязательны"}, status_code=400
            )
        conn = sqlite3.connect("coursegen.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        if not user:
            conn.close()
            return JSONResponse(
                {"detail": "Incorrect email or password"}, status_code=401
            )
        hashed_input = hash_password(password)
        stored_hash = user[2]
        if hashed_input != stored_hash:
            conn.close()
            return JSONResponse(
                {"detail": "Incorrect email or password"}, status_code=401
            )
        token = create_access_token(email)
        print(f"✅ Успешный вход: {email}")
        return JSONResponse(
            {
                "access_token": token,
                "token_type": "bearer",
                "user_id": user[0],
                "email": user[1],
                "first_name": user[3],
                "last_name": user[4],
            }
        )
    except Exception as e:
        print(f"❌ Ошибка входа: {e}")
        return JSONResponse({"detail": str(e)}, status_code=500)


@app.get("/api/courses")
async def get_user_courses(request: Request):
    try:
        current_user = await get_current_user(request)
        if not current_user:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        user_id = current_user["id"]
        print(f"📚 Loading courses for user: {current_user['email']}")
        conn = sqlite3.connect("coursegen.db")
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, description, video_url, video_title, created_at 
            FROM courses WHERE user_id = ? ORDER BY created_at DESC
        """,
            (user_id,),
        )
        courses_data = cursor.fetchall()
        conn.close()
        courses = []
        for course in courses_data:
            courses.append(
                {
                    "id": course[0],
                    "title": course[1],
                    "description": course[2],
                    "video_url": course[3],
                    "video_title": course[4],
                    "created_at": course[5],
                }
            )
        print(f"✅ Loaded {len(courses)} courses for user: {current_user['email']}")
        return JSONResponse({"courses": courses})
    except Exception as e:
        print(f"❌ Error loading courses: {e}")
        return JSONResponse({"courses": []})


@app.post("/api/generate-course")
async def generate_course(request: Request):
    try:
        current_user = await get_current_user(request)
        if not current_user:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        form_data = await request.form()
        video_url = form_data.get("video_url")
        if not video_url:
            return JSONResponse({"detail": "Video URL is required"}, status_code=400)
        print(f"🎬 Generating course for: {video_url} by user: {current_user['email']}")
        user_id = current_user["id"]
        video_id = "unknown"
        video_title_from_url = "YouTube Video"
        if "youtube.com/watch?v=" in video_url:
            video_id = video_url.split("youtube.com/watch?v=")[1].split("&")[0]
            video_title_from_url = f"YouTube Video {video_id}"
        elif "youtu.be/" in video_url:
            video_id = video_url.split("youtu.be/")[1].split("?")[0]
            video_title_from_url = f"YouTube Video {video_id}"
        ai_status = "Qwen2.5-4B" if is_lm_studio_available() else "basic template"
        print(f"🤖 AI Status: {ai_status}")
        demo_transcript = f"""
        Это автоматически сгенерированный транскрипт видео '{video_title_from_url}'.
        В реальной системе здесь будет извлеченный текст из YouTube видео с помощью YouTube Transcript API.
        Текущий видео материал посвящен образовательной тематике и содержит ценную информацию для обучения.
        Основные темы включают в себя анализ контента, выделение ключевых идей и структурирование учебного материала.
        """
        course_content = generate_course_content(
            video_title=video_title_from_url,
            transcript=demo_transcript,
            video_description=f"Видео с YouTube: {video_url}",
        )
        conn = sqlite3.connect("coursegen.db")
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO courses (title, description, video_url, video_title, content, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                course_content.get("title", f"Курс: {video_title_from_url}"),
                course_content.get("description", "Автоматически сгенерированный курс"),
                video_url,
                video_title_from_url,
                json.dumps(course_content, ensure_ascii=False),
                user_id,
            ),
        )
        course_id = cursor.lastrowid
        conn.commit()
        conn.close()
        print(f"✅ Course created with {ai_status}! ID: {course_id}")
        return JSONResponse(
            {
                "success": True,
                "course_id": course_id,
                "title": course_content.get("title", f"Курс: {video_title_from_url}"),
                "message": f"Курс успешно создан с помощью {ai_status}!",
                "ai_used": ai_status,
                "pdf_url": f"/api/courses/{course_id}/pdf",
            }
        )
    except Exception as e:
        print(f"❌ Course generation error: {e}")
        return JSONResponse({"detail": str(e)}, status_code=500)


@app.post("/api/generate-course-from-pdf")
async def generate_course_from_pdf(request: Request, pdf: UploadFile = File(...)):
    try:
        current_user = await get_current_user(request)
        if not current_user:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        contents = await pdf.read()
        import io
        from PyPDF2 import PdfReader

        pdf_reader = PdfReader(io.BytesIO(contents))
        full_text = ""
        for page in pdf_reader.pages:
            page_txt = page.extract_text()
            if page_txt:
                full_text += page_txt + "\n"

        video_title = pdf.filename
        course_content = generate_course_content(
            video_title=video_title,
            transcript=full_text,
            video_description=f"Документ: {pdf.filename}",
        )

        # === Логика проверки, что результат AI валидный (title и sections есть, не None, не {}) ===
        if "title" not in course_content or not course_content.get("sections"):
            print("❗ Используем fallback, AI не дал валидный JSON!")
            course_content = {
                "title": f"Курс: {video_title}",
                "description": f"Автоматически сгенерированный курс из PDF",
                "sections": [],
                "quizzes": [],
                "summary": "Нет резюме",
            }

        course_content["is_pdf"] = True
        course_content["video_url"] = ""  # убираем ссылку для pdf

        conn = sqlite3.connect("coursegen.db")
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO courses (title, description, video_url, video_title, content, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                course_content.get("title", f"Курс: {video_title}"),
                course_content.get(
                    "description", "Автоматически сгенерированный курс из PDF"
                ),
                "",  # video_url пустой, источник — PDF
                video_title,
                json.dumps(course_content, ensure_ascii=False),
                current_user["id"],
            ),
        )
        course_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return JSONResponse(
            {
                "success": True,
                "course_id": course_id,
                "title": course_content.get("title", f"Курс: {video_title}"),
                "message": "Курс успешно создан из PDF!",
                "ai_used": "Qwen2.5-4B",
                "pdf_url": f"/api/courses/{course_id}/pdf",
            }
        )
    except Exception as e:
        print(f"❌ Course from PDF error: {e}")
        return JSONResponse({"detail": str(e)}, status_code=500)


@app.get("/api/courses/{course_id}")
async def get_course_detail(course_id: int, request: Request):
    try:
        current_user = await get_current_user(request)
        if not current_user:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        user_id = current_user["id"]
        conn = sqlite3.connect("coursegen.db")
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, description, video_url, video_title, content, created_at 
            FROM courses WHERE id = ? AND user_id = ?
        """,
            (course_id, user_id),
        )
        course = cursor.fetchone()
        conn.close()
        if not course:
            return JSONResponse({"detail": "Course not found"}, status_code=404)
        course_data = {
            "id": course[0],
            "title": course[1],
            "description": course[2],
            "video_url": course[3],
            "video_title": course[4],
            "content": course[5],
            "created_at": course[6],
        }
        print(f"✅ Course details loaded: {course_data['title']}")
        return JSONResponse(course_data)
    except Exception as e:
        print(f"❌ Error loading course details: {e}")
        return JSONResponse({"detail": str(e)}, status_code=500)

@app.get("/api/courses/{course_id}/pdf")
async def get_course_pdf(course_id: int, request: Request):
    try:
        current_user = await get_current_user(request)
        if not current_user:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        user_id = current_user["id"]
        conn = sqlite3.connect("coursegen.db")
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT title, content FROM courses WHERE id = ? AND user_id = ?
        """,
            (course_id, user_id),
        )
        course = cursor.fetchone()
        conn.close()
        if not course:
            return JSONResponse({"detail": "Course not found"}, status_code=404)
        course_title = course[0]
        course_content_raw = course[1]
        try:
            course_content = json.loads(course_content_raw)
        except:
            course_content = {
                "title": course_title,
                "description": "Автоматически сгенерированный курс",
                "sections": [],
                "summary": "Курс создан на основе видео материала",
            }
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{course_content.get('title', course_title)}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 40px; }}
                h1 {{ color: #2C3E50; border-bottom: 2px solid #a3ff00; padding-bottom: 10px; }}
                h2 {{ color: #2C3E50; margin-top: 30px; }}
                .section {{ margin-bottom: 30px; }}
                .quiz {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .summary {{ background: #e8f5e8; padding: 20px; border-radius: 5px; margin: 20px 0; }}
                .pdf-preview {{ margin: 12px 0; }}
                .pdf-preview img {{ max-width: 180px; max-height: 260px; border-radius: 5px; box-shadow: 0 1px 12px #ccc; margin: 0 4px; }}
            </style>
        </head>
        <body>
            <h1>{course_content.get('title', course_title)}</h1>
            <p><strong>Описание:</strong> {course_content.get('description', 'Автоматически сгенерированный курс')}</p>
            <p><em>Сгенерировано с помощью AI: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</em></p>
            <div class="content">
        """
        sections = course_content.get("sections", [])
        for i, section in enumerate(sections, 1):
            html_content += f"""
                <div class="section">
                    <h2>{i}. {section.get('title', f'Раздел {i}')}</h2>
                    <p>{section.get('content', 'Содержание раздела')}</p>
                </div>
            """
        quizzes = course_content.get("quizzes", [])
        if quizzes:
            html_content += "<h2>Тесты для проверки знаний</h2>"
            for i, quiz in enumerate(quizzes, 1):
                html_content += f"""
                    <div class="quiz">
                        <h3>Вопрос {i}: {quiz.get('question', 'Вопрос')}</h3>
                        <ol>
                            {"".join(f'<li>{option}</li>' for option in quiz.get('options', []))}
                        </ol>
                    </div>
                """
        summary = course_content.get("summary")
        if summary:
            html_content += f"""
                <div class="summary">
                    <h2>Итоговое резюме</h2>
                    <p>{summary}</p>
                </div>
            """
        html_content += """
            </div>
        </body>
        </html>
        """
        os.makedirs("courses", exist_ok=True)
        pdf_path = f"courses/course_{course_id}.html"
        with open(pdf_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return FileResponse(
            pdf_path, filename=f"{course_title}.html", media_type="text/html"
        )
    except Exception as e:
        print(f"❌ Error generating PDF: {e}")
        return JSONResponse({"detail": str(e)}, status_code=500)


@app.get("/api/health")
async def health_check():
    lm_status = "available" if is_lm_studio_available() else "unavailable"
    return JSONResponse(
        {
            "status": "ok",
            "message": "CourseGen API is running",
            "ai_status": lm_status,
            "ai_model": "Qwen2.5-4B",
        }
    )


@app.get("/api/debug")
async def debug():
    import sqlite3

    conn = sqlite3.connect("coursegen.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, first_name, last_name FROM users")
    users = cursor.fetchall()
    cursor.execute("SELECT id, title, user_id FROM courses")
    courses = cursor.fetchall()
    conn.close()
    lm_status = "available" if is_lm_studio_available() else "unavailable"
    return JSONResponse(
        {
            "message": "Debug info",
            "users": [
                {"id": u[0], "email": u[1], "name": f"{u[2]} {u[3]}"} for u in users
            ],
            "courses": [{"id": c[0], "title": c[1], "user_id": c[2]} for c in courses],
            "database_exists": os.path.exists("coursegen.db"),
            "lm_studio_status": lm_status,
            "current_directory": os.getcwd(),
        }
    )


@app.get("/api/ai-status")
async def ai_status():
    status = is_lm_studio_available()
    return JSONResponse(
        {
            "ai_available": status,
            "model": "Qwen2.5-4B",
            "endpoint": (
                os.getenv("QWEN_API_URL", "http://127.0.0.1:1234/v1")
                if status
                else "unavailable"
            ),
        }
    )


@app.delete("/api/courses/{course_id}")
async def delete_course(course_id: int, request: Request):
    try:
        current_user = await get_current_user(request)
        if not current_user:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        user_id = current_user["id"]
        conn = sqlite3.connect("coursegen.db")
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id FROM courses WHERE id = ? AND user_id = ?
        """,
            (course_id, user_id),
        )
        course = cursor.fetchone()
        if not course:
            conn.close()
            return JSONResponse({"detail": "Course not found"}, status_code=404)
        cursor.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        conn.commit()
        conn.close()
        print(f"✅ Course deleted: {course_id} by user: {current_user['email']}")
        return JSONResponse({"success": True, "message": "Курс успешно удален"})
    except Exception as e:
        print(f"❌ Error deleting course: {e}")
        return JSONResponse({"detail": str(e)}, status_code=500)


if __name__ == "__main__":
    print("🚀 CourseGen Server started!")
    print("📁 Current directory:", os.getcwd())
    print("🌐 Open: http://localhost:8000")
    print("🔍 Debug: http://localhost:8000/api/debug")
    print("❤️ Health: http://localhost:8000/api/health")
    print("🤖 AI Status: http://localhost:8000/api/ai-status")
    if is_lm_studio_available():
        print("✅ Qwen2.5-4B доступен через LM Studio!")
    else:
        print("⚠️  LM Studio недоступен, будут использоваться шаблонные курсы")
    uvicorn.run("start:app", host="0.0.0.0", port=8000, reload=True)
