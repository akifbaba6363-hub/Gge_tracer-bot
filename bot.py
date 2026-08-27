import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# --------------------------------------------------------------------------
# AYARLAR
# --------------------------------------------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# gge-tracker.com'un RESMİ API adresi
API_BASE = "https://api.gge-tracker.com/api/v1"

# Dokümandan doğrulanmış, kesin doğru isim ve değer
SERVER_HEADER_NAME = "gge-server"
SERVER_VALUE = "TR1"

# MİMLİ / DÜŞMAN İTTİFAKLAR LİSTESİ
MIMLI_ITTIFAKLAR = [
    "Grand Alliance",
    "ELITE",
    "DARK OF SOUL",
    "PAYİTAHT",
    "GÖKDOĞAN",
    "VICTORY",
    "SARSILMAZ",
    "WARRIOR",
    "ELITE 2",
]

HEADERS = {
    SERVER_HEADER_NAME: SERVER_VALUE,
    "Accept": "application/json",
}


def _tek_deneme(player_name: str):
    """
    /players/{playerName} adresine tek bir istek atar.
    Başarılıysa (durum, veri) döner, başarısızsa (durum, None) döner.
    """
    url = f"{API_BASE}/players/{requests.utils.quote(player_name)}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
    except requests.exceptions.RequestException as e:
        logger.error(f"Bağlantı Hatası: {e}")
        return "baglanti_hatasi", None

    if res.status_code == 200:
        try:
            return "basarili", res.json()
        except ValueError:
            return "gecersiz_json", None

    if res.status_code == 404:
        return "bulunamadi", None
    if res.status_code == 400:
        return "gecersiz_format", None

    logger.error(f"API hatası: {res.status_code} - {res.text[:300]}")
    return "diger_hata", res.status_code


def get_player_by_name(player_name: str):
    """
    1. Adım: /players/{playerName} ile oyuncunun güncel bilgilerini
    (seviye, güç, güncel ittifak, player_id) çeker.

    Site aramasında büyük/küçük harf farketmiyor; API ise farkedebiliyor.
    Bu yüzden önce yazdığın haliyle deniyoruz, bulunamazsa arka arkaya
    birkaç farklı büyük/küçük harf biçimini otomatik deniyoruz.
    """
    player_name = player_name.strip()

    denenecek_isimler = [
        player_name,             # yazdığın gibi
        player_name.lower(),     # hepsi küçük harf
        player_name.upper(),     # hepsi büyük harf
        player_name.capitalize(),  # İlk harf büyük, gerisi küçük
        player_name.title(),     # Her Kelimenin İlk Harfi Büyük
    ]
    # Aynı olanları listeden çıkar (gereksiz istek atmayalım)
    denenecek_isimler = list(dict.fromkeys(denenecek_isimler))

    data = None
    for isim in denenecek_isimler:
        durum, sonuc = _tek_deneme(isim)
        if durum == "basarili":
            data = sonuc
            break
        if durum == "baglanti_hatasi":
            return "Veri çekilirken bağlantı hatası oluştu."
        if durum == "gecersiz_format":
            return "Oyuncu adı geçersiz formatta."
        if durum == "diger_hata":
            return f"Siteye erişilemedi (Kod: {sonuc})."
        # "bulunamadi" ise sıradaki büyük/küçük harf biçimini dene

    if data is None:
        return f"'{player_name}' TR1 sunucusunda bulunamadı. Yazılışını kontrol edebilirsin reis."

    player_id = data.get("player_id")
    level_value = data.get("level", "Bilinmiyor")
    might_value = data.get("might_current", "Bilinmiyor")
    guncel_ittifak = data.get("alliance_name") or "İttifaksız"

    # --------------------------------------------------------------------
    # 2. Adım: ittifak geçmişi için ayrı istek atıyoruz.
    # --------------------------------------------------------------------
    alliances_text = []
    if player_id:
        hist_url = f"{API_BASE}/updates/players/{player_id}/alliances"
        try:
            hist_res = requests.get(hist_url, headers=HEADERS, timeout=15)
            if hist_res.status_code == 200:
                hist_data = hist_res.json()
                # Liste muhtemelen bir "results" alanının içinde ya da
                # doğrudan bir liste olarak geliyor; ikisini de deniyoruz.
                items = hist_data if isinstance(hist_data, list) else hist_data.get("results", [])
                for item in items[:5]:
                    if isinstance(item, dict):
                        name = (
                            item.get("alliance_name")
                            or item.get("name")
                            or item.get("new_alliance_name")
                            or str(item)
                        )
                        alliances_text.append(name)
                    else:
                        alliances_text.append(str(item))
        except requests.exceptions.RequestException as e:
            logger.error(f"İttifak geçmişi hatası: {e}")

    if not alliances_text:
        alliances_text = [guncel_ittifak] if guncel_ittifak != "İttifaksız" else ["İttifak geçmişi bulunamadı."]

    # Mimli düşman analizi
    bulunan_dusmanlar = []
    for ittifak in alliances_text + [guncel_ittifak]:
        for mimli in MIMLI_ITTIFAKLAR:
            if mimli.lower() in ittifak.lower():
                if mimli not in bulunan_dusmanlar:
                    bulunan_dusmanlar.append(mimli)

    profile_link = f"https://gge-tracker.com/players?player={requests.utils.quote(player_name)}&server=TR1"

    return {
        "name": data.get("player_name") or player_name,
        "level": level_value,
        "might": f"{might_value:,}".replace(",", ".") if isinstance(might_value, (int, float)) else might_value,
        "guncel_ittifak": guncel_ittifak,
        "alliances": alliances_text,
        "dusmanlar": bulunan_dusmanlar,
        "profile_url": profile_link,
        "raw": data,
    }


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot resmi API üzerinden çalışıyor, engellenme yok reis! 🚀\n"
        "Sorgulamak için:\n`/oyuncu OyuncuAdi`\n(Örnek: `/oyuncu SirlusBlaCK`)",
        parse_mode="Markdown",
    )


async def oyuncu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Lütfen bir oyuncu adı girin!\nÖrnek: `/oyuncu SirlusBlaCK`",
            parse_mode="Markdown",
        )
        return

    player_name = " ".join(context.args)
    await update.message.reply_text(f"🔍 TR1 havuzunda '{player_name}' aranıyor ve analiz yapılıyor...")

    result = get_player_by_name(player_name)

    if isinstance(result, str):
        await update.message.reply_text(result)
        return

    alliance_list_text = "\n".join([f"• {item}" for item in result["alliances"]])

    if result["dusmanlar"]:
        dusman_text = "🚨 **DİKKAT! MİMLİ DÜŞMAN TESPİT EDİLDİ!**\nŞu düşman ittifaklarda bulundu: " + ", ".join(
            [f"*{d}*" for d in result["dusmanlar"]]
        )
    else:
        dusman_text = "✅ Son kayıtlarında mimli düşman ittifak bulunamadı."

    message = (
        f"🏰 *TR1 İstihbarat Raporu:* `{result['name']}`\n\n"
        f"⭐ *Seviye:* {result['level']}\n"
        f"⚡ *Güç:* {result['might']}\n"
        f"🛡️ *Güncel İttifak:* {result['guncel_ittifak']}\n\n"
        f"📜 *Son İttifak Geçmişi:*\n{alliance_list_text}\n\n"
        f"{dusman_text}\n\n"
        f"🔗 *Detaylı Profil:* {result['profile_url']}"
    )
    await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)


async def oyuncutest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /players/{playerName} adresinden gelen ham veriyi olduğu gibi gösterir.
    İttifak geçmişi cevabının gerçek yapısını görmek istersen faydalı.
    """
    if not context.args:
        await update.message.reply_text("Örnek: `/oyuncutest SirlusBlaCK`", parse_mode="Markdown")
        return

    player_name = " ".join(context.args)
    result = get_player_by_name(player_name)

    if isinstance(result, str):
        await update.message.reply_text(result)
        return

    import json

    raw_text = json.dumps(result["raw"], ensure_ascii=False, indent=2)
    if len(raw_text) > 3500:
        raw_text = raw_text[:3500] + "\n... (kısaltıldı)"

    await update.message.reply_text(f"```\n{raw_text}\n```", parse_mode="Markdown")


async def gecmistest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    SADECE TEST İÇİN: /updates/players/{playerId}/alliances adresinin
    ham (işlenmemiş) cevabını olduğu gibi gösterir. Bunu bir kere
    çalıştırıp Claude'a gönderince, ittifak geçmişindeki tarih ve isim
    alanlarının gerçek isimlerini görüp kodu kesinleştirebiliriz.
    İşimiz bitince bu komutu kodda silebilirsin.
    """
    if not context.args:
        await update.message.reply_text("Örnek: `/gecmistest SirlusBlaCK`", parse_mode="Markdown")
        return

    player_name = " ".join(context.args)

    # Önce oyuncunun player_id'sini bulalım
    durum, data = _tek_deneme(player_name)
    if durum != "basarili":
        # Büyük/küçük harf varyasyonlarını da dene
        for isim in [player_name.lower(), player_name.upper(), player_name.capitalize(), player_name.title()]:
            durum, data = _tek_deneme(isim)
            if durum == "basarili":
                break

    if durum != "basarili":
        await update.message.reply_text(f"Oyuncu bulunamadı: {player_name}")
        return

    player_id = data.get("player_id")
    if not player_id:
        await update.message.reply_text("player_id alınamadı, oyuncu verisinde bulunamadı.")
        return

    hist_url = f"{API_BASE}/updates/players/{player_id}/alliances"
    try:
        hist_res = requests.get(hist_url, headers=HEADERS, timeout=15)
    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"Bağlantı hatası: {e}")
        return

    import json

    info = f"Durum kodu: {hist_res.status_code}\nAdres: {hist_url}\n\n"
    try:
        raw_text = json.dumps(hist_res.json(), ensure_ascii=False, indent=2)
    except ValueError:
        raw_text = hist_res.text

    if len(raw_text) > 3000:
        raw_text = raw_text[:3000] + "\n... (kısaltıldı)"

    await update.message.reply_text(f"{info}```\n{raw_text}\n```", parse_mode="Markdown")


def main():
    TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")

    if not TOKEN:
        print("HATA: BOT_TOKEN bulunamadı!")
        return

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("oyuncu", oyuncu_command))
    application.add_handler(CommandHandler("oyuncutest", oyuncutest_command))
    application.add_handler(CommandHandler("gecmistest", gecmistest_command))

    print("Bot resmi API modunda aktif...")
    application.run_polling()


if __name__ == "__main__":
    main()
