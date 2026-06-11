import os
import time
import secrets
from flask import Flask, request, jsonify, send_file
from server_db import db_manager

app = Flask(__name__)

# ── Launch tokens (одноразовые токены запуска) ───────────────────────────────
# { token: { "hwid": ..., "expires": timestamp } }
_launch_tokens: dict[str, dict] = {}
_TOKEN_TTL = 120.0  # 2 минуты на использование


def _cleanup_tokens():
    now = time.time()
    dead = [t for t, v in _launch_tokens.items() if now > v["expires"]]
    for t in dead:
        del _launch_tokens[t]


@app.route('/api/launch/token', methods=['POST'])
def issue_launch_token():
    """Лаунчер запрашивает одноразовый токен перед запуском Minecraft."""
    data = request.json or {}
    hwid = (data.get('hwid') or '').strip()
    if not hwid:
        return jsonify({"success": False, "message": "hwid required"}), 400

    # Проверяем что у пользователя есть доступ
    if not db_manager.check_hwid_access(hwid):
        return jsonify({"success": False, "message": "No access"}), 403

    _cleanup_tokens()
    token = secrets.token_hex(32)
    _launch_tokens[token] = {"hwid": hwid, "expires": time.time() + _TOKEN_TTL}
    return jsonify({"success": True, "token": token})


@app.route('/api/launch/verify', methods=['POST'])
def verify_launch_token():
    """Мод проверяет токен при старте. Токен одноразовый — удаляется после проверки."""
    data = request.json or {}
    token = (data.get('token') or '').strip()
    hwid  = (data.get('hwid')  or '').strip()

    if not token or not hwid:
        return jsonify({"valid": False}), 400

    _cleanup_tokens()
    entry = _launch_tokens.get(token)
    if not entry:
        return jsonify({"valid": False})

    if entry["hwid"] != hwid:
        return jsonify({"valid": False})

    # Одноразовый — удаляем
    del _launch_tokens[token]
    return jsonify({"valid": True})
# ─────────────────────────────────────────────────────────────────────────────

# ── Globals — активные пользователи LuminaBETA ──────────────────────────────
# { "PlayerName": last_seen_timestamp }
_globals_players: dict[str, float] = {}
_GLOBALS_TTL = 90.0  # секунды — если игрок не пингует дольше, он считается оффлайн


def _cleanup_globals():
    now = time.time()
    dead = [n for n, ts in _globals_players.items() if now - ts > _GLOBALS_TTL]
    for n in dead:
        del _globals_players[n]


@app.route('/addPlayer', methods=['POST', 'GET'])
def globals_add():
    name = request.args.get('name') or (request.json or {}).get('name', '')
    name = (name or '').strip()
    if not name:
        return jsonify({"success": False, "message": "name required"}), 400
    _globals_players[name.lower()] = time.time()
    return jsonify({"success": True})


@app.route('/removePlayer', methods=['DELETE', 'POST', 'GET'])
def globals_remove():
    name = request.args.get('name') or (request.json or {}).get('name', '')
    name = (name or '').strip()
    if not name:
        return jsonify({"success": False, "message": "name required"}), 400
    _globals_players.pop(name.lower(), None)
    return jsonify({"success": True})


@app.route('/isClientUser', methods=['GET', 'POST'])
def globals_check():
    name = request.args.get('name') or request.args.get('player') or \
           request.args.get('nickname') or request.args.get('username') or \
           (request.json or {}).get('name', '')
    name = (name or '').strip()
    if not name:
        return jsonify(False)
    _cleanup_globals()
    return jsonify(name.lower() in _globals_players)


@app.route('/players', methods=['GET'])
def globals_list():
    _cleanup_globals()
    return jsonify(list(_globals_players.keys()))
# ─────────────────────────────────────────────────────────────────────────────

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

@app.route('/api/download/mod', methods=['GET'])
def download_mod():
    mod_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mod.jar")
    if os.path.exists(mod_path):
        return send_file(mod_path, as_attachment=True)
    return jsonify({"success": False, "message": "Mod not found on server"}), 404

@app.route('/api/mod_verify', methods=['POST'])
def mod_verify():
    data = request.json
    hwid = data.get('hwid')
    if not hwid:
        return jsonify({"success": False, "message": "Missing HWID"})
    has_access = db_manager.check_hwid_access(hwid)
    role = "User"
    uid = 1
    if has_access:
        role, uid = db_manager.get_user_role_and_uid_by_hwid(hwid)
    mod_version = db_manager.get_setting("mod_version", "1")
    return jsonify({"success": has_access, "role": role, "uid": uid, "mod_version": mod_version})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Lumina Backend API on port {port}...")
    app.run(host='0.0.0.0', port=port)
