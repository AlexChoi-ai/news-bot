import feedparser
import requests
import datetime
import os
from dateutil import parser
from urllib.parse import quote

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID_LIST")
CHAT_ID_LIST = [chat_id.strip() for chat_id in CHAT_ID_RAW.split(",")] if CHAT_ID_RAW else []

def get_google_news(publisher):
    # 검색 범위를 약간 넓혀서 더 많은 후보군을 가져옵니다.
    exclude_query = "-연예 -스포츠 -야구 -축구 -골프 -드라마 -아이돌"
    query = quote(f"source:{publisher} when:1d {exclude_query}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    news_list = []
    for entry in feed.entries:
        news_list.append({
            'title': entry.title.split(' - ')[0].strip(),
            'link': entry.link,
            'parsed_date': parser.parse(entry.published).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
        })
    return news_list

def main():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    hour = now.hour
    date_str = now.strftime("%y년 %m월 %d일")
    
    # 더 많은 기사를 확보하기 위해 언론사를 추가하거나 검색량을 늘립니다.
    press_list = ["연합뉴스", "한국경제", "매일경제"] 
    all_raw_news = []
    for press in press_list:
        all_raw_news.extend(get_google_news(press))
    
    # 중복 제거
    unique_news = []
    seen_titles = set()
    for news in all_raw_news:
        title_key = "".join(news['title'].split())[:15]
        if title_key not in seen_titles:
            unique_news.append(news)
            seen_titles.add(title_key)

    today_07am = now.replace(hour=7, minute=0, second=0, microsecond=0)
    
    if hour < 12:
        target_count = 8
        time_tag = "07시"
        sub_header = "어제 저녁의 주요 뉴스 8개"
        # 오전에는 단순히 최신순으로 8개
        filtered_news = unique_news
    else:
        target_count = 8
        time_tag = "18시"
        sub_header = "오늘 하루의 주요 뉴스 8개"
        # 오전 7시 이후 뉴스 중복 배제
        filtered_news = [n for n in unique_news if n['parsed_date'] > today_07am]
        
        # 만약 7시 이후 뉴스가 8개가 안 되면, 중복을 감수하더라도 8개를 채웁니다.
        if len(filtered_news) < target_count:
            filtered_news = unique_news

    # 최종 8개 추출
    top_news = filtered_news[:target_count]
    
    if not top_news:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n<b>{sub_header}</b>\n\n새로운 소식이 없습니다."
    else:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n"
        message += f"<b>{sub_header}</b>\n"
        message += "━━━━━━━━━━━━━━━━━━\n\n"
        for i, news in enumerate(top_news, 1):
            pub_time = news['parsed_date'].strftime('%H:%M')
            message += f"{i}. <a href='{news['link']}'>{news['title']}</a> [{pub_time}]\n\n"

    # 전송 로직
    send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for chat_id in CHAT_ID_LIST:
        payload = {
            "chat_id": chat_id, 
            "text": message, 
            "parse_mode": "HTML", 
            "disable_web_page_preview": False
        }
        res = requests.post(send_url, data=payload)
        print(f"전송 결과 ({chat_id}): {res.status_code}, {res.text}")

if __name__ == "__main__":
    main()
