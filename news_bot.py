import feedparser
import requests
import datetime
import os
from dateutil import parser
from urllib.parse import quote

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID_LIST")
CHAT_ID_LIST = [chat_id.strip() for chat_id in CHAT_ID_RAW.split(",")] if CHAT_ID_RAW else []

def get_google_news(publisher, target_count):
    # 검색 범위를 조금 넉넉하게 잡습니다 (필터링 후 개수를 맞추기 위해)
    exclude_query = "-연예 -스포츠 -야구 -축구 -골프 -드라마 -아이돌"
    query = quote(f"source:{publisher} when:1d {exclude_query}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    news_list = []
    seen_titles = set()
    
    for entry in feed.entries:
        title = entry.title.split(' - ')[0].strip()
        title_key = "".join(title.split())[:15]
        
        if title_key not in seen_titles:
            news_list.append({
                'title': title,
                'link': entry.link,
                'publisher': publisher,
                'parsed_date': parser.parse(entry.published).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
            })
            seen_titles.add(title_key)
        
        # 보충용까지 고려하여 타겟의 2배수 정도까지는 일단 수집합니다.
        if len(news_list) >= target_count * 2:
            break
            
    return news_list

def main():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    date_str = now.strftime("%y년 %m월 %d일")
    hour = now.hour
    time_tag = "07시" if hour < 12 else "18시"
    
    # 1. 언론사별 뉴스 수집 (여유 있게 수집)
    raw_yeonhap = get_google_news("연합뉴스", 4)
    raw_hankyung = get_google_news("한국경제", 2)
    raw_ytn = get_google_news("YTN", 2)
    
    # 2. 지정된 비중만큼 먼저 담기
    final_news = []
    final_news.extend(raw_yeonhap[:4])
    final_news.extend(raw_hankyung[:2])
    final_news.extend(raw_ytn[:2])
    
    # 3. [핵심] 만약 8개가 안 된다면? 남은 기사들 중에서 중복 없이 채우기
    if len(final_news) < 8:
        current_links = {n['link'] for n in final_news}
        pool = raw_yeonhap[4:] + raw_hankyung[2:] + raw_ytn[2:]
        # 시간순으로 정렬하여 신선한 뉴스부터 보충
        pool.sort(key=lambda x: x['parsed_date'], reverse=True)
        
        for extra in pool:
            if len(final_news) >= 8:
                break
            if extra['link'] not in current_links:
                final_news.append(extra)
                current_links.add(extra['link'])

    # 메시지 생성
    if not final_news:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n\n새로운 소식이 없습니다."
    else:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n"
        message += f"<b>주요 뉴스 브리핑 (연합4, 한경2, YTN2 기준)</b>\n"
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
