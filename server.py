import asyncio
import os
import websockets
import json
from game_logic import OyunYonetimi, Oyuncu
from database import Veritabani

# --- GLOBAL DEĞİŞKENLER ---
db = Veritabani()
connected_clients = {}  # {websocket: username}
username_to_ws = {}  # {username: websocket}
acik_masalar = {}  # {username: grid_size}
aktif_oyunlar = {}  # {game_id: OyunYonetimi}
oyun_id_sayaci = 0


async def broadcast_to_user(username, message_dict):
    """Belirli bir kullanıcıya JSON mesaj gönderir"""
    if username in username_to_ws:
        try:
            ws = username_to_ws[username]
            await ws.send(json.dumps(message_dict))
        except:
            pass


def get_game_state_dict(oyun, gid):
    """Oyun durumunu JSON formatına hazırlar"""
    return {
        "type": "GAME_STATE",
        "durum": oyun.durum,
        "gid": gid,
        "sira": oyun.sira.isim,
        "p1": {
            "isim": oyun.p1.isim,
            "can": oyun.p1.can,
            "hazir": oyun.p1.hazir,
            "secilen_bomba": oyun.p1.secilen_bomba_sayisi
        },
        "p2": {
            "isim": oyun.p2.isim,
            "can": oyun.p2.can,
            "hazir": oyun.p2.hazir,
            "secilen_bomba": oyun.p2.secilen_bomba_sayisi
        },
        "acilan_kareler": oyun.acilan_kareler,
        "rows": oyun.rows,  # Dinamik satır sayısı
        "cols": 3
    }


async def handler(websocket):
    global oyun_id_sayaci
    my_username = ""

    try:
        async for message in websocket:
            data = json.loads(message)  # Web'den gelen JSON'u oku
            komut = data.get("komut")

            # --- GİRİŞ / KAYIT ---
            if komut == "LOGIN":
                u, p = data["username"], data["password"]
                if db.kullanici_giris(u, p):
                    my_username = u
                    connected_clients[websocket] = u
                    username_to_ws[u] = websocket
                    await websocket.send(json.dumps({"type": "LOGIN_SUCCESS", "username": u}))
                else:
                    await websocket.send(json.dumps({"type": "ERROR", "msg": "Hatalı Giriş!"}))

            elif komut == "REGISTER":
                u, p = data["username"], data["password"]
                res = db.kullanici_kayit(u, p)
                await websocket.send(json.dumps({"type": "INFO", "msg": res}))

            # --- ODA YÖNETİMİ ---
            elif komut == "CREATE_ROOM":
                size = int(data.get("size", 9))
                acik_masalar[my_username] = size
                await websocket.send(json.dumps({"type": "ROOM_CREATED", "size": size}))

            elif komut == "GET_ROOMS":
                rooms = [{"host": k, "size": v} for k, v in acik_masalar.items() if k != my_username]
                await websocket.send(json.dumps({"type": "ROOM_LIST", "rooms": rooms}))

            elif komut == "JOIN_REQUEST":
                target = data["target"]
                await broadcast_to_user(target, {"type": "JOIN_REQ", "from": my_username})

            elif komut == "SEND_INVITE":
                target_user = data.get("target")
                target_ws = connected_users.get(target_user)

                if target_ws:
                    # Hedef kullanıcıya davet mesajı ilet
                    await target_ws.send(json.dumps({
                        "type": "INVITE_RECEIVED",
                        "from": username
                    }))
                else:
                    # Kullanıcı yoksa hata ver
                    await websocket.send(json.dumps({
                        "type": "ERROR",
                        "msg": f"Kullanıcı bulunamadı: {target_user}"
                    }))

            elif komut == "ACCEPT_INVITE":
                rakip = data["target"]

                # Oyun boyutunu belirle
                size = 9
                if my_username in acik_masalar:
                    size = acik_masalar[my_username]
                elif rakip in acik_masalar:
                    size = acik_masalar[rakip]

                # Oyunu Kur
                oyun_id_sayaci += 1
                gid = oyun_id_sayaci
                p1 = Oyuncu(rakip)
                p2 = Oyuncu(my_username)

                # Python Logic'i Başlat
                aktif_oyunlar[gid] = OyunYonetimi(p1, p2, size)

                # Masaları kaldır
                acik_masalar.pop(my_username, None)
                acik_masalar.pop(rakip, None)

                # Başlat Mesajı (Her iki tarafa)
                start_msg_p1 = {"type": "GAME_START", "gid": gid, "role": 0, "size": size, "opponent": my_username}
                start_msg_p2 = {"type": "GAME_START", "gid": gid, "role": 1, "size": size, "opponent": rakip}

                await broadcast_to_user(rakip, start_msg_p1)
                await broadcast_to_user(my_username, start_msg_p2)

            # --- OYUN İÇİ ---
            elif komut == "GAME_MOVE":
                gid = data["gid"]
                r, c = data["r"], data["c"]

                if gid in aktif_oyunlar:
                    oyun = aktif_oyunlar[gid]
                    me = oyun.p1 if my_username == oyun.p1.isim else oyun.p2

                    # 1. HAZIRLIK EVRESİ
                    if oyun.durum == 'HAZIRLIK':
                        if not me.hazir:
                            if me.bomba_ekle(r, c):
                                if me.secilen_bomba_sayisi == 3:
                                    me.hazir = True

                                # Eğer ikisi de hazırsa oyunu başlat
                                if oyun.p1.hazir and oyun.p2.hazir:
                                    oyun.durum = 'OYNANIYOR'
                                    oyun.sira = oyun.p1  # İlk sıra P1'de

                    # 2. OYNAMA EVRESİ
                    elif oyun.durum == 'OYNANIYOR':
                        if oyun.sira.isim == my_username:
                            oyun.hamle_yap(r, c)
                            if oyun.durum != 'BITTI':
                                oyun.sira_degistir()

                    # HER HAMLEDEN SONRA DURUM GÜNCELLEMESİ YOLLA
                    state = get_game_state_dict(oyun, gid)

                    # Size özel veri ekle (Kendi bombalarını gör, rakibinkini görme)
                    state_p1 = state.copy()
                    state_p1["my_board"] = oyun.p1.kendi_alani  # P1 kendi bombalarını görsün

                    state_p2 = state.copy()
                    state_p2["my_board"] = oyun.p2.kendi_alani  # P2 kendi bombalarını görsün

                    await broadcast_to_user(oyun.p1.isim, state_p1)
                    await broadcast_to_user(oyun.p2.isim, state_p2)

    except websockets.exceptions.ConnectionClosed:
        print(f"{my_username} bağlantısı koptu.")
    except Exception as e:
        print(f"Hata oluştu: {e}")
    finally:
        # Kullanıcı çıktığında temizlik yap
        if my_username:
            if my_username in username_to_ws:
                del username_to_ws[my_username]
            if websocket in connected_clients:
                del connected_clients[websocket]
            if my_username in acik_masalar:
                del acik_masalar[my_username]


async def main():
    # Bulut sunucunun verdiği portu al, yoksa 8765 kullan
    port = int(os.environ.get("PORT", 8765))

    # "0.0.0.0" dış dünyaya açılmak demektir
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"🔥 SERVER ÇALIŞIYOR (Port: {port})...")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
