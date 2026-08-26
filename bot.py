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
    """GGE Tracker sitesinden TR1 sunucusuna göre oyuncu arayan fonksiyon."""
    # TR1 sunucusu için hedef URL (veya ana sayfa üzerinden arama)
    url = f"https://gge-tracker.com/players?search={player_name}&server=TR1"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return "Oyuncu bulunamadı veya siteye ulaşılamadı."
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Tablo satırlarını bulalım
        player_rows = soup.find_all('tr')
        
        found_data = None
        for row in player_rows:
            if player_name.lower() in row.text.lower():
                found_data = row
                break
                
        if not found_data:
            return f"'{player_name}' adında bir oyuncu TR1 sunucusunda bulunamadı."
            
        columns = found_data.find_all('td')
        
        if len(columns) > 3:
            castle_level = columns[2].text.strip() if len(columns) > 2 else "Bilinmiyor"
            might = columns[3].text.strip() if len(columns) > 3 else "Bilinmiyor"
            alliance_history = columns[5].text.strip() if len(columns) > 5 else "Bilinmiyor"
            
            return {
                "castle_level": castle_level,
                "might": might,
                "alliance_history": alliance_history
            }
        else:
            return "Oyuncu bilgileri okunamadı."
            
    except Exception as e:
        logger.error(f"Veri çekme hatası: {e}")
        return "Veri çekilirken bir hata oluştu."

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
            "Lütfen bir oyuncu adı girin!\nÖrnek kullanım: `/oyuncu siriusblack`",
            parse_mode="Markdown"
        )
        return

    player_name = " ".join(context.args)
    await update.message.reply_text(f"🔍 TR1 sunucusunda '{player_name}' aranıyor, bekletmeyecem...")

    result = get_player_stats(player_name)

    if isinstance(result, str):
        await update.message.reply_text(result)
    else:
        message = (
            f"🏰 *TR1 Oyuncu Raporu:* `{player_name}`\n\n"
            f"⭐ *Kale Seviyesi:* {result['castle_level']}\n"
            f"⚔️ *Güç Puanı (Might):* {result['might']}\n"
            f"🛡️ *İttifak Geçmişi:* {result['alliance_history']}"
        )
        await update.message.reply_text(message, parse_mode="Markdown")

def main():
    TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
    
    if not TOKEN:
        print("HATA: BOT_TOKEN bulunamadı!")
        return

    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("oyuncu", oyuncu_command))

    print("Bot TR1 için güncellendi ve çalışıyor...")
    application.run_polling()

if __name__ == "__main__":
    main()
