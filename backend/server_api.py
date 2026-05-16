import os
from flask import Flask, request, jsonify
from server_db import db_manager

app = Flask(__name__)

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    success, msg = db_manager.create_user(data.get('username'), data.get('password'), data.get('hwid'))
    return jsonify({"success": success, "message": msg})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    success, user_id, msg = db_manager.login(data.get('username'), data.get('password'), data.get('hwid'))
    return jsonify({"success": success, "user_id": user_id, "message": msg})

@app.route('/api/activate', methods=['POST'])
def activate():
    data = request.json
    success, msg = db_manager.activate_key(data.get('key_code'), data.get('user_id'), data.get('hwid'))
    return jsonify({"success": success, "message": msg})

@app.route('/api/check_access', methods=['POST'])
def check_access():
    data = request.json
    has_access = db_manager.check_user_access(data.get('user_id'), data.get('hwid'))
    return jsonify({"success": has_access})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Lumina Backend API on port {port}...")
    app.run(host='0.0.0.0', port=port)
