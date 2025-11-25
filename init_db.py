# init_db.py
import sqlite3
import os

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
    conn.close()
    print("✅ База данных инициализирована!")
    
    # Проверяем существование таблиц
    conn = sqlite3.connect('coursegen.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("📊 Таблицы в базе данных:", [table[0] for table in tables])
    
    conn.close()

if __name__ == "__main__":
    init_database()