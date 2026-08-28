import os
import logging
from datetime import datetime

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

API_BASE = "https://api.gge-tracker.com/api/v1"
SERVER_HEADER_NAME = "gge-server"
SERVER_VALUE = "TR1"

# MİMLİ / DÜŞMAN İTTİFAKLAR LİSTESİ (güncellendi)
MIMLI_ITTIFAKLAR = [
    # 1-8
    "Grand Alliance",
    "ELITE",
    "DARK OF SOUL",
    "PAYİTAHT",
    "GÖKDOĞAN",          # API'de [GÖKDOĞAN] gelebilir
    "VICTORY",
    "SARSILMAZ",
    "WARRIOR",
    # 11
    "ANKEBUT",
    # 14
    "ELITE 2",
    # 16
    "Winged Hussars",
    # 17
    "DEVLET-İ ALİYYE",
    # 18
    "...TURAN...",
    # 21
    "HEYULA",
    # 30
    "SUMUD FİLOSU",
]

# Kaç tane geçmiş ittifak gösterilecek
GECMIS_ITTIFAK_SAYISI = 5

HEADERS = {
    SERVER_HEADER_NAME: SERVER_VALUE,
    "Accept": "application/json",
}


def temizle_isim(isim: str) -> str:
    """İttifak isimlerindeki süslemeleri (【】~[] ) ve fazla boşlukları temizler."""
    if not isim:
        return ""
    isim = isim.replace("【", "").replace("】", "").replace("~", "")
    isim = isim.replace("[", "").replace("]", "")   # köşeli parantezleri temizle
    return " ".join(isim.split())


def tarihi_formatla(iso_tarih: str) -> str:
    """'2026-08-03T19:10:40.989Z' -> '03.08.2026' """
    try:
        dt = datetime.strptime(iso_tarih[:10], "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return iso_tarih or "Bilinmiyor"


def mimli_mi(ittifak_adi: str) -> bool:
    # Tüm boşlukları kaldırıp küçük harfe çevirerek karşılaştır
    temiz = temizle_isim(ittifak_adi).lower().replace(" ", "")
    for mimli in MIMLI_ITTIFAKLAR:
        mimli_temiz = temizle_isim(mimli).lower().replace(" ", "")
        if mimli_temiz and (mimli_temiz in temiz or temiz in mimli_temiz):
            return True
    return False


def _tek_deneme(player_name: str):
    """/players/{playerName} adresine tek bir istek atar."""
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


def oyuncuyu_bul(player_name: str):
    """
    Büyük/küçük harf farketmeksizin oyuncuyu bulmaya çalışır.
    Döner: ("basarili", data) ya da (hata_metni, None)
    """
    player_name = player_name.strip()
    denenecek_isimler = list(dict.fromkeys([
        player_name,
        player_name.lower(),
        player_name.upper(),
        player_name.capitalize(),
        player_name.title(),
    ]))

    for isim in denenecek_isimler:
        durum, sonuc = _tek_deneme(isim)
        if durum == "basarili":
            return "basarili", sonuc
        if durum == "baglanti_hatasi":
            return "Veri çekilirken bağlantı hatası oluştu.", None
        if durum == "gecersiz_format":
            return "Oyuncu adı geçersiz formatta.", None
        if durum == "diger_hata":
            return f"Siteye erişilemedi (Kod: {sonuc}).", None
        # "bulunamadi" ise sıradaki büyük/küçük harf biçimini dene

    return f"'{player_name}' TR1 sunucusunda bulunamadı. Yazılışını kontrol edebilirsin reis.", None


def ittifak_gecmisini_getir(player_id: str):
    """
    /updates/players/{playerId}/alliances adresinden ittifak geçmişini çeker.
    Son GECMIS_ITTIFAK_SAYISI kadar farklı (benzersiz) ittifağı, tarihleriyle
    birlikte, en yeniden en eskiye doğru sıralı liste olarak döner:
        [{"isim": "...", "tarih": "03.08.2026"}, ...]
    """
    url = f"{API_BASE}/updates/players/{player_id}/alliances"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
    except requests.exceptions.RequestException as e:
        logger.error(f"İttifak geçmişi bağlantı hatası: {e}")
        return []

    if res.status_code != 200:
        logger.error(f"İttifak geçmişi API hatası: {res.status_code}")
        return []

    try:
        data = res.json()
    except ValueError:
        return []

    updates = data.get("updates", [])

    sonuc = []
    gorulen_isimler = set()

    for kayit in updates:
        yeni_isim = kayit.get("original_new_alliance_name") or kayit.get("new_alliance_name")
        if not yeni_isim:
            continue  # bu kayıt bir "ittifaktan ayrılma" kaydı, atla

        temiz_isim = temizle_isim(yeni_isim)
        if not temiz_isim or temiz_isim in gorulen_isimler:
            continue  # aynı ittifakı (rename'ler dahil) tekrar sayma

        gorulen_isimler.add(temiz_isim)
        sonuc.append({
            "isim": temiz_isim,
            "tarih": tarihi_formatla(kayit.get("date", "")),
        })

        if len(sonuc) >= GECMIS_ITTIFAK_SAYISI:
            break

    return sonuc


def get_player_by_name(player_name: str):
    """Oyuncunun tüm bilgilerini (seviye, güç, ittifak geçmişi, mimli analiz) toplar."""
    durum, data = oyuncuyu_bul(player_name)
    if durum != "basarili":
        return durum  # hata mesajı

    player_id = data.get("player_id")
    level_value = data.get("level", "Bilinmiyor")
    might_value = data.get("might_current", "Bilinmiyor")
    guncel_ittifak = temizle_isim(data.get("alliance_name") or "") or "İttifaksız"

    gecmis = ittifak_gecmisini_getir(player_id) if player_id else []

    if not gecmis:
        gecmis = [{"isim": guncel_ittifak, "tarih": "Bilinmiyor"}] if guncel_ittifak != "İttifaksız" else []

    # Mimli düşman analizi: geçmişteki HER ittifak için ayrı ayrı kontrol
    mimli_kayitlar = [kayit for kayit in gecmis if mimli_mi(kayit["isim"])]

    profile_link = f"https://gge-tracker.com/players?player={requests.utils.quote(player_name)}&server=TR1"

    return {
        "name": data.get("player_name") or player_name,
        "level": level_value,
        "might": f"{might_value:,}".replace(",", ".") if isinstance(might_value, (int, float)) else might_value,
        "guncel_ittifak": guncel_ittifak,
        "gecmis": gecmis,
        "mimli_kayitlar": mimli_kayitlar,
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

    gecmis_text = "\n".join([f"• {k['isim']} — {k['tarih']}" for k in result["gecmis"]]) or "Kayıt bulunamadı."

    if result["mimli_kayitlar"]:
        satirlar = [f"   ⚠️ {k['isim']} — {k['tarih']} tarihinde bu ittifaktaydı" for k in result["mimli_kayitlar"]]
        dusman_text = "🚨 **DİKKAT! MİMLİ DÜŞMAN GEÇMİŞİ TESPİT EDİLDİ!**\n" + "\n".join(satirlar)
    else:
        dusman_text = "✅ Son kayıtlarında mimli düşman ittifak bulunamadı."

    message = (
        f"🏰 *TR1 İstihbarat Raporu:* `{result['name']}`\n\n"
        f"⭐ *Seviye:* {result['level']}\n"
        f"⚡ *Güç:* {result['might']}\n"
        f"🛡️ *Güncel İttifak:* {result['guncel_ittifak']}\n\n"
        f"📜 *Son {GECMIS_ITTIFAK_SAYISI} İttifak Geçmişi:*\n{gecmis_text}\n\n"
        f"{dusman_text}\n\n"
        f"🔗 *Detaylı Profil:* {result['profile_url']}"
    )
    await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)


async def oyuncutest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/players/{playerName} adresinden gelen ham veriyi olduğu gibi gösterir (test amaçlı)."""
    if not context.args:
        await update.message.reply_text("Örnek: `/oyuncutest SirlusBlaCK`", parse_mode="Markdown")
        return

    player_name = " ".join(context.args)
    durum, data = oyuncuyu_bul(player_name)
    if durum != "basarili":
        await update.message.reply_text(durum)
        return

    import json

    raw_text = json.dumps(data, ensure_ascii=False, indent=2)
    if len(raw_text) > 3500:
        raw_text = raw_text[:3500] + "\n... (kısaltıldı)"

    await update.message.reply_text(f"```\n{raw_text}\n```", parse_mode="Markdown")


def main():
    TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")

    if not TOKEN:
        print("HATA: BOT_TOKEN bulunamadı!")
        return

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("oyuncu", oyuncu_command))
    application.add_handler(CommandHandler("oyuncutest", oyuncutest_command))

    print("Bot resmi API modunda aktif...")
    application.run_polling()


if __name__ == "__main__":
    main()
