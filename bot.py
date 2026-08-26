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

# MİMLİ / DÜŞMAN İTTİFAKLAR LİSTESİ
MIMLI_ITTIFAKLAR = ["GÖKDOĞAN", "DüşmanKlan1", "TheOttomans", "BlackDeath"]

def get_player_real_stats(player_query):
    """Bulut korumalarını ve yönlendirmeleri aşan güncellenmiş arama fonksiyonu."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://gge-tracker.com/",
        "Cache-Control": "no-cache"
    }
    
    player_link = None
    
    # 1. Eğer kullanıcı direkt ID girdiyse doğrudan profil linkini kur
    if player_query.isdigit():
        player_link = f"https://gge-tracker.com/player/{player_query}"
    else:
        # 2. İsimle arama yaparken hem küçük harfli hem orijinal halini deneyelim
        queries_to_try = [player_query, player_query.lower(), player_query.capitalize()]
        
        for q in queries_to_try:
            search_url = f"https://gge-tracker.com/players?player={requests.utils.quote(q)}&server=TR1"
            try:
                session = requests.Session()
                res = session.get(search_url, headers=headers, timeout=12)
                
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    
                    # Sayfadaki oyuncu linklerini tara
                    for a in soup.find_all('a', href=True):
                        href = a['href']
                        if '/player/' in href:
                            player_link = "https://gge-tracker.com" + href if href.startswith('/') else href
                            break
                    if player_link:
                        break
            except Exception as e:
                logger.error(f"Arama deneme hatası: {e}")

    if not player_link:
        return f"'{player_query}' TR1 sunucusunda bulunamadı. Sitede ismin nasıl geçtiğini kontrol edebilirsin."

    alliance_page_link = f"{player_link}#alliances"

    try:
        session = requests.Session()
        profile_res = session.get(player_link, headers=headers, timeout=12)
        
        might_value = "Bilinmiyor"
        level_value = "Bilinmiyor"
        alliances = []
        
        if profile_res.status_code == 200:
            p_soup = BeautifulSoup(profile_res.text, 'html.parser')
            
            for el in p_soup.find_all(['div', 'span', 'td', 'li', 'p', 'b']):
                text = el.get_text(strip=True)
                
                # İttifak geçmişi tarih kalıpları
                if any(m in text for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]) and len(text) < 100:
                    if text not in alliances:
                        alliances.append(text)
                        
                if "might" in text.lower() or "güç" in text.lower():
                    might_value = text
                if "level" in text.lower() or "seviye" in text.lower():
                    level_value = text

        # Mimli düşman analizi
        bulunan_dusmanlar = []
        for ittifak in alliances:
            for mimli in MIMLI_ITTIFAKLAR:
                if mimli.lower() in ittifak.lower():
                    if mimli not in bulunan_dusmanlar:
                        bulunan_dusmanlar.append(mimli)

        return {
            "name": player_query,
            "level": level_value,
            "might": might_value,
            "alliances": alliances[:5] if alliances else ["İttifak geçmişi detay sayfasında."],
            "dusmanlar": bulunan_dusmanlar,
            "profile_url": alliance_page_link
        }
            
    except Exception as e:
        logger.error(f"Profil hata: {e}")
        return "Profil verileri çekilirken hata oluştu."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot en kararlı sürümle aktif reis! 🚀 Sorgulamak için:\n`/oyuncu OyuncuAdi`", 
        parse_mode="Markdown"
    )

async def oyuncu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Lütfen bir oyuncu adı girin!\nÖrnek: `/oyuncu siriusblack`",
            parse_mode="Markdown"
        )
        return

    player_query = " ".join(context.args)
    await update.message.reply_text(f"🔍 TR1 havuzunda '{player_query}' taranıyor...")

    result = get_player_real_stats(player_query)

    if isinstance(result, str):
        await update.message.reply_text(result)
    else:
        alliance_list_text = "\n".join([f"• {item}" for item in result['alliances']])
        
        if result['dusmanlar']:
            dusman_text = f"🚨 **DİKKAT! MİMLİ DÜŞMAN TESPİT EDİLDİ!**\nŞu düşman ittifaklarda bulundu: " + ", ".join([f"*{d}*" for d in result['dusmanlar']])
        else:
            dusman_text = "✅ Son kayıtlarında mimli düşman ittifak bulunamadı."

        message = (
            f"🏰 *TR1 İstihbarat Raporu:* `{result['name']}`\n\n"
            f"⭐ *Seviye:* {result['level']}\n"
            f"⚡ *Güç:* {result['might']}\n\n"
            f"🛡️ *Son İttifak Geçmişi:*\n{alliance_list_text}\n\n"
            f"{dusman_text}\n\n"
            f"🔗 *Detaylı Profil:* {result['profile_url']}"
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

    print("Bot kararlı sürümle çalışıyor...")
    application.run_polling()

if __name__ == "__main__":
    main()
