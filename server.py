
import asyncio
import websockets
import json
import sqlite3
import random
from datetime import datetime


# --- VERİTABANI ---
def init_db():
    conn = sqlite3.connect('bombom_users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT UNIQUE, 
                  password TEXT, 
                  wins INTEGER DEFAULT 0,
                  created_at TEXT)''')
    conn.commit()
    conn.close()


init_db()

connected_users = {}  # {username: websocket}
active_games = {}  # {game_id: GameState}
pending_invites = {}  # {to_user: {from_user, size}}
waiting_rooms = {}  # {username: size} - Oyun oluşturanlar
game_id_counter = 100


class GameState:
    def __init__(self, p1_name, p2_name, size=9):
        self.p1_name = p1_name
        self.p2_name = p2_name
        self.size = size
        self.rows = size // 3

        # 0: Boş, 1: Bomba
        self.p1_board = [[0 for _ in range(3)] for _ in range(self.rows)]
        self.p2_board = [[0 for _ in range(3)] for _ in range(self.rows)]

        self.p1_bombs_placed = 0
        self.p2_bombs_placed = 0

        self.p1_ready = False
        self.p2_ready = False

        self.p1_lives = 3
        self.p2_lives = 3

        self.turn = p1_name  # Sıra kimde
        self.status = "HAZIRLIK"  # HAZIRLIK -> GERISAYIM -> OYNANIYOR -> BITTI

        # Açılan kareler
        self.revealed = []

    def place_bomb(self, username, r, c):
        if self.status != "HAZIRLIK":
            return False

        if username == self.p1_name:
            if self.p1_bombs_placed < 3 and self.p1_board[r][c] == 0:
                self.p1_board[r][c] = 1
                self.p1_bombs_placed += 1
                if self.p1_bombs_placed == 3:
                    self.p1_ready = True
                return True
        elif username == self.p2_name:
            if self.p2_bombs_placed < 3 and self.p2_board[r][c] == 0:
                self.p2_board[r][c] = 1
                self.p2_bombs_placed += 1
                if self.p2_bombs_placed == 3:
                    self.p2_ready = True
                return True
        return False

    def check_start(self):
        if self.p1_ready and self.p2_ready:
            self.status = "GERISAYIM"
            return True
        return False

    def make_move(self, username, r, c):
        # Oyun oynuyor mu ve sıra bu kullanıcıda mı kontrol et
        if self.status != "OYNANIYOR":
            return None

        if username != self.turn:
            return None  # Sıra sende değil

        # Rakip tahtasına bak
        opponent_board = self.p2_board if username == self.p1_name else self.p1_board

        result = "SAFE"
        if opponent_board[r][c] == 1:
            result = "BOM"
            if username == self.p1_name:
                self.p1_lives -= 1
            else:
                self.p2_lives -= 1

        self.revealed.append({"r": r, "c": c, "type": result, "by": username})

        # Sıra değiştir
        self.turn = self.p2_name if username == self.p1_name else self.p1_name

        # Oyun bitti mi?
        if self.p1_lives <= 0 or self.p2_lives <= 0:
            self.status = "BITTI"

        return result


async def handler(websocket):
    current_user = None
    try:
        async for message in websocket:
            data = json.loads(message)
            komut = data.get("komut")

            # --- GİRİŞ ---
            if komut == "LOGIN":
                user = data.get("username")
                pw = data.get("password")

                if not user or not pw:
                    await websocket.send(json.dumps({"type": "ERROR", "msg": "Kullanıcı adı ve şifre gerekli!"}))
                    continue

                conn = sqlite3.connect('bombom_users.db')
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, pw))
                result = c.fetchone()
                conn.close()

                if result:
                    # Zaten bağlıysa eski bağlantıyı kapat
                    if user in connected_users:
                        try:
                            await connected_users[user].close()
                        except:
                            pass

                    current_user = user
                    connected_users[user] = websocket
                    await websocket.send(json.dumps({"type": "LOGIN_SUCCESS", "username": user}))
                else:
                    await websocket.send(json.dumps({"type": "ERROR", "msg": "Hatalı kullanıcı adı veya şifre!"}))

            # --- KAYIT ---
            elif komut == "REGISTER":
                user = data.get("username")
                pw = data.get("password")

                if not user or not pw:
                    await websocket.send(json.dumps({"type": "ERROR", "msg": "Tüm alanları doldur!"}))
                    continue

                if len(pw) < 8:
                    await websocket.send(json.dumps({"type": "ERROR", "msg": "Şifre en az 8 karakter olmalı!"}))
                    continue

                conn = sqlite3.connect('bombom_users.db')
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)",
                              (user, pw, datetime.now().isoformat()))
                    conn.commit()
                    await websocket.send(json.dumps({"type": "REGISTER_SUCCESS"}))
                except sqlite3.IntegrityError:
                    await websocket.send(json.dumps({"type": "ERROR", "msg": "Bu kullanıcı adı zaten alınmış!"}))
                finally:
                    conn.close()

            # --- ODALAR LİSTESİ ---
            elif komut == "GET_ROOMS":
                rooms = []
                for host, size in waiting_rooms.items():
                    if host != current_user and host in connected_users:
                        rooms.append({"host": host, "size": size})

                await websocket.send(json.dumps({"type": "ROOM_LIST", "rooms": rooms}))

            # --- ODA OLUŞTUR ---
            elif komut == "CREATE_ROOM":
                size = int(data.get("size", 9))
                waiting_rooms[current_user] = size
                await websocket.send(json.dumps({"type": "ROOM_CREATED", "size": size}))

            # --- ODADAN AYRIL ---
            elif komut == "LEAVE_ROOM":
                if current_user in waiting_rooms:
                    del waiting_rooms[current_user]

            # --- KATILMA İSTEĞİ ---
            elif komut == "JOIN_REQUEST":
                host = data.get("host")

                if host in connected_users and host in waiting_rooms:
                    # Host'a bildir
                    await connected_users[host].send(json.dumps({
                        "type": "INVITE_RECEIVED",
                        "from": current_user,
                        "size": waiting_rooms[host]
                    }))

                    # İsteği sakla
                    pending_invites[host] = {"from": current_user, "size": waiting_rooms[host]}

            # --- DİREKT DAVET ---
            elif komut == "SEND_INVITE":
                target = data.get("target")
                size = int(data.get("size", 9))

                if target in connected_users:
                    await connected_users[target].send(json.dumps({
                        "type": "INVITE_RECEIVED",
                        "from": current_user,
                        "size": size
                    }))

                    pending_invites[target] = {"from": current_user, "size": size}
                    await websocket.send(json.dumps({"type": "INVITE_SENT"}))
                else:
                    await websocket.send(json.dumps({"type": "ERROR", "msg": "Kullanıcı bulunamadı!"}))

            # --- DAVETI KABUL ET ---
            elif komut == "ACCEPT_INVITE":
                target = data.get("target")  # Davet eden
                size = int(data.get("size", 9))

                if target not in connected_users:
                    await websocket.send(json.dumps({"type": "ERROR", "msg": "Kullanıcı çevrimdışı!"}))
                    continue

                # OYUNU BAŞLAT
                global game_id_counter
                gid = game_id_counter
                game_id_counter += 1

                # Yeni oyun objesi
                active_games[gid] = GameState(target, current_user, size)

                # Odayı temizle
                if target in waiting_rooms:
                    del waiting_rooms[target]
                if current_user in waiting_rooms:
                    del waiting_rooms[current_user]

                # İki tarafa da bildir
                msg = {"type": "GAME_INIT", "gid": gid, "p1": target, "p2": current_user, "size": size}

                await connected_users[target].send(json.dumps(msg))
                await websocket.send(json.dumps(msg))

            # --- DAVETI REDDET ---
            elif komut == "DECLINE_INVITE":
                target = data.get("target")
                if target in connected_users:
                    await connected_users[target].send(json.dumps({
                        "type": "INVITE_DECLINED",
                        "from": current_user
                    }))

            # --- BOMBA YERLEŞTİR ---
            elif komut == "PLACE_BOMB":
                gid = data.get("gid")
                r = data.get("r")
                c = data.get("c")

                if gid in active_games:
                    game = active_games[gid]
                    success = game.place_bomb(current_user, r, c)

                    if success:
                        # Sadece kendine bildir
                        await websocket.send(json.dumps({"type": "BOMB_PLACED", "r": r, "c": c}))

                        # Her iki oyuncu da hazırsa geri sayım başlat
                        if game.check_start():
                            start_msg = {"type": "START_COUNTDOWN"}

                            if game.p1_name in connected_users:
                                await connected_users[game.p1_name].send(json.dumps(start_msg))
                            if game.p2_name in connected_users:
                                await connected_users[game.p2_name].send(json.dumps(start_msg))

                            # 3.5 saniye bekle
                            await asyncio.sleep(3.5)
                            game.status = "OYNANIYOR"

                            play_msg = {"type": "GAME_STARTED_NOW", "turn": game.turn}

                            if game.p1_name in connected_users:
                                await connected_users[game.p1_name].send(json.dumps(play_msg))
                            if game.p2_name in connected_users:
                                await connected_users[game.p2_name].send(json.dumps(play_msg))

            # --- HAMLE YAP ---
            elif komut == "GAME_MOVE":
                gid = data.get("gid")
                r = data.get("r")
                c = data.get("c")

                if gid in active_games:
                    game = active_games[gid]
                    res = game.make_move(current_user, r, c)

                    if res:
                        update_msg = {
                            "type": "UPDATE_BOARD",
                            "r": r, "c": c,
                            "res": res,
                            "turn": game.turn,
                            "p1_lives": game.p1_lives,
                            "p2_lives": game.p2_lives,
                            "opener": current_user
                        }

                        # İki tarafa da gönder
                        if game.p1_name in connected_users:
                            await connected_users[game.p1_name].send(json.dumps(update_msg))
                        if game.p2_name in connected_users:
                            await connected_users[game.p2_name].send(json.dumps(update_msg))

                        # Oyun bitti mi?
                        if game.status == "BITTI":
                            winner = game.p1_name if game.p1_lives > 0 else game.p2_name

                            # Veritabanında kazananı güncelle
                            conn = sqlite3.connect('bombom_users.db')
                            c = conn.cursor()
                            c.execute("UPDATE users SET wins = wins + 1 WHERE username = ?", (winner,))
                            conn.commit()
                            conn.close()

                            end_msg = {"type": "GAME_OVER", "winner": winner}

                            if game.p1_name in connected_users:
                                await connected_users[game.p1_name].send(json.dumps(end_msg))
                            if game.p2_name in connected_users:
                                await connected_users[game.p2_name].send(json.dumps(end_msg))

                            # Oyunu sil
                            del active_games[gid]

    except websockets.exceptions.ConnectionClosed:
        print(f"Bağlantı kapandı: {current_user}")
    except Exception as e:
        print(f"Hata ({current_user}): {e}")
    finally:
        # Temizlik
        if current_user:
            if current_user in connected_users:
                del connected_users[current_user]
            if current_user in waiting_rooms:
                del waiting_rooms[current_user]


async def main():
    print("Server başlatılıyor...")
    async with websockets.serve(handler, "0.0.0.0", 10000):
        print("Server 10000 portunda çalışıyor!")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
