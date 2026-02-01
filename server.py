import asyncio
import websockets
import json
import sqlite3
import random


# --- VERİTABANI ---
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

connected_users = {}  # {username: websocket}
active_games = {}  # {game_id: GameState}
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

        # Açılan kareler: (r, c, type, who_opened)
        self.revealed = []

    def place_bomb(self, username, r, c):
        if self.status != "HAZIRLIK": return False

        if username == self.p1_name:
            if self.p1_bombs_placed < 3 and self.p1_board[r][c] == 0:
                self.p1_board[r][c] = 1
                self.p1_bombs_placed += 1
                if self.p1_bombs_placed == 3: self.p1_ready = True
                return True
        elif username == self.p2_name:
            if self.p2_bombs_placed < 3 and self.p2_board[r][c] == 0:
                self.p2_board[r][c] = 1
                self.p2_bombs_placed += 1
                if self.p2_bombs_placed == 3: self.p2_ready = True
                return True
        return False

    def check_start(self):
        if self.p1_ready and self.p2_ready:
            self.status = "GERISAYIM"
            return True
        return False

    def make_move(self, username, r, c):
        if self.status != "OYNANIYOR" or username != self.turn:
            return None

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

            if komut == "LOGIN":
                user = data.get("username")
                pw = data.get("password")
                conn = sqlite3.connect('bombom_users.db')
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, pw))
                if c.fetchone():
                    current_user = user
                    connected_users[user] = websocket
                    await websocket.send(json.dumps({"type": "LOGIN_SUCCESS", "username": user}))
                else:
                    await websocket.send(json.dumps({"type": "ERROR", "msg": "Hatalı giriş!"}))
                conn.close()

            elif komut == "REGISTER":
                user = data.get("username")
                pw = data.get("password")
                conn = sqlite3.connect('bombom_users.db')
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (user, pw))
                    conn.commit()
                    await websocket.send(json.dumps({"type": "REGISTER_SUCCESS"}))
                except:
                    await websocket.send(json.dumps({"type": "ERROR", "msg": "Kullanıcı adı dolu!"}))
                conn.close()

            elif komut == "GET_ROOMS":
                # Basit oda listesi (Host olanlar)
                # Not: Gerçek bir oda listesi için ayrı yapı kurulabilir ama şimdilik online kullanıcıları dönüyoruz
                users = [u for u in connected_users if u != current_user]
                await websocket.send(
                    json.dumps({"type": "ROOM_LIST", "rooms": [{"host": u, "size": 9} for u in users]}))

            elif komut == "SEND_INVITE":
                target = data.get("target")
                size = int(data.get("size", 9))  # Varsayılan 9
                if target in connected_users:
                    await connected_users[target].send(json.dumps({
                        "type": "INVITE_RECEIVED", "from": current_user, "size": size
                    }))

            elif komut == "ACCEPT_INVITE":
                target = data.get("target")  # Davet eden
                size = int(data.get("size", 9))

                # OYUNU BAŞLAT
                global game_id_counter
                gid = game_id_counter
                game_id_counter += 1

                # Yeni oyun objesi oluştur
                active_games[gid] = GameState(target, current_user, size)

                # İki tarafa da bildir
                msg = {"type": "GAME_INIT", "gid": gid, "p1": target, "p2": current_user, "size": size}

                if target in connected_users:
                    await connected_users[target].send(json.dumps(msg))
                await websocket.send(json.dumps(msg))

            elif komut == "PLACE_BOMB":
                gid = data.get("gid")
                r = data.get("r")
                c = data.get("c")

                if gid in active_games:
                    game = active_games[gid]
                    success = game.place_bomb(current_user, r, c)

                    # Sadece bana bombayı koyduğumu söyle (Rakip görmemeli)
                    if success:
                        await websocket.send(json.dumps({"type": "BOMB_PLACED", "r": r, "c": c}))

                        # Eğer herkes hazırsa Geri Sayımı başlat
                        if game.check_start():
                            # İki tarafa da geri sayım gönder
                            start_msg = {"type": "START_COUNTDOWN"}
                            if game.p1_name in connected_users:
                                await connected_users[game.p1_name].send(json.dumps(start_msg))
                            if game.p2_name in connected_users:
                                await connected_users[game.p2_name].send(json.dumps(start_msg))

                            # 3 saniye bekle ve oyunu başlat (Async sleep)
                            await asyncio.sleep(3.5)
                            game.status = "OYNANIYOR"

                            play_msg = {"type": "GAME_STARTED_NOW", "turn": game.turn}
                            if game.p1_name in connected_users:
                                await connected_users[game.p1_name].send(json.dumps(play_msg))
                            if game.p2_name in connected_users:
                                await connected_users[game.p2_name].send(json.dumps(play_msg))

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

                        # İki tarafa da güncelleme gönder
                        if game.p1_name in connected_users:
                            await connected_users[game.p1_name].send(json.dumps(update_msg))
                        if game.p2_name in connected_users:
                            await connected_users[game.p2_name].send(json.dumps(update_msg))

                        if game.status == "BITTI":
                            end_msg = {"type": "GAME_OVER",
                                       "winner": game.p1_name if game.p1_lives > 0 else game.p2_name}
                            if game.p1_name in connected_users:
                                await connected_users[game.p1_name].send(json.dumps(end_msg))
                            if game.p2_name in connected_users:
                                await connected_users[game.p2_name].send(json.dumps(end_msg))

    except Exception as e:
        print("Hata:", e)
    finally:
        if current_user in connected_users:
            del connected_users[current_user]


async def main():
    async with websockets.serve(handler, "0.0.0.0", 10000):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
