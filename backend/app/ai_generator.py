import json
import os
from datetime import datetime
import requests
from typing import Dict, Any
import pdfkit

class QwenAIClient:
    def __init__(self, base_url: str = "http://127.0.0.1:1234/v1"):
        self.base_url = base_url
    
    def generate_course_content(self, video_title: str, transcript: str, video_description: str = "") -> dict:
        """Generate structured course content using Qwen3-VL-4B"""
        
        # Ограничиваем длину транскрипта
        truncated_transcript = transcript[:2500] if len(transcript) > 2500 else transcript
        
        prompt = self._create_optimized_prompt(video_title, truncated_transcript, video_description)
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": "local-model",
                    "messages": [
                        {
                            "role": "system",
                            "content": """Ты - эксперт по созданию образовательных курсов. 
                            Твоя задача - создавать структурированные, информативные учебные материалы на русском языке.
                            ВСЕГДА возвращай ПОЛНЫЙ ответ в формате JSON без обрезания.
                            Убедись что JSON валидный и содержит все необходимые поля."""
                        },
                        {
                            "role": "user", 
                            "content": prompt
                        }
                    ],
                    "max_tokens": 3000,  # Увеличили с 2000 до 3000
                    "temperature": 0.5,  # Уменьшили температуру для более стабильного вывода
                    "top_p": 0.9,
                    "stream": False
                },
                timeout=120  # Увеличили таймаут
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
    
    def _create_optimized_prompt(self, video_title: str, transcript: str, description: str) -> str:
        """Create optimized prompt for Qwen3-VL-4B"""
        return f"""
СОЗДАЙ УЧЕБНЫЙ КУРС В ФОРМАТЕ JSON НА ОСНОВЕ ВИДЕО.

ТЕМА: {video_title}
ОПИСАНИЕ: {description}

ТРАНСКРИПТ:
{transcript}

СОЗДАЙ ПОЛНЫЙ JSON С ТАКОЙ СТРУКТУРОЙ:

1. Заголовок курса
2. Описание курса (2-3 предложения)
3. 2 раздела с названием, содержанием и 3 ключевыми пунктами
4. 1 тестовый вопрос с 4 вариантами ответов
5. Краткое резюме

ВАЖНО: Верни ПОЛНЫЙ JSON без обрезания. Убедись что все скобки закрыты.

JSON ФОРМАТ:
{{
  "title": "Название курса здесь",
  "description": "Описание курса здесь",
  "sections": [
    {{
      "title": "Название раздела 1",
      "content": "Содержание раздела 1",
      "key_points": ["Пункт 1", "Пункт 2", "Пункт 3"]
    }},
    {{
      "title": "Название раздела 2", 
      "content": "Содержание раздела 2",
      "key_points": ["Пункт 1", "Пункт 2", "Пункт 3"]
    }}
  ],
  "quizzes": [
    {{
      "question": "Тестовый вопрос здесь",
      "options": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"],
      "correct_answer": 0
    }}
  ],
  "summary": "Краткое резюме курса здесь"
}}
"""
    
    def _parse_ai_response(self, response_data: dict, video_title: str) -> dict:
        """Parse AI response and extract JSON"""
        try:
            content = response_data["choices"][0]["message"]["content"]
            usage = response_data.get("usage", {})
            print(f"📊 Использовано токенов: {usage.get('completion_tokens', 0)}")
            
            # Очищаем ответ
            content = content.strip()
            print(f"📝 Ответ ИИ (первые 500 символов): {content[:500]}...")
            
            # Ищем JSON в ответе
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = content[start_idx:end_idx]
                print(f"🔍 Найден JSON длиной: {len(json_str)} символов")
                
                try:
                    course_data = json.loads(json_str)
                    
                    # Базовая валидация
                    if self._validate_course_data(course_data):
                        print("✅ Курс успешно создан с помощью Qwen3-VL-4B!")
                        return course_data
                    else:
                        print("⚠️  JSON не прошел валидацию")
                        
                except json.JSONDecodeError as e:
                    print(f"❌ Ошибка парсинга JSON: {e}")
                    print(f"🔍 Проблемный JSON: {json_str[:200]}...")
            
            # Если JSON не найден или невалиден
            print("⚠️  ИИ вернул некорректный формат, используем fallback")
            return self._get_fallback_content(video_title)
            
        except Exception as e:
            print(f"❌ Ошибка обработки ответа: {e}")
            return self._get_fallback_content(video_title)
    
    def _validate_course_data(self, course_data: dict) -> bool:
        """Validate course data structure"""
        required = ["title", "description", "sections"]
        if not all(field in course_data for field in required):
            return False
        
        # Проверяем секции
        sections = course_data.get("sections", [])
        if not sections or len(sections) < 1:
            return False
            
        # Проверяем что у секций есть обязательные поля
        for section in sections:
            if "title" not in section or "content" not in section:
                return False
                
        return True
    
    def _get_fallback_content(self, video_title: str) -> dict:
        """Fallback content if AI fails"""
        return {
            "title": f"Курс: {video_title}",
            "description": f"Автоматически сгенерированный курс на основе видео '{video_title}' с использованием Qwen3-VL-4B",
            "sections": [
                {
                    "title": "Основные концепции видео",
                    "content": "Этот раздел содержит анализ ключевых идей и основных моментов из видео материала.",
                    "key_points": [
                        "Анализ основной темы и целей видео",
                        "Выделение ключевых сообщений и выводов", 
                        "Практическое применение представленной информации"
                    ]
                },
                {
                    "title": "Структура и содержание",
                    "content": "Подробное рассмотрение структуры видео и основных концепций, затронутых в материале.",
                    "key_points": [
                        "Логика изложения и структура материала",
                        "Важные детали и примеры из видео",
                        "Рекомендации для дальнейшего изучения"
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
        response = requests.get("http://127.0.0.1:1234/v1/models", timeout=10)
        if response.status_code == 200:
            models = response.json().get("data", [])
            print(f"📋 Доступные модели в LM Studio: {[m['id'] for m in models]}")
            return True
        return False
    except Exception as e:
        print(f"❌ Ошибка проверки LM Studio: {e}")
        return False

# Основная функция генерации
def generate_course_content(video_title: str, transcript: str, video_description: str = "") -> Dict[str, Any]:
    """Generate course content using Qwen2.5-4B via LM Studio"""
    
    if is_lm_studio_available():
        print("🎯 Используем Qwen2.5-4B для создания курса...")
        ai_client = QwenAIClient()
        return ai_client.generate_course_content(video_title, transcript, video_description)
    else:
        print("⚠️  LM Studio недоступен, используем базовый шаблон")
        ai_client = QwenAIClient()
        return ai_client._get_fallback_content(video_title)

# Остальные функции (generate_pdf и т.д.) остаются без изменений
def generate_pdf(course_content: dict, course_id: int) -> str:
    """Generate PDF from course content"""
    
    # Create courses directory if not exists
    os.makedirs("courses", exist_ok=True)
    
    # HTML template for PDF
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{course_content['title']}</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 40px; }}
            h1 {{ color: #2C3E50; border-bottom: 2px solid #a3ff00; }}
            h2 {{ color: #2C3E50; margin-top: 30px; }}
            .section {{ margin-bottom: 30px; }}
            .key-points {{ background: #f8f9fa; padding: 15px; border-radius: 5px; }}
            .quiz {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <h1>{course_content['title']}</h1>
        <p><strong>Описание:</strong> {course_content['description']}</p>
        <p><em>Сгенерировано с помощью Qwen2.5-4B: {datetime.now().strftime('%Y-%m-%d %H:%M')}</em></p>
        
        <div class="content">
    """
    
    # Add sections
    for i, section in enumerate(course_content.get('sections', []), 1):
        html_content += f"""
            <div class="section">
                <h2>{i}. {section['title']}</h2>
                <p>{section['content']}</p>
                <div class="key-points">
                    <h3>Ключевые моменты:</h3>
                    <ul>
                        {"".join(f'<li>{point}</li>' for point in section.get('key_points', []))}
                    </ul>
                </div>
            </div>
        """
    
    # Add quizzes
    if course_content.get('quizzes'):
        html_content += '<h2>Тесты для проверки знаний</h2>'
        for i, quiz in enumerate(course_content['quizzes'], 1):
            html_content += f"""
                <div class="quiz">
                    <h3>Вопрос {i}: {quiz['question']}</h3>
                    <ol>
                        {"".join(f'<li>{option}</li>' for option in quiz['options'])}
                    </ol>
                </div>
            """
    
    # Add summary
    if course_content.get('summary'):
        html_content += f"""
            <div class="section">
                <h2>Итоговое резюме</h2>
                <p>{course_content['summary']}</p>
            </div>
        """
    
    html_content += """
        </div>
    </body>
    </html>
    """
    
    # Generate PDF
    pdf_path = f"courses/course_{course_id}.pdf"
    
    try:
        # You'll need to install wkhtmltopdf for this to work
        # On Ubuntu: sudo apt-get install wkhtmltopdf
        pdfkit.from_string(html_content, pdf_path)
    except:
        # Fallback: create HTML file if PDF generation fails
        with open(pdf_path.replace('.pdf', '.html'), 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    return pdf_path