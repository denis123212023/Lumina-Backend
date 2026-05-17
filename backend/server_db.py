import os
import sqlite3
import hashlib
from datetime import datetime

class DBManager:
    def __init__(self):
        # Use RAILWAY_VOLUME_MOUNT_PATH if available to avoid data loss on restarts
        volume_path = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", ".")
        self.db_path = os.path.join(volume_path, "keys.db")
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                hwid TEXT,
                role TEXT DEFAULT 'User',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'User'")
        except sqlite3.OperationalError:
            pass
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_code TEXT UNIQUE NOT NULL,
                user_id INTEGER,
                hwid TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.commit()
        conn.close()

    def hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def set_admin_password(self, password: str):
        pwd_hash = self.hash_password(password)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('admin_password', pwd_hash))
        conn.commit()
        conn.close()

    def check_admin_password(self, password: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', ('admin_password',))
        result = cursor.fetchone()
        conn.close()
        if not result:
            return False
        return self.hash_password(password) == result[0]
        
    def has_admin_password(self) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', ('admin_password',))
        result = cursor.fetchone()
        conn.close()
        return bool(result)

    def create_user(self, username, password, hwid):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            pwd_hash = self.hash_password(password)
            cursor.execute('INSERT INTO users (username, password_hash, hwid) VALUES (?, ?, ?)', (username, pwd_hash, hwid))
            conn.commit()
            conn.close()
            return True, "User created successfully"
        except sqlite3.IntegrityError:
            return False, "Username already exists"
        except Exception as e:
            return False, str(e)

    def login(self, username, password, hwid):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            pwd_hash = self.hash_password(password)
            cursor.execute('SELECT id, hwid FROM users WHERE username = ? AND password_hash = ?', (username, pwd_hash))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                user_id, saved_hwid = result
                # HWID locking check
                if saved_hwid and saved_hwid != hwid:
                    return False, None, "Ошибка HWID: Этот аккаунт привязан к другому ПК."
                return True, user_id, "Success"
            return False, None, "Неверное имя пользователя или пароль"
        except Exception as e:
            return False, None, str(e)

    def activate_key(self, key_code, user_id, hwid):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT id, status, expires_at FROM keys WHERE key_code = ?', (key_code,))
            result = cursor.fetchone()
            
            if not result:
                return False, "Ключ не найден"
            
            key_id, status, expires_at = result
            if status != 'active':
                return False, f"Ключ уже {status}"
            
            if expires_at:
                exp_date = datetime.fromisoformat(expires_at)
                if datetime.now() > exp_date:
                    return False, "Ключ истек"

            # Check if user already has an active key
            cursor.execute('''SELECT COUNT(*) FROM keys WHERE user_id = ? AND status = 'used' AND (expires_at IS NULL OR expires_at > datetime('now'))''', (user_id,))
            if cursor.fetchone()[0] > 0:
                return False, "У вас уже есть активный ключ"
            
            cursor.execute('UPDATE keys SET user_id = ?, hwid = ?, status = ? WHERE id = ?', (user_id, hwid, 'used', key_id))
            
            # Also update user HWID if it was null
            cursor.execute('UPDATE users SET hwid = ? WHERE id = ? AND (hwid IS NULL OR hwid = "")', (hwid, user_id))
            
            conn.commit()
            conn.close()
            return True, "Ключ успешно активирован"
        except Exception as e:
            return False, str(e)

    def check_user_access(self, user_id, hwid):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''SELECT COUNT(*) FROM keys 
                              WHERE user_id = ? AND hwid = ? AND status = 'used' 
                              AND (expires_at IS NULL OR expires_at > datetime('now'))''', (user_id, hwid))
            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        except Exception:
            return False

    def check_hwid_access(self, hwid):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''SELECT COUNT(*) FROM keys 
                              WHERE hwid = ? AND status = 'used' 
                              AND (expires_at IS NULL OR expires_at > datetime('now'))''', (hwid,))
            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        except Exception:
            return False

    def add_key(self, key_code, expires_at=None):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('INSERT INTO keys (key_code, expires_at, status) VALUES (?, ?, ?)', (key_code, expires_at, 'active'))
            conn.commit()
            conn.close()
            return True, "Key added successfully"
        except sqlite3.IntegrityError:
            return False, "Key already exists"
        except Exception as e:
            return False, str(e)

    def get_user_role_and_uid_by_hwid(self, hwid):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT role, id FROM users WHERE hwid = ?', (hwid,))
            result = cursor.fetchone()
            conn.close()
            if result:
                return result[0], result[1]
            return "User", 1
        except Exception:
            return "User", 1

    def change_user_role(self, username, role):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET role = ? WHERE username = ?', (role, username))
            conn.commit()
            success = cursor.rowcount > 0
            conn.close()
            return success, "Роль успешно обновлена" if success else "Пользователь не найден"
        except Exception as e:
            return False, str(e)

db_manager = DBManager()
