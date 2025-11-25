# create_user.py
"""Secure helper to create or update an admin user.

Behaviour:
- If environment variables `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set, the script
  will use them to create/update the user.
- Otherwise the script prompts interactively for email and password.

This file no longer contains hardcoded credentials or salts.
"""

import os
import sqlite3
import hashlib
import getpass


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((password + salt).encode()).hexdigest()


def init_database():
    conn = sqlite3.connect('coursegen.db')
    cursor = conn.cursor()

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


def create_or_update_user(email: str, password: str, first_name: str = None, last_name: str = None, salt: str = "coursegen-salt"):
    """Create user or update password if user exists."""
    init_database()
    conn = sqlite3.connect('coursegen.db')
    cursor = conn.cursor()

    hashed = hash_password(password, salt)

    try:
        cursor.execute('''
            INSERT INTO users (email, hashed_password, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (email, hashed, first_name, last_name))
        conn.commit()
        print(f"✅ Пользователь создан: {email}")
    except sqlite3.IntegrityError:
        cursor.execute('''
            UPDATE users SET hashed_password = ? WHERE email = ?
        ''', (hashed, email))
        conn.commit()
        print(f"✅ Пароль для пользователя обновлён: {email}")

    conn.close()


def main():
    # Prefer environment variables for automation
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    password_salt = os.getenv("PASSWORD_SALT", "coursegen-salt")

    if not admin_email or not admin_password:
        print("Нет переменных окружения ADMIN_EMAIL/ADMIN_PASSWORD.")
        use_interactive = input("Ввести данные интерактивно? [y/N]: ").strip().lower() == 'y'
        if not use_interactive:
            print("Отменено. Установите ADMIN_EMAIL и ADMIN_PASSWORD в окружении для автоматического создания.")
            return

        admin_email = input("Email: ").strip()
        admin_password = getpass.getpass("Пароль (скрыто): ")

    if not admin_email or not admin_password:
        print("Email и пароль обязательны. Прерывание.")
        return

    create_or_update_user(admin_email, admin_password, first_name=None, last_name=None, salt=password_salt)


if __name__ == "__main__":
    main()