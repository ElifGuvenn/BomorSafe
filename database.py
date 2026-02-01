import sqlite3
import hashlib

class Veritabani:
    def __init__(self):
        self.conn = sqlite3.connect("bombom_users.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.tablo_olustur()

    def tablo_olustur(self):
        """Kullanıcı tablosunu oluşturur"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                wins INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

    def sifrele(self, password):
        """Şifreyi SHA256 ile hashler (Güvenlik için)"""
        return hashlib.sha256(password.encode()).hexdigest()

    def kullanici_kayit(self, username, password):
        """Yeni kullanıcı kaydeder"""
        if len(password) < 8:
            return "HATA: Şifre en az 8 karakter olmalı!"

        hashed_pw = self.sifrele(password)
        try:
            self.cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
            self.conn.commit()
            return "BAŞARILI"
        except sqlite3.IntegrityError:
            return "HATA: Bu kullanıcı adı zaten alınmış."

    def kullanici_giris(self, username, password):
        """Giriş kontrolü yapar"""
        hashed_pw = self.sifrele(password)
        self.cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed_pw))
        user = self.cursor.fetchone()

        if user:
            return True
        else:
            return False

    def skor_guncelle(self, username):
        """Kazananın skorunu artırır"""
        self.cursor.execute("UPDATE users SET wins = wins + 1 WHERE username = ?", (username,))
        self.conn.commit()