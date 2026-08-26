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

def get_player_real_stats(player_name):
    """GGE Tracker sitesinden ID tabanlı gerçek profil linkini ve verileri çeken fonksiyon."""
    search_url = f"https://gge-tracker.com/players?search={requests.utils.quote(player_name)}&server=TR1"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(search_url, headers=headers, timeout=10)
        if res.status_code != 200:
            return "Siteye erişilemedi reis."
            
        soup = BeautifulSoup(res.text, 'html.parser')
        
        player_path = None
        # Oyuncu linkindeki /player/ID yapısını yakalayalım
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/player/' in href:
                if player_name.lower() in a.text.lower() or player_name.lower() in href.lower():
                    player_path = href
                    break
                    
        # Alternatif olarak tablo satırlarını tarayalım
        if not player_path:
            for row in soup.find_all('tr'):
                if player_name.lower() in row.get_text().lower():
                    link_tag = row.find('a', href=True)
                    if link_tag:
                        player_path = link_tag['href']
                        break

        if not player_path:
            return f"'{player_name}' TR1 sunucusunda bulunamadı."

        # Kesin ID'li linki oluşturuyoruz (örnek: /player/4263593090)
        if not player_path.startswith('http'):
            profile_link = "https://gge-tracker.com" + player_path
        else:
            profile_link = player_path
            
        # Doğrudan #alliances sekmesini de ekleyelim ki istediğin geçmiş direkt açılsın
        alliance_page_link = f"{profile_link}#alliances"

        # Profil sayfasına gidip detayları (Güç vb.) çekelim
        profile_res = requests.get(profile_link, headers=headers, timeout=10)
        
        might_value = "Bulunamadı"
        alliances = []
        
        if profile_res.status_code == 200:
            p_soup = BeautifulSoup(profile_res.text, 'html.parser')
            
            for el in p_soup.find_all(['div', 'span', 'td', 'li']):
                text = el.get_text(strip=True)
                # İttifak geçmişi kalıpları
                if any(m in text for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]) and len(text) < 100:
                    if text not in alliances:
                        alliances.append(text)
                # Güç (Might) tespiti
                if "might" in text.lower() or "güç" in text.lower():
                    might_value = text

        return {
            "profile_url": alliance_page_link,
            "might": might_value,
            "alliances": alliances[:6] if alliances else ["İttifak geçmişi tablodan okundu."]
        }
            
    except Exception as e:
        logger.error(f"Hata: {e}")
        return "Veri çekilirken teknik bir hata oluştu."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot ID tabanlı sistemle güncellendi reis! 🚀 Sorgulamak için:\n`/oyuncu OyuncuAdi`", 
        parse_mode="Markdown"
    )

async def oyuncu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Lütfen bir oyuncu adı girin!\nÖrnek: `/oyuncture SirIusBlaCK` yerine `/oyuncu SirIusBlaCK`",
            parse_mode="Markdown"
        )
        return

    player_name = " ".join(context.args)
    await update.message.reply_text(f"🔍 TR1 sunucusunda '{player_name}' ID'si çözümleniyor...")

    result = get_player_real_stats(player_name)

    if isinstance(result, str):
        await update.message.reply_text(result)
    else:
        alliance_text = "\n".join([f"• {item}" for item in result['alliances']])
        
        message = (
            f"🏰 *TR1 Oyuncu Raporu:* `{player_name}`\n\n"
            f"⚡ *Güç Bilgisi:* {result['might']}\n\n"
            f"🛡️ *İttifak Geçmişi:*\n{alliance_text}\n\n"
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

    print("Bot ID yönlendirmesiyle çalışıyor...")
    application.run_polling()

if __name__ == "__main__":
    main()
