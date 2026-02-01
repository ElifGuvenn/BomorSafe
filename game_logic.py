class Oyuncu:
    def __init__(self, isim):
        self.isim = isim
        self.can = 3
        # 3x3 grid, 0: Boş, 1: Bomba
        self.kendi_alani = [[0 for _ in range(3)] for _ in range(3)]
        self.secilen_bomba_sayisi = 0

    def bomba_ekle(self, r, c):
        if self.secilen_bomba_sayisi < 3 and self.kendi_alani[r][c] == 0:
            self.kendi_alani[r][c] = 1
            self.secilen_bomba_sayisi += 1
            return True
        return False


class OyunYonetimi:
    def __init__(self, p1, p2):
        self.p1 = p1
        self.p2 = p2
        self.sira = self.p1
        self.rakip = self.p2
        self.durum = 'P1_SECIM'
        self.acilan_kareler = []

    def sira_degistir(self):
        self.sira, self.rakip = self.rakip, self.sira

    def hamle_yap(self, r, c):
        # Rakibin alanına bakıyoruz
        if self.rakip.kendi_alani[r][c] == 1:
            self.sira.can -= 1
            sonuc = "BOM"
            if self.sira.can <= 0:
                self.durum = 'BITTI'
        else:
            sonuc = "SAFE"

        self.acilan_kareler.append((r, c, sonuc, self.sira.isim))
        return sonuc