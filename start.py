import uvicorn
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
import json
import sqlite3
from jose import jwt
import datetime
import hashlib
import requests

# Добавляем backend в путь Python
from typing import Optional

# Create main app
app = FastAPI(title="CourseGen")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# ========== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ==========

def init_database():
    print("🔧 Инициализация базы данных...")
    
    # Подключаемся к базе данных
    conn = sqlite3.connect('coursegen.db')
    cursor = conn.cursor()
    
    # Создаем таблицу users если её нет
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Создаем таблицу courses если её нет
    cursor.execute('''
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
    ''')
    
    conn.commit()
    
    # Проверяем существование таблиц
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("📊 Таблицы в базе данных:", [table[0] for table in tables])
    
    conn.close()
    print("✅ База данных готова!")

# Инициализируем базу данных при запуске
init_database()

# Load secrets from environment (do not hardcode in repo)
SECRET_KEY = os.getenv("SECRET_KEY", "coursegen-secret-key")
PASSWORD_SALT = os.getenv("PASSWORD_SALT", "coursegen-salt")

# ========== ИНТЕГРАЦИЯ С QWEN2.5-4B ==========

class QwenAIClient:
    def __init__(self, base_url: str = "http://127.0.0.1:1234/v1"):
        self.base_url = base_url
    
    def generate_course_content(self, video_title: str, transcript: str, video_description: str = "") -> dict:
        """Generate structured course content using Qwen2.5-4B"""
        
        # Ограничиваем длину транскрипта
        truncated_transcript = transcript[:3000] if len(transcript) > 3000 else transcript
        
        prompt = self._create_course_prompt(video_title, truncated_transcript, video_description)
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": "local-model",  # LM Studio автоматически использует загруженную модель
                    "messages": [
                        {
                            "role": "system",
                            "content": """Ты - эксперт по созданию образовательных курсов. 
                            Создавай структурированные, информативные учебные материалы на русском языке.
                            Всегда возвращай ответ в формате JSON без дополнительного текста."""
                        },
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ],
                    "max_tokens": 3000,
                    "temperature": 0.7,
                    "stream": False
                },
                timeout=180
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
    
    def _create_course_prompt(self, video_title: str, transcript: str, description: str) -> str:
        """Create optimized prompt for Qwen2.5-4B"""
        return f"""
СОЗДАЙ СТРУКТУРИРОВАННЫЙ УЧЕБНЫЙ КУРС НА РУССКОМ ЯЗЫКЕ НА ОСНОВЕ ЭТОГО ВИДЕО.

НАЗВАНИЕ ВИДЕО: {video_title}
ОПИСАНИЕ: {description}

ТРАНСКРИПТ ВИДЕО:
{transcript}

СОЗДАЙ КУРС СО СЛЕДУЮЩЕЙ СТРУКТУРОЙ В ФОРМАТЕ JSON:

1. ЗАГОЛОВОК КУРСА - отражает основную тему
2. ОПИСАНИЕ КУРСА - краткое введение (2-3 предложения)  
3. 2-3 РАЗДЕЛА - каждый с названием, содержанием и 3-4 ключевыми пунктами
4. 1-2 ТЕСТОВЫХ ВОПРОСА с вариантами ответов
5. КРАТКОЕ РЕЗЮМЕ основных идей

ВЕРНИ ОТВЕТ ТОЛЬКО В ФОРМАТЕ JSON БЕЗ ЛЮБОГО ДОПОЛНИТЕЛЬНОГО ТЕКСТА.

JSON ФОРМАТ:
{{
  "title": "Название курса",
  "description": "Описание курса",
  "sections": [
    {{
      "title": "Название раздела 1",
      "content": "Содержание раздела...",
      "key_points": ["Пункт 1", "Пункт 2", "Пункт 3"]
    }},
    {{
      "title": "Название раздела 2", 
      "content": "Содержание раздела...",
      "key_points": ["Пункт 1", "Пункт 2", "Пункт 3"]
    }}
  ],
  "quizzes": [
    {{
      "question": "Вопрос для проверки знаний",
      "options": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"],
      "correct_answer": 0
    }}
  ],
  "summary": "Краткое резюме курса..."
}}
"""
    
    def _parse_ai_response(self, response_data: dict, video_title: str) -> dict:
        """Parse AI response and extract JSON"""
        try:
            content = response_data["choices"][0]["message"]["content"]
            
            # Очищаем ответ
            content = content.strip()
            
            # Ищем JSON в ответе
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = content[start_idx:end_idx]
                course_data = json.loads(json_str)
                
                # Базовая валидация
                if "title" in course_data and "sections" in course_data:
                    print("✅ Курс успешно создан с помощью Qwen2.5-4B!")
                    return course_data
            
            # Если JSON не найден или невалиден
            print("⚠️  ИИ вернул некорректный формат, используем fallback")
            return self._get_fallback_content(video_title)
            
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            return self._get_fallback_content(video_title)
        except Exception as e:
            print(f"❌ Ошибка обработки ответа: {e}")
            return self._get_fallback_content(video_title)
    
    def _get_fallback_content(self, video_title: str) -> dict:
        """Fallback content if AI fails"""
        return {
            "title": f"Курс: {video_title}",
            "description": f"Автоматически сгенерированный курс на основе видео '{video_title}' с использованием AI",
            "sections": [
                {
                    "title": "Основные концепции",
                    "content": "Этот раздел содержит ключевые идеи и основные моменты из видео материала.",
                    "key_points": [
                        "Анализ основной темы и целей видео",
                        "Выделение ключевых сообщений и выводов", 
                        "Практическое применение представленной информации"
                    ]
                },
                {
                    "title": "Детальный разбор содержания",
                    "content": "Подробное рассмотрение основных тем и концепций, затронутых в видео.",
                    "key_points": [
                        "Структура и логика изложения материала",
                        "Важные детали, примеры и case studies",
                        "Рекомендации для углубленного изучения темы"
                    ]
                }
            ],
            "quizzes": [
                {
                    "question": "Какова основная цель или тема этого видео?",
                    "options": [
                        "Технический анализ или инструктаж",
                        "Образовательный или обучающий контент", 
                        "Развлекательный материал",
                        "Новостной или информационный репортаж"
                    ],
                    "correct_answer": 1
                }
            ],
            "summary": "Данный курс предоставляет структурированное изложение материала из исходного видео, выделяя ключевые идеи, концепции и практические аспекты для лучшего понимания и усвоения информации."
        }

def is_lm_studio_available():
    """Check if LM Studio is running"""
    try:
        response = requests.get("http://127.0.0.1:1234/v1/models", timeout=5)
        return response.status_code == 200
    except:
        return False

def generate_course_content(video_title: str, transcript: str, video_description: str = "") -> dict:
    """Generate course content using Qwen2.5-4B via LM Studio"""
    
    if is_lm_studio_available():
        print("🎯 Используем Qwen2.5-4B для создания курса...")
        ai_client = QwenAIClient()
        return ai_client.generate_course_content(video_title, transcript, video_description)
    else:
        print("⚠️  LM Studio недоступен, используем базовый шаблон")
        ai_client = QwenAIClient()
        return ai_client._get_fallback_content(video_title)

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def hash_password(password):
    """Функция хеширования пароля"""
    return hashlib.sha256((password + PASSWORD_SALT).encode()).hexdigest()

def create_access_token(email: str):
    """Создание JWT токена"""
    token_data = {
        "sub": email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    token = jwt.encode(token_data, SECRET_KEY, algorithm="HS256")
    return token

def verify_token(token: str):
    """Проверка JWT токена"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.JWTError:
        return None

async def get_current_user(request: Request):
    """Получение текущего пользователя из токена"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    user_email = verify_token(token)
    
    if not user_email:
        return None
    
    # Проверяем что пользователь существует в базе
    conn = sqlite3.connect('coursegen.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, first_name, last_name FROM users WHERE email = ?", (user_email,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            "id": user[0],
            "email": user[1],
            "first_name": user[2],
            "last_name": user[3]
        }
    return None

# ========== API ENDPOINTS ==========

# Serve frontend pages
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

# Handle .html requests
@app.get("/{page_name}.html")
async def serve_html_pages(page_name: str):
    pages = ["index", "login", "register", "generator", "my-courses", "support", "course-detail"]
    if page_name in pages:
        return FileResponse(f"frontend/{page_name}.html")
    return FileResponse("frontend/index.html")

@app.post("/api/register")
async def register_user(request: Request):
    """Регистрация пользователя"""
    try:
        form_data = await request.form()
        email = form_data.get("email")
        password = form_data.get("password")
        first_name = form_data.get("first_name")
        last_name = form_data.get("last_name")
        
        print(f"📝 Регистрация: {email}")
        
        if not email or not password or not first_name or not last_name:
            return JSONResponse({"detail": "Все поля обязательны для заполнения"}, status_code=400)
        
        # Проверяем в базе данных
        conn = sqlite3.connect('coursegen.db')
        cursor = conn.cursor()
        
        # Проверяем существует ли пользователь
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            conn.close()
            return JSONResponse({"detail": "Email already registered"}, status_code=400)
        
        # Создаем пользователя
        hashed_password = hash_password(password)
        
        cursor.execute('''
            INSERT INTO users (email, hashed_password, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (email, hashed_password, first_name, last_name))
        
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        # Создаем токен
        token = create_access_token(email)
        
        print(f"✅ Пользователь зарегистрирован: {email}")
        
        return JSONResponse({
            "access_token": token,
            "token_type": "bearer",
            "user_id": user_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name
        })
        
    except Exception as e:
        print(f"❌ Ошибка регистрации: {e}")
        return JSONResponse({"detail": str(e)}, status_code=500)

@app.post("/api/login")
async def login_user(request: Request):
    """Вход пользователя"""
    try:
        form_data = await request.form()
        email = form_data.get("email")
        password = form_data.get("password")
        
        print(f"🔐 Вход: {email}")
        
        if not email or not password:
            return JSONResponse({"detail": "Email и пароль обязательны"}, status_code=400)
        
        # Проверяем в базе данных
        conn = sqlite3.connect('coursegen.db')
        cursor = conn.cursor()
        
        # Ищем пользователя
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return JSONResponse({"detail": "Incorrect email or password"}, status_code=401)
        
        # Проверяем пароль
        hashed_input = hash_password(password)
        stored_hash = user[2]  # hashed_password находится в третьей колонке
        
        if hashed_input != stored_hash:
            conn.close()
            return JSONResponse({"detail": "Incorrect email or password"}, status_code=401)
        
        # Создаем токен
        token = create_access_token(email)
        
        print(f"✅ Успешный вход: {email}")
        
        return JSONResponse({
            "access_token": token,
            "token_type": "bearer",
            "user_id": user[0],  # id
            "email": user[1],    # email
            "first_name": user[3], # first_name
            "last_name": user[4]   # last_name
        })
        
    except Exception as e:
        print(f"❌ Ошибка входа: {e}")
        return JSONResponse({"detail": str(e)}, status_code=500)

@app.get("/api/courses")
async def get_user_courses(request: Request):
    """Get user courses"""
    try:
        current_user = await get_current_user(request)
        if not current_user:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        
        user_id = current_user["id"]
        print(f"📚 Loading courses for user: {current_user['email']}")
        
        # Получаем курсы пользователя из базы данных
        conn = sqlite3.connect('coursegen.db')
        cursor = conn.cursor()
        
        # Получаем курсы пользователя
        cursor.execute('''
            SELECT id, title, description, video_url, video_title, created_at 
            FROM courses WHERE user_id = ? ORDER BY created_at DESC
        ''', (user_id,))
        
        courses_data = cursor.fetchall()
        conn.close()
        
        courses = []
        for course in courses_data:
            courses.append({
                "id": course[0],
                "title": course[1],
                "description": course[2],
                "video_url": course[3],
                "video_title": course[4],
                "created_at": course[5]
            })
        
        print(f"✅ Loaded {len(courses)} courses for user: {current_user['email']}")
        
        return JSONResponse({"courses": courses})
        
    except Exception as e:
        print(f"❌ Error loading courses: {e}")
        return JSONResponse({"courses": []})

@app.post("/api/generate-course")
async def generate_course(request: Request):
    """Generate course from YouTube video using Qwen2.5-4B"""
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
        
        # Извлекаем ID видео из YouTube URL
        video_id = "unknown"
        video_title_from_url = "YouTube Video"
        if "youtube.com/watch?v=" in video_url:
            video_id = video_url.split("youtube.com/watch?v=")[1].split("&")[0]
            video_title_from_url = f"YouTube Video {video_id}"
        elif "youtu.be/" in video_url:
            video_id = video_url.split("youtu.be/")[1].split("?")[0]
            video_title_from_url = f"YouTube Video {video_id}"
        
        # Проверяем доступность LM Studio
        ai_status = "Qwen2.5-4B" if is_lm_studio_available() else "basic template"
        print(f"🤖 AI Status: {ai_status}")
        
        # Создаем демо-транскрипт (в реальном приложении используйте youtube.py)
        demo_transcript = f"""
        Это автоматически сгенерированный транскрипт видео '{video_title_from_url}'.
        В реальной системе здесь будет извлеченный текст из YouTube видео с помощью YouTube Transcript API.
        Текущий видео материал посвящен образовательной тематике и содержит ценную информацию для обучения.
        Основные темы включают в себя анализ контента, выделение ключевых идей и структурирование учебного материала.
        """
        
        # Генерируем контент курса с помощью Qwen2.5-4B
        course_content = generate_course_content(
            video_title=video_title_from_url,
            transcript=demo_transcript,
            video_description=f"Видео с YouTube: {video_url}"
        )
        
        conn = sqlite3.connect('coursegen.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO courses (title, description, video_url, video_title, content, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            course_content.get("title", f"Курс: {video_title_from_url}"),
            course_content.get("description", "Автоматически сгенерированный курс"),
            video_url,
            video_title_from_url,
            json.dumps(course_content, ensure_ascii=False),
            user_id
        ))
        
        course_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✅ Course created with {ai_status}! ID: {course_id}")
        
        return JSONResponse({
            "success": True,
            "course_id": course_id,
            "title": course_content.get("title", f"Курс: {video_title_from_url}"),
            "message": f"Курс успешно создан с помощью {ai_status}!",
            "ai_used": ai_status,
            "pdf_url": f"/api/courses/{course_id}/pdf"
        })
        
    except Exception as e:
        print(f"❌ Course generation error: {e}")
        return JSONResponse({"detail": str(e)}, status_code=500)

@app.get("/api/courses/{course_id}")
async def get_course_detail(course_id: int, request: Request):
    """Get detailed course information"""
    try:
        current_user = await get_current_user(request)
        if not current_user:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        
        user_id = current_user["id"]
        
        # Получаем курс
        conn = sqlite3.connect('coursegen.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, title, description, video_url, video_title, content, created_at 
            FROM courses WHERE id = ? AND user_id = ?
        ''', (course_id, user_id))
        
        course = cursor.fetchone()
        conn.close()
        
        if not course:
            return JSONResponse({"detail": "Course not found"}, status_code=404)
        
        # Форматируем ответ
        course_data = {
            "id": course[0],
            "title": course[1],
            "description": course[2],
            "video_url": course[3],
            "video_title": course[4],
            "content": course[5],
            "created_at": course[6]
        }
        
        print(f"✅ Course details loaded: {course_data['title']}")
        
        return JSONResponse(course_data)
        
    except Exception as e:
        print(f"❌ Error loading course details: {e}")
        return JSONResponse({"detail": str(e)}, status_code=500)

@app.get("/api/courses/{course_id}/pdf")
async def get_course_pdf(course_id: int, request: Request):
    """Скачивание PDF курса"""
    try:
        current_user = await get_current_user(request)
        if not current_user:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        
        user_id = current_user["id"]
        
        # Получаем курс
        conn = sqlite3.connect('coursegen.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT title, content FROM courses WHERE id = ? AND user_id = ?
        ''', (course_id, user_id))
        
        course = cursor.fetchone()
        conn.close()
        
        if not course:
            return JSONResponse({"detail": "Course not found"}, status_code=404)
        
        # Генерируем простой HTML для PDF
        course_title = course[0]
        course_content_raw = course[1]
        
        # Парсим контент курса
        try:
            course_content = json.loads(course_content_raw)
        except:
            course_content = {
                "title": course_title,
                "description": "Автоматически сгенерированный курс",
                "sections": [],
                "summary": "Курс создан на основе видео материала"
            }
        
        # Создаем HTML контент
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
                .key-points {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .quiz {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .summary {{ background: #e8f5e8; padding: 20px; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>{course_content.get('title', course_title)}</h1>
            <p><strong>Описание:</strong> {course_content.get('description', 'Автоматически сгенерированный курс')}</p>
            <p><em>Сгенерировано с помощью AI: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</em></p>
            
            <div class="content">
        """
        
        # Добавляем разделы
        sections = course_content.get('sections', [])
        for i, section in enumerate(sections, 1):
            html_content += f"""
                <div class="section">
                    <h2>{i}. {section.get('title', f'Раздел {i}')}</h2>
                    <p>{section.get('content', 'Содержание раздела')}</p>
            """
            
            # Добавляем ключевые моменты
            key_points = section.get('key_points', [])
            if key_points:
                html_content += f"""
                    <div class="key-points">
                        <h3>Ключевые моменты:</h3>
                        <ul>
                            {"".join(f'<li>{point}</li>' for point in key_points)}
                        </ul>
                    </div>
                """
            
            html_content += "</div>"
        
        # Добавляем тесты
        quizzes = course_content.get('quizzes', [])
        if quizzes:
            html_content += '<h2>Тесты для проверки знаний</h2>'
            for i, quiz in enumerate(quizzes, 1):
                html_content += f"""
                    <div class="quiz">
                        <h3>Вопрос {i}: {quiz.get('question', 'Вопрос')}</h3>
                        <ol>
                            {"".join(f'<li>{option}</li>' for option in quiz.get('options', []))}
                        </ol>
                    </div>
                """
        
        # Добавляем резюме
        summary = course_content.get('summary')
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
        
        # Сохраняем как HTML файл
        os.makedirs("courses", exist_ok=True)
        pdf_path = f"courses/course_{course_id}.html"
        
        with open(pdf_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return FileResponse(
            pdf_path,
            filename=f"{course_title}.html",
            media_type='text/html'
        )
        
    except Exception as e:
        print(f"❌ Error generating PDF: {e}")
        return JSONResponse({"detail": str(e)}, status_code=500)

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    lm_status = "available" if is_lm_studio_available() else "unavailable"
    return JSONResponse({
        "status": "ok", 
        "message": "CourseGen API is running",
        "ai_status": lm_status,
        "ai_model": "Qwen2.5-4B"
    })

@app.get("/api/debug")
async def debug():
    """Debug endpoint"""
    import sqlite3
    conn = sqlite3.connect('coursegen.db')
    cursor = conn.cursor()
    
    # Получаем всех пользователей
    cursor.execute("SELECT id, email, first_name, last_name FROM users")
    users = cursor.fetchall()
    
    # Получаем все курсы
    cursor.execute("SELECT id, title, user_id FROM courses")
    courses = cursor.fetchall()
    
    conn.close()
    
    lm_status = "available" if is_lm_studio_available() else "unavailable"
    
    return JSONResponse({
        "message": "Debug info",
        "users": [{"id": u[0], "email": u[1], "name": f"{u[2]} {u[3]}"} for u in users],
        "courses": [{"id": c[0], "title": c[1], "user_id": c[2]} for c in courses],
        "database_exists": os.path.exists('coursegen.db'),
        "lm_studio_status": lm_status,
        "current_directory": os.getcwd()
    })

@app.get("/api/ai-status")
async def ai_status():
    """Check AI status"""
    status = is_lm_studio_available()
    return JSONResponse({
        "ai_available": status,
        "model": "Qwen2.5-4B",
        "endpoint": (os.getenv("QWEN_API_URL", "http://127.0.0.1:1234/v1") if status else "unavailable")
    })

@app.delete("/api/courses/{course_id}")
async def delete_course(course_id: int, request: Request):
    """Удаление курса"""
    try:
        current_user = await get_current_user(request)
        if not current_user:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        
        user_id = current_user["id"]
        
        # Проверяем существование курса и принадлежность пользователю
        conn = sqlite3.connect('coursegen.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id FROM courses WHERE id = ? AND user_id = ?
        ''', (course_id, user_id))
        
        course = cursor.fetchone()
        
        if not course:
            conn.close()
            return JSONResponse({"detail": "Course not found"}, status_code=404)
        
        # Удаляем курс
        cursor.execute('DELETE FROM courses WHERE id = ?', (course_id,))
        conn.commit()
        conn.close()
        
        print(f"✅ Course deleted: {course_id} by user: {current_user['email']}")
        
        return JSONResponse({
            "success": True,
            "message": "Курс успешно удален"
        })
        
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
    
    # Проверяем статус LM Studio
    if is_lm_studio_available():
        print("✅ Qwen2.5-4B доступен через LM Studio!")
    else:
        print("⚠️  LM Studio недоступен, будут использоваться шаблонные курсы")
    
    uvicorn.run("start:app", host="0.0.0.0", port=8000, reload=True)