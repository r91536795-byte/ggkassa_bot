import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
import json

app = Flask(__name__)

# ========== НАСТРОЙКИ ==========
ADMIN_ID = 8763658506  # ЗАМЕНИ НА СВОЙ TELEGRAM ID

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, join_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS deposits (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount INTEGER, account_id TEXT, photo TEXT, status TEXT, date TEXT)''')
    c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (ADMIN_ID,))
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (user_id, username, join_date) VALUES (?, ?, ?)', 
              (user_id, username, datetime.now().strftime("%d.%m.%Y %H:%M")))
    conn.commit()
    conn.close()

def add_deposit(user_id, amount, account_id, photo):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('INSERT INTO deposits (user_id, amount, account_id, photo, status, date) VALUES (?, ?, ?, ?, ?, ?)',
              (user_id, amount, account_id, photo, 'pending', datetime.now().strftime("%d.%m.%Y %H:%M")))
    dep_id = c.lastrowid
    conn.commit()
    conn.close()
    return dep_id

def get_user_balance(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT SUM(amount) FROM deposits WHERE user_id = ? AND status = "approved"', (user_id,))
    balance = c.fetchone()[0] or 0
    conn.close()
    return balance

def get_all_deposits():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, user_id, amount, account_id, photo, status, date FROM deposits ORDER BY id DESC')
    rows = c.fetchall()
    conn.close()
    return rows

def update_deposit_status(dep_id, status):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('UPDATE deposits SET status = ? WHERE id = ?', (status, dep_id))
    conn.commit()
    conn.close()

def is_admin(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT * FROM admins WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row is not None

def get_stats():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    users = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM deposits WHERE status="pending"')
    pending = c.fetchone()[0]
    c.execute('SELECT SUM(amount) FROM deposits WHERE status="approved"')
    total = c.fetchone()[0] or 0
    conn.close()
    return {'users': users, 'pending': pending, 'total': total}

init_db()

# ========== МАРШРУТЫ ==========
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/admin')
def admin():
    return send_from_directory('.', 'admin.html')

@app.route('/health')
def health():
    return "OK", 200

@app.route('/api/get_balance', methods=['POST'])
def get_balance():
    data = request.json
    user_id = data.get('user_id')
    balance = get_user_balance(user_id)
    return jsonify({'balance': balance})

@app.route('/api/deposit', methods=['POST'])
def deposit():
    try:
        data = request.json
        user_id = data.get('user_id')
        username = data.get('username')
        amount = data.get('amount')
        account_id = data.get('account_id')
        photo = data.get('photo')
        
        add_user(user_id, username)
        dep_id = add_deposit(user_id, amount, account_id, photo)
        
        return jsonify({'status': 'ok', 'deposit_id': dep_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    user_id = data.get('user_id')
    if is_admin(user_id):
        return jsonify({'status': 'ok', 'admin': True})
    return jsonify({'status': 'error', 'admin': False}), 401

@app.route('/api/admin/deposits', methods=['GET'])
def admin_deposits():
    user_id = request.args.get('user_id')
    if not is_admin(int(user_id)):
        return jsonify({'status': 'error'}), 401
    
    deposits = get_all_deposits()
    result = []
    for dep in deposits:
        result.append({
            'id': dep[0],
            'user_id': dep[1],
            'amount': dep[2],
            'account_id': dep[3],
            'photo': dep[4],
            'status': dep[5],
            'date': dep[6]
        })
    return jsonify({'deposits': result})

@app.route('/api/admin/approve', methods=['POST'])
def admin_approve():
    data = request.json
    user_id = data.get('user_id')
    dep_id = data.get('dep_id')
    
    if not is_admin(user_id):
        return jsonify({'status': 'error'}), 401
    
    update_deposit_status(dep_id, 'approved')
    return jsonify({'status': 'ok'})

@app.route('/api/admin/reject', methods=['POST'])
def admin_reject():
    data = request.json
    user_id = data.get('user_id')
    dep_id = data.get('dep_id')
    
    if not is_admin(user_id):
        return jsonify({'status': 'error'}), 401
    
    update_deposit_status(dep_id, 'rejected')
    return jsonify({'status': 'ok'})

@app.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    user_id = request.args.get('user_id')
    if not is_admin(int(user_id)):
        return jsonify({'status': 'error'}), 401
    
    stats = get_stats()
    return jsonify(stats)

# ========== ПИНГ ДЛЯ 24/7 (НЕ ДАЁТ ЗАСНУТЬ) ==========
import threading
import requests
import time

def keep_alive():
    while True:
        try:
            requests.get("https://ggkassa-bot.onrender.com/health")
            print("✅ Пинг выполнен")
        except Exception as e:
            print(f"❌ Ошибка пинга: {e}")
        time.sleep(600)  # каждые 10 минут

# Запускаем пинг в отдельном потоке
ping_thread = threading.Thread(target=keep_alive, daemon=True)
ping_thread.start()

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
