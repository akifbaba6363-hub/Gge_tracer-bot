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
    """GGE Tracker API üzerinden hatasız oyuncu arama fonksiyonu."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    # 1. Alternatif API Endpoint'leri (Tracker sitelerinin sıklıkla kullandığı yollar)
    endpoints_to_try = [
        f"https://api.gge-tracker.com/v1/players?search={requests.utils.quote(player_name)}&server=TR1",
        f"https://api.gge-tracker.com/v1/search?q={requests.utils.quote(player_name)}&server=TR1",
        f"https://api.gge-tracker.com/api/v1/players/search?name={requests.utils.quote(player_name)}&server=TR1",
        f"https://gge-tracker.com/api/players?search={requests.utils.quote(player_name)}&server=TR1"
    ]
    
    data = None
    success_url = ""
    
    for url in endpoints_to_try:
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                success_url = url
                break
        except Exception as e:
            continue
            
    if not data:
        # Eğer hiçbir API endpoint doğrudan dönmezse, doğrudan web profil linkini oluşturalım
        # GGE Tracker genelde doğrudan /player/İsim şeklinde de yönlendirebiliyor
        fallback_profile = f"https://gge-tracker.com/player/{player_name}"
        return {
            "name": player_name,
            "profile_url": fallback_profile,
            "alliances": ["API yanıt vermedi, doğrudan profil linki oluşturuldu."]
        }

    # Gelen veriyi işle
    players = data.get("data", data) if isinstance(data, dict) else data
    if isinstance(players, list) and len(players) > 0:
        player = players[0]
        player_id = player.get("id") or player.get("player_id") or player_name
        exact_name = player.get("name", player_name)
        
        profile_link = f"https://gge-tracker.com/player/{player_id}"
        
        # İttifak geçmişi varsa çek
        alliance_history = []
        raw_alliances = player.get("alliances", player.get("allianceHistory", []))
        for ah in raw_alliances:
            a_name = ah.get("name", "Bilinmiyor")
            a_date = ah.get("date", "")
            alliance_history.append(f"{a_date}: {a_name}" if a_date else a_name)
            
        return {
            "name": exact_name,
            "profile_url": profile_link,
            "alliances": alliance_history[:6] if alliance_history else ["İttifak geçmişi bulunamadı."]
        }
    else:
        return f"'{player_name}' sunucuda bulunamadı."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot başlatıldığında çalışan /start komutu."""
    await update.message.reply_text(
        "Bot hazır reis! 🚀 Doğrudan sorgulamak için:\n`/oyuncu OyuncuAdi`", 
        parse_mode="Markdown"
    )

async def oyuncu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Herhangi bir zamanda /oyuncu <OyuncuAdi> yazıldığında çalışan komut."""
    if not context.args:
        await update.message.reply_text(
            "Lütfen bir oyuncu adı girin!\nÖrnek: `/oyuncu SirIusBlaCK`",
            parse_mode="Markdown"
        )
        return

    player_name = " ".join(context.args)
    await update.message.reply_text(f"🔍 '{player_name}' taranıyor...")

    result = get_player_via_api(player_name)

    if isinstance(result, str):
        await update.message.reply_text(result)
    else:
        alliance_text = "\n".join([f"• {item}" for item in result['alliances']])
        
        message = (
            f"🏰 *TR1 Oyuncu Raporu:* `{result['name']}`\n\n"
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

    print("Bot stabil versiyonla çalışıyor...")
    application.run_polling()

if __name__ == "__main__":
    main()
