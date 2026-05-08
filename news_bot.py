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
HISTORY_FILE = "last_news.txt"

def collect_with_limit(query_str, start_time, end_time, exclude_links, final_list, limit_per_pub=2):
    """지정된 쿼리 내에서 언론사별 점유율을 지키며 기사 수집"""
    exclude_keywords = "-연예 -스포츠 -야구 -축구 -농구 -배구 -골프 -드라마 -아이돌 -연예인 -뮤직 -차트 -영화 -예능 -방송"
    full_query = f"{query_str} {exclude_keywords} when:1d"
    rss_url = f"https://news.google.com/rss/search?q={quote(full_query)}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    ban_list = ['연예', '스포츠', '축구', '야구', '골프', '드라마', '아이돌', '방송', '뮤직', '열애', '결혼', '출연', '콘서트', '데뷔']
    
    for entry in feed.entries:
        if len(final_list) >= 8:
            break
            
        try:
            # 1. 중복 및 아침 뉴스 제외
            if any(n['link'] == entry.link for n in final_list) or entry.link in exclude_links:
                continue

            pub_date = parser.parse(entry.published).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
            
            # 2. 직전 24시간 절대 유지
            if start_time <= pub_date <= end_time:
                full_title = entry.title.rsplit(' - ', 1)
                title = full_title[0].strip()
                publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
                
                # 3. 개별 언론사 점유율 제한 (최대 2개)
                current_pub_count = sum(1 for n in final_list if n['publisher'] == publisher)
                if current_pub_count >= limit_per_pub:
                    continue
                
                # 4. 금지어 필터링
                if any(word in title for word in ban_list):
                    continue
                
                # 5. 제목 유사도 중복 방지
                title_key = "".join(title.split())[:15]
                if any("".join(n['title'].split())[:15] == title_key for n in final_list):
                    continue

                final_list.append({
                    'title': title,
                    'link': entry.link,
                    'publisher': publisher,
                    'parsed_date': pub_date
                })
        except:
            continue
    return final_list

def main():
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    date_str = now.strftime("%y년 %m월 %d일")
    hour = now.hour
    
    # 실행 시간 기준 직전 24시간 (절대 범위)
    end_time = now
    start_time = now - datetime.timedelta(days=1)

    morning_history = set()
    if 5 <= hour < 12:
        time_tag = "아침"
    else:
        time_tag = "오후"
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                morning_history = {line.strip() for line in f.readlines()}

    final_news = []
    
    # 우선순위 순서대로 수집 (각 언론사별 최대 2개 제한)
    priorities = ["source:연합뉴스", "source:YTN", "source:한국경제", "source:매일경제"]
    
    for source in priorities:
        if len(final_news) < 8:
            final_news = collect_with_limit(source, start_time, end_time, morning_history, final_news)
    
    # 나머지 8개까지는 기타 언론사에서 보충 (역시 언론사당 2개 제한 유지)
    if len(final_news) < 8:
        final_news = collect_with_limit("", start_time, end_time, morning_history, final_news)

    # 최종 메시지 전송
    if final_news:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n<b>24시간 내 주요 뉴스</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        for i, news in enumerate(final_news[:8], 1):
            pub_info = news['parsed_date'].strftime('%m.%d %H:%M')
            message += f"{i}. <a href='{news['link']}'>{news['title']}</a> [{news['publisher']} / {pub_info}]\n\n"

        for chat_id in CHAT_ID_LIST:
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                             data={"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False}, timeout=10)
            except: pass

        # 아침 실행시에만 기록 (오후에 중복 제거하기 위함)
        if 5 <= hour < 12:
            with open(HISTORY_FILE, "w") as f:
                for n in final_news[:8]:
                    f.write(n['link'] + "\n")

if __name__ == "__main__":
    main()
