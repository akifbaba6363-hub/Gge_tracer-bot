import os
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# Logging ayarları
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_player_stats(player_name):
    """GGE Tracker sitesinden TR1 sunucusunda oyuncu arayan gelişmiş fonksiyon."""
    # Sitenin arama sayfasına direkt gidiyoruz
    search_url = f"https://gge-tracker.com/players?search={player_name}&server=TR1"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return "Siteye ulaşılamadı reis."
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        player_link = None
        # Bütün linkleri tarayıp oyuncunun profil linkini arayalım
        for a in soup.find_all('a', href=True):
            if '/player/' in a['href']:
                # Harf duyarlılığını kaldırarak eşleşmeye bakıyoruz
                if player_name.lower() in a.text.lower() or player_name.lower() in a['href'].lower():
                    player_link = "https://gge-tracker.com" + a['href']
                    break
        
        # Eğer link bulunamadıysa tablo satırlarını kontrol et
        if not player_link:
            for row in soup.find_all('tr'):
                if player_name.lower() in row.text.lower():
                    link_tag = row.find('a', href=True)
                    if link_tag:
                        player_link = "https://gge-tracker.com" + link_tag['href']
                        break

        if not player_link:
            return f"'{player_name}' TR1 sunucusunda bulunamadı. İsmi doğru yazdığından emin olalım."

        # Oyuncu profil sayfasına gidip detayları çekelim
        profile_res = requests.get(player_link, headers=headers, timeout=10)
        if profile_res.status_code != 200:
            return f"Profil sayfasına ulaşıldı ama içerik alınamadı: {player_link}"

        return {
            "profile_url": player_link
        }
            
    except Exception as e:
        logger.error(f"Veri çekme hatası: {e}")
        return "Veri çekilirken teknik bir hata oluştu."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot başlatıldığında çalışan /start komutu."""
    await update.message.reply_text(
        "Bot aktif reis! 🚀\nTR1 sunucusunda oyuncu sorgulamak için:\n`/oyuncu OyuncuAdi`", 
        parse_mode="Markdown"
    )

async def oyuncu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gruba veya özele /oyuncu <OyuncuAdi> yazıldığında çalışan komut."""
    if not context.args:
        await update.message.reply_text(
            "Lütfen bir oyuncu adı girin!\nÖrnek kullanım: `/oyuncu SirIusBlaCK`",
            parse_mode="Markdown"
        )
        return

    player_name = " ".join(context.args)
    await update.message.reply_text(f"🔍 TR1 sunucusunda '{player_name}' taranıyor, bekletmiyorum...")

    result = get_player_stats(player_name)

    if isinstance(result, str):
        await update.message.reply_text(result)
    else:
        message = (
            f"🏰 *TR1 Oyuncu Profili Bulundu!*\n"
            f"👤 *Aranan:* `{player_name}`\n\n"
            f"🔗 *Profil Linki:* {result['profile_url']}"
        )
        await update.message.reply_text(message, parse_mode="Markdown", disable_web_page_preview=True)

def main():
    TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
    
    if not TOKEN:
        print("HATA: BOT_TOKEN bulunamadı!")
        return

    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("oyuncu", oyuncu_command))

    print("Bot arama mekanizmasıyla güncellendi ve çalışıyor...")
    application.run_polling()

if __name__ == "__main__":
    main()
