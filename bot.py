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
    """GGE Tracker sitesinden oyuncu arayan ve profili çeken gelişmiş fonksiyon."""
    # Sitenin arama sayfasına TR1 ve query parametresiyle gidiyoruz
    search_url = f"https://gge-tracker.com/players?search={requests.utils.quote(player_name)}&server=TR1"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return "Siteye ulaşılamadı reis."
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        player_link = None
        
        # 1. Yöntem: Bütün <a> etiketlerini tara
        for a in soup.find_all('a', href=True):
            href = a['href']
            link_text = a.get_text().strip()
            if '/player/' in href:
                if player_name.lower() in link_text.lower() or player_name.lower() in href.lower():
                    player_link = "https://gge-tracker.com" + href if href.startswith('/') else href
                    break
        
        # 2. Yöntem: Tablo satırlarını (tr) tara
        if not player_link:
            for row in soup.find_all('tr'):
                row_text = row.get_text()
                if player_name.lower() in row_text.lower():
                    link_tag = row.find('a', href=True)
                    if link_tag:
                        href = link_tag['href']
                        player_link = "https://gge-tracker.com" + href if href.startswith('/') else href
                        break

        # Eğer hala bulamadıysak doğrudan ID veya arama kalıbıyla eşleşen kutulara bakalım
        if not player_link:
            # Alternatif olarak sitenin genel arama girdisini simüle edelim ya da direkt uyarı verelim
            return f"'{player_name}' için arama sonuçlarında doğrudan eşleşme bulunamadı. Sitenin kendi arama yapısı dinamik çalışıyor olabilir."

        # Oyuncu profil sayfasına git
        profile_res = requests.get(player_link, headers=headers, timeout=10)
        if profile_res.status_code != 200:
            return f"Profil sayfasına ulaşılamadı: {player_link}"

        p_soup = BeautifulSoup(profile_res.text, 'html.parser')
        
        # İttifak geçmişini toplayalım
        alliance_history = []
        for element in p_soup.find_all(['div', 'tr', 'li', 'span']):
            txt = element.get_text(strip=True)
            # Tarih veya ittifak geçiş ibarelerini yakala
            if any(m in txt for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]) and len(txt) < 120:
                if txt not in alliance_history:
                    alliance_history.append(txt)

        return {
            "profile_url": player_link,
            "alliances": alliance_history[:6]
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
    await update.message.reply_text(f"🔍 TR1 sunucusunda '{player_name}' taranıyor...")

    result = get_player_stats(player_name)

    if isinstance(result, str):
        await update.message.reply_text(result)
    else:
        alliance_text = "\n".join([f"• {item}" for item in result['alliances']]) if result['alliances'] else "Geçmiş kayıt bulunamadı."
        
        message = (
            f"🏰 *TR1 Oyuncu Raporu:* `{player_name}`\n\n"
            f"🛡️ *İttifak Geçmişi (Son Kayıtlar):*\n{alliance_text}\n\n"
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

    print("Bot güncellendi ve çalışıyor...")
    application.run_polling()

if __name__ == "__main__":
    main()
