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

def get_player_via_api(player_name):
    """GGE Tracker API kullanarak oyuncu verilerini ve ittifak geçmişini çeken fonksiyon."""
    # Genellikle bu tarz tracker API'lerinde arama endpoint'i bulunur. 
    # API base URL: https://api.gge-tracker.com/v1 (veya dokümandaki base url)
    api_url = f"https://api.gge-tracker.com/v1/players/search" # Veya dokümandaki doğru endpoint
    
    # Alternatif olarak doğrudan oyuncu adına göre endpoint denetimi
    search_endpoint = f"https://api.gge-tracker.com/v1/search?query={requests.utils.quote(player_name)}&server=TR1"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }
    
    try:
        # Önce API arama endpoint'ini deneyelim
        response = requests.get(search_endpoint, headers=headers, timeout=10)
        
        # Eğer doğrudan arama endpoint yapısı farklıysa, alternatif URL'yi test edelim
        if response.status_code != 200:
            alt_url = f"https://api.gge-tracker.com/api/v1/players?name={requests.utils.quote(player_name)}&server=TR1"
            response = requests.get(alt_url, headers=headers, timeout=10)
            
        if response.status_code != 200:
            return f"API üzerinden oyuncuya ulaşılamadı (Kod: {response.status_code})."
            
        data = response.json()
        
        # Gelen JSON verisinden oyuncu ID ve detaylarını alalım
        # Genellikle 'data' veya liste döner
        players = data.get("data", data) if isinstance(data, dict) else data
        
        if not players:
            return f"'{player_name}' API kayıtlarında bulunamadı."
            
        # İlk eşleşen oyuncuyu alalım
        player = players[0] if isinstance(players, list) else players
        player_id = player.get("id") or player.get("player_id")
        exact_name = player.get("name", player_name)
        
        if not player_id:
            return f"'{player_name}' bulundu ancak ID bilgisi alınamadı."

        # Oyuncunun detaylı geçmişini (ittifak değişimleri dahil) çeken ikinci istek
        detail_url = f"https://api.gge-tracker.com/v1/players/{player_id}"
        detail_res = requests.get(detail_url, headers=headers, timeout=10)
        
        alliances = []
        if detail_res.status_code == 200:
            detail_data = detail_res.json()
            alliance_history = detail_data.get("alliances", detail_data.get("allianceHistory", []))
            for ah in alliance_history:
                name = ah.get("name", "Bilinmiyor")
                date = ah.get("date", ah.get("changed_at", ""))
                alliances.satis(f"{date}: {name}" if date else name)

        profile_link = f"https://gge-tracker.com/player/{player_id}"

        return {
            "name": exact_name,
            "profile_url": profile_link,
            "alliances": alliances[:6] if alliances else ["API üzerinden ittifak geçmişi listelenemedi."]
        }
            
    except Exception as e:
        logger.error(f"API bağlantı hatası: {e}")
        return "API sorgulanırken teknik bir hata oluştu."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot başlatıldığında çalışan /start komutu."""
    await update.message.reply_text(
        "Bot API modunda aktif reis! 🚀\nTR1 sunucusunda oyuncu sorgulamak için:\n`/oyuncu OyuncuAdi`", 
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
    await update.message.reply_text(f"🔍 TR1 sunucusunda '{player_name}' API ile sorgulanıyor...")

    result = get_player_via_api(player_name)

    if isinstance(result, str):
        await update.message.reply_text(result)
    else:
        alliance_text = "\n".join([f"• {item}" for item in result['alliances']])
        
        message = (
            f"🏰 *TR1 Oyuncu Raporu (API):* `{result['name']}`\n\n"
            f"🛡️ *İttifak Geçmişi:*\n{alliance_text}\n\n"
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

    print("Bot API entegrasyonuyla çalışıyor...")
    application.run_polling()

if __name__ == "__main__":
    main()
