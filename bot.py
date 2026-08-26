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

def get_player_real_stats(player_query):
    """Oyuncu adı veya ID'sine göre GGE Tracker verilerini çeken kusursuz fonksiyon."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://gge-tracker.com/"
    }
    
    player_link = None
    
    # Eğer kullanıcı direkt ID girdiyse (örn: 4263593090) doğrudan linki oluşturalım!
    if player_query.isdigit():
        player_link = f"https://gge-tracker.com/player/{player_query}"
    else:
        # İsimle arama yapıyorsak sitenin arama parametresini kullanalım
        search_url = f"https://gge-tracker.com/players?search={requests.utils.quote(player_query)}&server=TR1"
        
        try:
            res = requests.get(search_url, headers=headers, timeout=10)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # Sayfadaki tüm linkleri tarayıp /player/ içeren ID'li linki kapalım
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if '/player/' in href:
                        # Eşleşme bulduk
                        player_link = "https://gge-tracker.com" + href if href.startswith('/') else href
                        break
                
                # Eğer link bulamadıysak tablo satırlarına bakalım
                if not player_link:
                    for row in soup.find_all('tr'):
                        if player_query.lower() in row.get_text().lower():
                            link_tag = row.find('a', href=True)
                            if link_tag:
                                href = link_tag['href']
                                player_link = "https://gge-tracker.com" + href if href.startswith('/') else href
                                break
        except Exception as e:
            logger.error(f"Arama hatası: {e}")

    # Eğer hala bulunamadıysa, son çare olarak doğrudan girilen ismi ID sanıp veya url kalıbıyla deneyelim
    if not player_link:
        # Alternatif olarak doğrudan arama sonucunu bulamadık ama kullanıcıya ID ile arama yapabileceğini söyleyelim
        return f"'{player_query}' arama sonuçlarında listelenemedi. Oyuncunun GGE Tracker ID numarasıyla (Örn: `/oyuncu 4263593090`) aramayı dene reis!"

    # Doğrudan #alliances sekmesini ekleyelim ki ittifak geçmişi direkt açılsın
    alliance_page_link = f"{player_link}#alliances"

    try:
        # Profil sayfasına gidip güç ve ittifak geçmişini çekelim
        profile_res = requests.get(player_link, headers=headers, timeout=10)
        
        might_value = "Bulunamadı"
        alliances = []
        
        if profile_res.status_code == 200:
            p_soup = BeautifulSoup(profile_res.text, 'html.parser')
            
            for el in p_soup.find_all(['div', 'span', 'td', 'li', 'p']):
                text = el.get_text(strip=True)
                # İttifak geçmişi tespiti (Aylar veya tarih kalıpları)
                if any(m in text for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]) and len(text) < 100:
                    if text not in alliances:
                        alliances.append(text)
                # Güç tespiti
                if "might" in text.lower() or "güç" in text.lower():
                    might_value = text

        return {
            "profile_url": alliance_page_link,
            "might": might_value,
            "alliances": alliances[:6] if alliances else ["İttifak geçmişi sekmesinde mevcut."]
        }
            
    except Exception as e:
        logger.error(f"Profil çekme hatası: {e}")
        return "Profil verileri okunurken teknik bir hata oluştu."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot hazır reis! 🚀 Sorgulamak için:\n`/oyuncu OyuncuAdi` veya `/oyuncu OyuncuIDsi`", 
        parse_mode="Markdown"
    )

async def oyuncu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Lütfen bir oyuncu adı veya ID'si girin!\nÖrnek: `/oyuncu siriusblack` veya `/oyuncu 4263593090`",
            parse_mode="Markdown"
        )
        return

    query = " ".join(context.args)
    await update.message.reply_text(f"🔍 TR1 sunucusunda '{query}' taranıyor...")

    result = get_player_real_stats(query)

    if isinstance(result, str):
        await update.message.reply_text(result)
    else:
        alliance_text = "\n".join([f"• {item}" for item in result['alliances']])
        
        message = (
            f"🏰 *TR1 Oyuncu Raporu*\n\n"
            f"⚡ *Güç Bilgisi:* {result['might']}\n\n"
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

    print("Bot ID ve İsim destekli sürümle çalışıyor...")
    application.run_polling()

if __name__ == "__main__":
    main()
