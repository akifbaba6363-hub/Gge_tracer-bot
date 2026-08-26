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

def get_player_real_stats(player_name):
    """Sitenin güvenlik duvarını aşmak için tam tarayıcı taklidi yapan gelişmiş fonksiyon."""
    # Doğrudan ana sitenin oyuncu arama URL'si
    search_url = f"https://gge-tracker.com/players?player={requests.utils.quote(player_name)}&server=TR1"
    
    # Gerçek bir tarayıcının gönderdiği tüm gizli başlıkları ekliyoruz ki site bizi engellemesin
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://gge-tracker.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        # Oturum (Session) kullanarak istek atalım
        session = requests.Session()
        res = session.get(search_url, headers=headers, timeout=15)
        
        if res.status_code != 200:
            return f"Site engeline takıldık (Kod: {res.status_code})."
            
        soup = BeautifulSoup(res.text, 'html.parser')
        
        player_path = None
        
        # 1. Sayfadaki oyuncu linklerini tara (/player/ID)
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/player/' in href:
                player_path = href
                break
                
        # 2. Tablo satırlarından yakalamaya çalış
        if not player_path:
            for row in soup.find_all('tr'):
                if player_name.lower() in row.get_text().lower():
                    link_tag = row.find('a', href=True)
                    if link_tag:
                        player_path = link_tag['href']
                        break

        if not player_path:
            return f"'{player_name}' TR1 sunucusunda bulunamadı."

        # Profil linkini tamamla
        profile_link = "https://gge-tracker.com" + player_path if not player_path.startswith('http') else player_path
        alliance_page_link = f"{profile_link}#alliances"

        # Oyuncunun profil sayfasına gidip detayları (güç ve ittifaklar) çekelim
        profile_res = session.get(profile_link, headers=headers, timeout=15)
        
        might_value = "Bilinmiyor"
        level_value = "Bilinmiyor"
        alliances = []
        
        if profile_res.status_code == 200:
            p_soup = BeautifulSoup(profile_res.text, 'html.parser')
            
            # Sayfadaki metinleri ve elementleri tarayalım
            for el in p_soup.find_all(['div', 'span', 'td', 'li', 'p', 'b']):
                text = el.get_text(strip=True)
                
                # İttifak geçmişi tarih formatları kontrolü
                if any(m in text for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]) and len(text) < 100:
                    if text not in alliances:
                        alliances.append(text)
                        
                # Güç tespiti
                if "might" in text.lower() or "güç" in text.lower():
                    might_value = text
                    
                # Seviye tespiti
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
            "name": player_name,
            "level": level_value,
            "might": might_value,
            "alliances": alliances[:5] if alliances else ["İttifak geçmişi detay sayfasında."],
            "dusmanlar": bulunan_dusmanlar,
            "profile_url": alliance_page_link
        }
            
    except Exception as e:
        logger.error(f"Hata: {e}")
        return "Bağlantı sırasında teknik bir hata oluştu."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot korumayı aşacak şekilde güncellendi reis! 🚀 Sorgulamak için:\n`/oyuncu OyuncuAdi`", 
        parse_mode="Markdown"
    )

async def oyuncu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Lütfen bir oyuncu adı girin!\nÖrnek: `/oyuncu siriusblack`",
            parse_mode="Markdown"
        )
        return

    player_name = " ".join(context.args)
    await update.message.reply_text(f"🔍 TR1 sunucusunda '{player_name}' taranıyor ve düşman analizi yapılıyor...")

    result = get_player_real_stats(player_name)

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

    print("Bot koruma aşmalı sürümle çalışıyor...")
    application.run_polling()

if __name__ == "__main__":
    main()
