import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# Logging ayarları
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_player_real_stats(player_name):
    """Doğrudan GGE Tracker API'sini kullanarak oyuncu verilerini ve ID'sini çeken kusursuz fonksiyon."""
    # Ekran görüntüsünde yakaladığımız gerçek API uç noktası
    api_url = f"https://api.gge-tracker.com/players?player={requests.utils.quote(player_name)}&server=TR1"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://gge-tracker.com/",
        "Origin": "https://gge-tracker.com"
    }
    
    try:
        res = requests.get(api_url, headers=headers, timeout=10)
        if res.status_code != 200:
            return "API sunucusuna erişilemedi reis."
            
        data = res.json()
        
        # API'den dönen verinin yapısını kontrol edelim
        players = []
        if isinstance(data, list):
            players = data
        elif isinstance(data, dict) and "data" in data:
            players = data["data"]
        elif isinstance(data, dict):
            players = [data]

        if not players:
            return f"'{player_name}' TR1 sunucusunda API kayıtlarında bulunamadı."

        # İlk eşleşen oyuncuyu alalım
        player = players[0]
        
        # Oyuncu ID'sini ve diğer detayları JSON verisinden saniyede çekelim
        player_id = player.get("id") or player.get("player_id") or player.get("uid")
        actual_name = player.get("name", player_name)
        might = player.get("might", player.get("lord_might", "Bulunamadı"))
        
        if player_id:
            profile_url = f"https://gge-tracker.com/player/{player_id}#alliances"
        else:
            profile_url = f"https://gge-tracker.com/players?player={requests.utils.quote(player_name)}"

        return {
            "name": actual_name,
            "profile_url": profile_url,
            "might": might,
            "alliances": ["İttifak geçmişi için profil linkine tıklayabilirsin."]
        }
            
    except Exception as e:
        logger.error(f"API Hata: {e}")
        return "API verisi çözümlenirken teknik bir hata oluştu."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot doğrudan API bağlantısıyla güncellendi reis! 🚀 Sorgulamak için:\n`/oyuncu OyuncuAdi`", 
        parse_mode="Markdown"
    )

async def oyuncu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Lütfen bir oyuncu adı girin!\nÖrnek: `/oyuncu legendararrow`",
            parse_mode="Markdown"
        )
        return

    player_name = " ".join(context.args)
    await update.message.reply_text(f"🔍 TR1 API havuzunda '{player_name}' sorgulanıyor...")

    result = get_player_real_stats(player_name)

    if isinstance(result, str):
        await update.message.reply_text(result)
    else:
        message = (
            f"🏰 *TR1 Oyuncu Raporu:* `{result['name']}`\n\n"
            f"⚡ *Güç Bilgisi:* {result['might']}\n\n"
            f"🔗 *Doğrudan Profil Linki:* {result['profile_url']}"
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

    print("Bot API tabanlı modda çalışıyor...")
    application.run_polling()

if __name__ == "__main__":
    main()
