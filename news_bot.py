import feedparser
import requests
import datetime
import os
from dateutil import parser
from urllib.parse import quote

# 환경 변수 설정
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID_LIST")
CHAT_ID_LIST = [chat_id.strip() for chat_id in CHAT_ID_RAW.split(",")] if CHAT_ID_RAW else []

def get_verified_news(search_publisher, domain_keyword, target_count, start_time, end_time):
    """특정 시간 구간 내의 특정 언론사 기사를 수집"""
    exclude_query = "-연예 -스포츠 -야구 -축구 -골프 -드라마 -아이돌"
    query = quote(f'source:{search_publisher} when:1d {exclude_query}')
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(rss_url)
    
    verified_list = []
    seen_titles = set()
    
    for entry in feed.entries:
        if len(verified_list) >= target_count:
            break
            
        pub_date = parser.parse(entry.published).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
        
        # [핵심] 사용자가 요청한 시간 구간 내에 있는지 확인
        if not (start_time <= pub_date <= end_time):
            continue

        full_title = entry.title.rsplit(' - ', 1)
        title = full_title[0].strip()
        pub_name = full_title[1].strip() if len(full_title) > 1 else search_publisher
        
        if domain_keyword in entry.link or search_publisher in pub_name:
            title_key = "".join(title.split())[:15]
            if title_key not in seen_titles:
                verified_list.append({
                    'title': title,
                    'link': entry.link,
                    'publisher': pub_name,
                    'parsed_date': pub_date
                })
                seen_titles.add(title_key)
    
    # 구글이 제공한 관련성(인기) 순서를 유지하되, 그 안에서 최신순 정렬
    return verified_list

def main():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    date_str = now.strftime("%y년 %m월 %d일")
    hour = now.hour
    
    # 1. 시간대별 수집 구간 설정 (사용자 요청 기준)
    if 7 <= hour < 18:
        # 아침 7시 브리핑용: 전날 18:01 ~ 당일 06:59
        time_tag = "07시"
        sub_header = "어제 저녁부터 오늘 아침까지의 주요 뉴스"
        end_time = now.replace(hour=6, minute=59, second=59, microsecond=0)
        start_time = (end_time - datetime.timedelta(days=1)).replace(hour=18, minute=1, second=0)
    else:
        # 저녁 18시 브리핑용: 당일 07:00 ~ 당일 17:59
        time_tag = "18시"
        sub_header = "오늘 하루의 주요 뉴스 8개"
        start_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
        end_time = now.replace(hour=17, minute=59, second=59, microsecond=0)

    # 2. 언론사별 검증 수집 (연합 4 / 한경 2)
    news_yeonhap = get_verified_news("연합뉴스", "yna.co.kr", 4, start_time, end_time)
    news_hankyung = get_verified_news("한국경제", "hankyung.com", 2, start_time, end_time)
    
    # 3. 비중대로 결합
    final_news = news_yeonhap + news_hankyung
    collected_links = {n['link'] for n in final_news}
    
    # 4. 나머지 2개는 구간 내 랜덤 보충 (구글 뉴스 메인 기반)
    # (get_random_news 함수도 시간 필터가 필요하여 메인에서 직접 처리하거나 
    # 위 함수를 재활용할 수 있지만, 안정성을 위해 검증 함수로 보충합니다.)
    if len(final_news) < 8:
        extra = get_verified_news("중앙일보", "joongang.co.kr", 8 - len(final_news), start_time, end_time)
        final_news.extend(extra)

    # 메시지 생성
    if not final_news:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n<b>{sub_header}</b>\n\n지정한 시간 구간 내에 새로운 소식이 없습니다."
    else:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n"
        message += f"<b>{sub_header}</b>\n"
        message += "━━━━━━━━━━━━━━━━━━\n\n"
        for i, news in enumerate(final_news[:8], 1):
            pub_time = news['parsed_date'].strftime('%H:%M')
            message += f"{i}. <a href='{news['link']}'>{news['title']}</a> [{news['publisher']} / {pub_time}]\n\n"

    # 전송 로직
    send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for chat_id in CHAT_ID_LIST:
        requests.post(send_url, data={"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False})

if __name__ == "__main__":
    main()
