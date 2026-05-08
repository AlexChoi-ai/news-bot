import feedparser
import requests
import datetime
import os
from dateutil import parser
from urllib.parse import quote

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID_LIST")
CHAT_ID_LIST = [chat_id.strip() for chat_id in CHAT_ID_RAW.split(",")] if CHAT_ID_RAW else []

def get_flexible_news(publisher, domain_keyword, target_count, start_time, end_time):
    # 검색 범위를 1d로 넓게 잡아서 충분한 기사 후보군을 확보합니다.
    exclude_query = "-연예 -스포츠 -야구 -축구 -골프 -드라마 -아이돌"
    query = quote(f'source:{publisher} when:1d {exclude_query}')
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(rss_url)
    
    news_pool = []
    seen_titles = set()
    
    for entry in feed.entries:
        pub_date = parser.parse(entry.published).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
        
        # [수정] 1순위: 지정된 시간 구간 내의 기사만 담습니다.
        if start_time <= pub_date <= end_time:
            full_title = entry.title.rsplit(' - ', 1)
            title = full_title[0].strip()
            pub_name = full_title[1].strip() if len(full_title) > 1 else publisher
            
            # 도메인 검증 (낚시 방지)
            if domain_keyword in entry.link or publisher in pub_name:
                title_key = "".join(title.split())[:15]
                if title_key not in seen_titles:
                    news_pool.append({
                        'title': title, 'link': entry.link, 'publisher': pub_name, 'parsed_date': pub_date
                    })
                    seen_titles.add(title_key)
    
    # 해당 구간 뉴스를 최신순(인기순 기반)으로 정렬
    news_pool.sort(key=lambda x: x['parsed_date'], reverse=True)
    return news_pool[:target_count]

def main():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    date_str = now.strftime("%y년 %m월 %d일")
    hour = now.hour
    
    # 시간대별 수집 구간 설정
    if 7 <= hour < 18:
        time_tag = "07시"; sub_header = "어제 저녁부터 오늘 아침까지의 주요 뉴스"
        end_time = now.replace(hour=6, minute=59, second=59)
        start_time = (end_time - datetime.timedelta(days=1)).replace(hour=18, minute=1, second=0)
    else:
        time_tag = "18시"; sub_header = "오늘 하루의 주요 뉴스 8개"
        start_time = now.replace(hour=7, minute=0, second=0)
        end_time = now.replace(hour=17, minute=59, second=59)

    # 1. 메인 수집 (비중: 연합 4, 한경 2)
    final_news = []
    final_news.extend(get_flexible_news("연합뉴스", "yna.co.kr", 4, start_time, end_time))
    final_news.extend(get_flexible_news("한국경제", "hankyung.com", 2, start_time, end_time))
    
    # 2. 부족분 채우기 (연합/한경 외 다른 주요 언론사 포함)
    if len(final_news) < 8:
        current_links = {n['link'] for n in final_news}
        # 구글 뉴스 전체에서 해당 시간대 기사 보충
        query = quote(f'when:1d -연예 -스포츠')
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            if len(final_news) >= 8: break
            pub_date = parser.parse(entry.published).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
            if start_time <= pub_date <= end_time and entry.link not in current_links:
                full_title = entry.title.rsplit(' - ', 1)
                final_news.append({
                    'title': full_title[0].strip(),
                    'link': entry.link,
                    'publisher': full_title[1].strip() if len(full_title) > 1 else "뉴스",
                    'parsed_date': pub_date
                })
                current_links.add(entry.link)

    # 3. [최종 보루] 그래도 8개가 안 되면 시간 필터를 해제하고 가장 최신 뉴스라도 채움
    if len(final_news) < 8:
        feed = feedparser.parse("https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko")
        for entry in feed.entries:
            if len(final_news) >= 8: break
            if entry.link not in {n['link'] for n in final_news}:
                full_title = entry.title.rsplit(' - ', 1)
                final_news.append({
                    'title': full_title[0].strip(),
                    'link': entry.link,
                    'publisher': full_title[1].strip() if len(full_title) > 1 else "뉴스",
                    'parsed_date': parser.parse(entry.published).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
                })

    # 메시지 생성 및 전송 (생략 없이 8개 유지)
    message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n<b>{sub_header}</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    for i, news in enumerate(final_news[:8], 1):
        pub_time = news['parsed_date'].strftime('%H:%M')
        message += f"{i}. <a href='{news['link']}'>{news['title']}</a> [{news['publisher']} / {pub_time}]\n\n"

    for chat_id in CHAT_ID_LIST:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                      data={"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False})

if __name__ == "__main__":
    main()
