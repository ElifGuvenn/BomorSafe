# 💣 Bom Bom Bom (Bom or Safe) Multiplayer Oyun Projesi

Bu proje, Python ve Pygame kullanılarak geliştirilmiş, çok oyunculu (multiplayer) bir strateji ve şans oyunudur. İstemci-sunucu (client-server) mimarisiyle çalışır ve oyuncuların lobide buluşup birbirleriyle gerçek zamanlı olarak rekabet etmesini sağlar.

🌐 **[HEMEN OYNA: Oyunun Web Sürümüne Gitmek İçin Tıklayın!](https://playful-pothos-e67468.netlify.app/)**

## 🎮 Bağlantı ve Oynanış Senaryoları

Oyunu oynamak veya test etmek için aşağıdaki senaryolardan size en uygun olanı seçebilirsiniz:

### 1. Web Sürümü (En Kolayı - Kurulum Gerektirmez)
Arkadaşlarınızla hızlıca oynamak için herhangi bir dosya indirmenize veya kurulum yapmanıza gerek yoktur.
* Tarayıcınızdan doğrudan şu adrese gidin: 👉 **https://playful-pothos-e67468.netlify.app/**
* Kendinize bir hesap oluşturun veya giriş yapın.
* Lobiden bir oyun kurun veya açık olan masalara katılarak oynamaya başlayın!

### 2. Geliştirici Kurulumu (Sıfırdan / Yerel Test)
Projeyi kendi bilgisayarınızda (lokal olarak) çalıştırmak ve geliştirmek istiyorsanız aşağıdaki adımları sırasıyla uygulayın:

**Sanal Ortam (Virtual Environment) Oluşturun:** Projeye özel bağımlılıkları izole etmek için bir sanal ortam oluşturun.
python -m venv venv

Sanal Ortamı Aktifleştirin:

Mac / Linux için:
source venv/bin/activate

Windows için:
venv\Scripts\activate

Gerekli Kütüphaneleri Yükleyin: Sanal ortam aktifken projenin ihtiyaç duyduğu kütüphaneleri kurun.
pip install pygame
(Eğer projede bir requirements.txt dosyası varsa pip install -r requirements.txt komutunu kullanabilirsiniz.)

Projeyi Çalıştırma (Sunucu)
Kurulumu tamamladıktan sonra oyuncuların lobide eşleşebilmesi ve oyun odalarının kurulabilmesi için öncelikle ana sunucuyu başlatmanız gerekmektedir:
python server.py
Sunucu başladığında terminalde arka planda çalışarak bağlantıları dinlemeye başlayacaktır.

Bağlantı Senaryoları (Oynanış)
Ana sunucu arka planda çalışırken (python server.py aktifken), yeni bir terminal penceresi açarak (sanal ortamı aktifleştirmeyi unutmayın) aşağıdaki şekillerde istemciyi (oyunu) başlatabilirsiniz.

1. Temel Yerel Test Senaryosu (Localhost)
Tek bilgisayar üzerinden veya aynı Wi-Fi ağına bağlıyken oyunu test etmek için kullanılan temel yöntemdir. network.py dosyasındaki IP adresi yerel ağa (127.0.0.1 veya yerel IPv4) ayarlı olmalıdır.
python main.py
Geliştirici Notu: Tek bilgisayarda testi simüle etmek için birden fazla terminal sekmesi açıp her birinde python main.py yazarak kendinize karşı oynayabilirsiniz.

2. Gelişmiş Uzaktan Bağlantı Senaryosu (İnternet Üzerinden)
Farklı evlerdeki oyuncuların aynı oyuna katılabilmesi için uygulanan senaryodur (Ngrok, Serveo, AWS veya Radmin VPN gibi bir tünelleme aracı gerektirir).

Özelleştirilmiş Ayarlarla Kullanım:
Öncelikle projedeki network.py dosyasını açın ve self.server ile self.port değerlerini sunucuyu kuran kişinin dağıttığı uzak IP adresi ve port numarası ile güncelleyin.

Dosya güncellendikten sonra oyuna giriş yapmak için:
python main.py
Uygulama başladığında karşınıza gelen ekrandan kayıt olup lobiye geçiş yapabilir, odalara katılabilir veya arkadaşlarınıza doğrudan davet atabilirsiniz.
