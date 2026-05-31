import sqlite3
import os

# تحديد مسار ملف الداتابيز عشان نضمن إنه يتكَرّيت جوه مجلد database
DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

def get_connection():
    """بتفتح اتصال بقاعدة البيانات"""
    return sqlite3.connect(DB_PATH)

def setup_db():
    """بتعمل الجدول الأساسي لو مش موجود"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER,
            guild_id INTEGER,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, guild_id)
        )
    ''')
    conn.commit()
    conn.close()

def add_user(user_id, guild_id):
    """بتضيف عضو جديد للداتابيز لو أول مرة يبعت رسالة"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, guild_id, xp, level)
        VALUES (?, ?, 0, 0)
    ''', (user_id, guild_id))
    conn.commit()
    conn.close()

def get_user(user_id, guild_id):
    """بتجيب بيانات العضو (الـ XP والليفل)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT xp, level FROM users WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
    result = cursor.fetchone()
    conn.close()
    return result

def add_xp(user_id, guild_id, xp_amount):
    """بتزود XP للعضو"""
    # نتأكد الأول إن العضو متسجل
    add_user(user_id, guild_id) 
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET xp = xp + ? 
        WHERE user_id = ? AND guild_id = ?
    ''', (xp_amount, user_id, guild_id))
    conn.commit()
    conn.close()

def update_level(user_id, guild_id, new_level):
    """بتعمل تحديث لليفل العضو لما يترقى"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users 
        SET level = ? 
        WHERE user_id = ? AND guild_id = ?
    ''', (new_level, user_id, guild_id))
    conn.commit()
    conn.close()

# تشغيل الدالة دي تلقائياً أول ما الملف ده يتعمله Import عشان نضمن وجود الجدول
setup_db()