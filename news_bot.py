import feedparser
import requests
import datetime
import os
from dateutil import parser
from urllib.parse import quote

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID_LIST")
CHAT_ID_LIST = [chat_id.strip() for chat_id in CHAT_ID_RAW.split(",")] if CHAT_ID_RAW else []

def get_google_news(publisher, count):
    exclude_query = "-연예 -스포츠 -야구 -축구 -골프 -드라마 -아이돌"
    query = quote(f"source:{publisher} when:1d {exclude_query}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    news_list = []
    seen_titles = set()
    
    for entry in feed.entries:
        if len(news_list) >= count: # 각 언론사별 목표 개수까지만 수집
            break
        title = entry.title.split(' - ')[0].strip()
        title_key = "".join(title.split())[:15]
        
        if title_key not in seen_titles:
            news_list.append({
                'title': title,
                'link': entry.link,
                'parsed_date': parser.parse(entry.published).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
            })
            seen_titles.add(title_key)
    return news_list

def main():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    date_str = now.strftime("%y년 %m월 %d일")
    hour = now.hour
    time_tag = "07시" if hour < 12 else "18시"
    sub_header = "주요 언론사별 맞춤 브리핑"

    # 사용자 지정 언론사별 비중 설정
    configs = [
        {"name": "연합뉴스", "count": 4},
        {"name": "한국경제", "count": 2},
        {"name": "YTN", "count": 2}
    ]
    
    final_news = []
    for config in configs:
        final_news.extend(get_google_news(config["name"], config["count"]))
    
    if not final_news:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n\n새로운 소식이 없습니다."
    else:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n"
        message += f"<b>{sub_header} (연합4, 한경2, YTN2)</b>\n"
        message += "━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, news in enumerate(final_news, 1):
            pub_time = news['parsed_date'].strftime('%H:%M')
            message += f"{i}. <a href='{news['link']}'>{news['title']}</a> [{pub_time}]\n\n"

    # 전송
    send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for chat_id in CHAT_ID_LIST:
        payload = {
            "chat_id": chat_id, 
            "text": message, 
            "parse_mode": "HTML", 
            "disable_web_page_preview": False
        }
        requests.post(send_url, data=payload)

if __name__ == "__main__":
    main()
