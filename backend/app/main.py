from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse,FileResponse 
from sqlalchemy.orm import Session
from typing import List
import os

from . import models, database, auth, youtube, ai_generator
from .models import User, Course
from .auth import get_current_user, create_access_token
from .database import get_db

app = FastAPI(title="CourseGen API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create database tables
models.Base.metadata.create_all(bind=database.engine)

@app.post("/api/register", response_model=dict)
async def register(
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    db: Session = Depends(get_db)
):
    """Регистрация пользователя"""
    # Check if user exists
    db_user = auth.get_user_by_email(db, email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user = auth.create_user(db, email, password, first_name, last_name)
    
    # Generate token
    access_token = create_access_token(data={"sub": user.email})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name
    }

@app.post("/api/login", response_model=dict)
async def login(
    email: str,
    password: str,
    db: Session = Depends(get_db)
):
    """Вход пользователя"""
    user = auth.authenticate_user(db, email, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token = create_access_token(data={"sub": user.email})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name
    }

@app.post("/api/generate-course")
async def generate_course(
    video_url: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Генерация курса из YouTube видео"""
    try:
        # Extract video info
        video_info = youtube.get_video_info(video_url)
        
        # Get transcript
        transcript = youtube.get_video_transcript(video_url)
        
        # Generate course content using AI
        course_content = ai_generator.generate_course_content(
            video_title=video_info["title"],
            transcript=transcript,
            video_description=video_info.get("description", "")
        )
        
        # Create course in database
        course = models.Course(
            title=course_content["title"],
            description=course_content["description"],
            video_url=video_url,
            video_title=video_info["title"],
            user_id=current_user.id,
            content=course_content
        )
        
        db.add(course)
        db.commit()
        db.refresh(course)
        
        # Generate PDF
        pdf_path = ai_generator.generate_pdf(course_content, course.id)
        
        return {
            "success": True,
            "course_id": course.id,
            "title": course.title,
            "message": "Курс успешно создан!",
            "pdf_url": f"/api/courses/{course.id}/pdf"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating course: {str(e)}"
        )

@app.get("/api/courses")
async def get_user_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение курсов пользователя"""
    courses = db.query(Course).filter(Course.user_id == current_user.id).all()
    return {
        "courses": [
            {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "created_at": course.created_at.isoformat(),
                "video_title": course.video_title,
                "video_url": course.video_url
            }
            for course in courses
        ]
    }

@app.get("/api/courses/{course_id}")
async def get_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Получение детальной информации о курсе"""
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    return course

@app.get("/api/courses/{course_id}/pdf")
async def get_course_pdf(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Скачивание PDF курса"""
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.user_id == current_user.id
    ).first()
    
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    pdf_path = f"courses/course_{course_id}.pdf"
    
    if not os.path.exists(pdf_path):
        pdf_path = ai_generator.generate_pdf(course.content, course_id)
    
    return FileResponse(
        pdf_path,
        filename=f"{course.title}.pdf",
        media_type='application/pdf'
    )

@app.get("/")
async def root():
    return {"message": "CourseGen API is running"}