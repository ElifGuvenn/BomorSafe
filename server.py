import asyncio
import websockets
import json
import sqlite3


# --- VERİTABANI AYARLARI ---
def init_db():
    conn = sqlite3.connect('bombom_users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT UNIQUE, 
                  password TEXT, 
                  wins INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()


init_db()

# --- OYUN DEĞİŞKENLERİ ---
connected_users = {}  # {username: websocket}
active_games = {}  # {game_id: GameState}
game_id_counter = 100


class GameState:
    def __init__(self, p1, p2, size=9):
        self.p1 = p1
        self.p2 = p2
        self.size = size
        self.turn = p1
        self.p1_lives = 3
        self.p2_lives = 3
        # Basitlik için tahtayı şimdilik boş tutuyoruz, detaylı mantık eklenebilir
        self.board = {}
        self.status = "HAZIRLIK"


async def handler(websocket):
    current_user = None
    try:
        async for message in websocket:
            data = json.loads(message)
            komut = data.get("komut")

            # --- KAYIT OL ---
            if komut == "REGISTER":
                user = data.get("username")
                pw = data.get("password")
                conn = sqlite3.connect('bombom_users.db')
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (user, pw))
                    conn.commit()
                    await websocket.send(json.dumps({"type": "REGISTER_SUCCESS"}))
                except sqlite3.IntegrityError:
                    await websocket.send(json.dumps({"type": "ERROR", "msg": "Bu kullanıcı adı dolu!"}))
                finally:
                    conn.close()

            # --- GİRİŞ YAP ---
            elif komut == "LOGIN":
                user = data.get("username")
                pw = data.get("password")
                conn = sqlite3.connect('bombom_users.db')
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, pw))
                result = c.fetchone()
                conn.close()

                if result:
                    current_user = user
                    connected_users[user] = websocket
                    await websocket.send(json.dumps({"type": "LOGIN_SUCCESS", "username": user}))
                else:
                    await websocket.send(json.dumps({"type": "ERROR", "msg": "Kullanıcı adı veya şifre yanlış!"}))

            # --- ODA LİSTESİ ---
            elif komut == "GET_ROOMS":
                # Şimdilik boş oda listesi dönelim veya aktif kullanıcıları
                room_list = [{"host": u, "size": 9} for u in connected_users if u != current_user]
                await websocket.send(json.dumps({"type": "ROOM_LIST", "rooms": room_list}))

            # --- DAVET GÖNDERME (KRİTİK KISIM) ---
            elif komut == "SEND_INVITE":
                target_user = data.get("target")
                # Hedef kullanıcı online mı?
                if target_user in connected_users:
                    target_ws = connected_users[target_user]
                    # Hedefe "Sana davet var" mesajı yolla
                    await target_ws.send(json.dumps({
                        "type": "INVITE_RECEIVED",
                        "from": current_user
                    }))
                    # Gönderene "İletildi" de
                    await websocket.send(json.dumps({"type": "INFO", "msg": "Davet gönderildi!"}))
                else:
                    await websocket.send(json.dumps({"type": "ERROR", "msg": f"{target_user} şu an çevrimdışı."}))

            # --- DAVET KABUL ---
            elif komut == "ACCEPT_INVITE":
                target_user = data.get("target")  # Daveti eden kişi
                # Burada oyun başlatma mantığı devreye girer
                # Şimdilik sadece oyun başladı diyelim
                if target_user in connected_users:
                    p1_ws = connected_users[target_user]
                    p2_ws = websocket

                    # İkisine de oyun başladı de
                    msg = {"type": "GAME_START", "gid": 101, "role": 0, "size": 9}
                    await p1_ws.send(json.dumps(msg))

                    msg["role"] = 1
                    await p2_ws.send(json.dumps(msg))

    except Exception as e:
        print("Hata:", e)
    finally:
        if current_user and current_user in connected_users:
            del connected_users[current_user]


async def main():
    async with websockets.serve(handler, "0.0.0.0", 10000):
        await asyncio.Future()  # Sonsuza kadar çalış


if __name__ == "__main__":
    asyncio.run(main())
