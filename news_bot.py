import feedparser
import requests
import datetime
import os
from dateutil import parser
from urllib.parse import quote

# [기존 유지] 환경 변수 및 설정
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID_LIST")
CHAT_ID_LIST = [chat_id.strip() for chat_id in CHAT_ID_RAW.split(",")] if CHAT_ID_RAW else []

def get_news_by_time(query_str, target_count, start_time, end_time):
    """구글 뉴스에서 인기순으로 가져오되, 연예/스포츠를 배제하고 시간 구간 필터링"""
    
    exclude_keywords = "-연예 -스포츠 -야구 -축구 -농구 -배구 -골프 -드라마 -아이돌 -연예인 -뮤직 -차트 -영화 -예능 -방송"
    full_query = f"{query_str} {exclude_keywords} when:1d"
    rss_url = f"https://news.google.com/rss/search?q={quote(full_query)}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    results = []
    seen_titles = set()
    
    ban_list = ['연예', '스포츠', '축구', '야구', '골프', '드라마', '아이돌', '방송', '뮤직', '열애', '결혼', '출연']
    
    for entry in feed.entries:
        # 필터링을 통과한 기사가 타겟 숫자를 채우면 중단
        if len(results) >= target_count:
            break
            
        try:
            pub_date = parser.parse(entry.published).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
            
            # 시간 구간 내 기사인지 확인
            if start_time <= pub_date <= end_time:
                full_title = entry.title.rsplit(' - ', 1)
                title = full_title[0].strip()
                publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
                
                if any(word in title for word in ban_list):
                    continue
                    
                title_key = "".join(title.split())[:15]
                if title_key not in seen_titles:
                    results.append({
                        'title': title,
                        'link': entry.link,
                        'publisher': publisher,
                        'parsed_date': pub_date
                    })
                    seen_titles.add(title_key)
        except Exception:
            continue
            
    return results

def main():
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    date_str = now.strftime("%y년 %m월 %d일")
    hour = now.hour
    
    # [기존 유지] 시간 구간 설정
    if 7 <= hour < 18:
        time_tag = "07시"
        sub_header = "어제 저녁부터 오늘 아침까지의 주요 뉴스"
        end_time = now.replace(hour=6, minute=59, second=59, microsecond=0)
        start_time = (end_time - datetime.timedelta(days=1)).replace(hour=18, minute=1, second=0, microsecond=0)
    else:
        time_tag = "18시"
        sub_header = "오늘 하루의 주요 뉴스 8개"
        start_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
        end_time = now.replace(hour=17, minute=59, second=59, microsecond=0)

    final_news = []
    collected_links = set()
    
    # 1. 연합뉴스 수집 (최대 4개 목표, 검색은 넉넉하게 15개 시도)
    yonhap = get_news_by_time("source:연합뉴스", 4, start_time, end_time)
    for n in yonhap:
        final_news.append(n)
        collected_links.add(n['link'])
    
    # 2. 한국경제 수집 (최대 2개 목표)
    hankyung = get_news_by_time("source:한국경제", 2, start_time, end_time)
    for n in hankyung:
        if n['link'] not in collected_links:
            final_news.append(n)
            collected_links.add(n['link'])
            
    # 3. 8개가 채워질 때까지 전체 언론사에서 수집 (중복 제외)
    # 검색 범위를 넉넉히 20개로 잡아 필터링 후에도 8개가 남도록 함
    if len(final_news) < 8:
        needed = 8 - len(final_news)
        general = get_news_by_time("", 20, start_time, end_time)
        for n in general:
            if len(final_news) >= 8:
                break
            if n['link'] not in collected_links:
                final_news.append(n)
                collected_links.add(n['link'])

    # 메시지 전송 로직
    if final_news:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n<b>{sub_header}</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        # 정확히 8개만 슬라이싱하여 전송
        for i, news in enumerate(final_news[:8], 1):
            pub_time = news['parsed_date'].strftime('%H:%M')
            message += f"{i}. <a href='{news['link']}'>{news['title']}</a> [{news['publisher']} / {pub_time}]\n\n"

        send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        for chat_id in CHAT_ID_LIST:
            try:
                requests.post(send_url, data={
                    "chat_id": chat_id, 
                    "text": message, 
                    "parse_mode": "HTML", 
                    "disable_web_page_preview": False
                }, timeout=10)
            except Exception as e:
                print(f"전송 실패: {e}")

if __name__ == "__main__":
    main()
