import feedparser
import requests
import datetime
import os
from dateutil import parser
from urllib.parse import quote

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID_LIST")
CHAT_ID_LIST = [chat_id.strip() for chat_id in CHAT_ID_RAW.split(",")] if CHAT_ID_RAW else []
HISTORY_FILE = "last_news.txt"

def main():
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    date_str = now.strftime("%y년 %m월 %d일")
    hour = now.hour
    
    # 직전 24시간 범위 절대 유지
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

    # 1. 광범위하게 뉴스 수집 (특정 언론사 지정 없이 전체 인기 뉴스)
    exclude_keywords = "-연예 -스포츠 -야구 -축구 -농구 -배구 -골프 -드라마 -아이돌 -연예인 -뮤직 -차트 -영화 -예능 -방송"
    query = f"{exclude_keywords} when:1d"
    rss_url = f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(rss_url)
    
    raw_news_list = []
    ban_list = ['연예', '스포츠', '축구', '야구', '골프', '드라마', '아이돌', '방송', '뮤직', '열애', '결혼', '출연', '콘서트']

    # 우선순위 점수표
    priority_map = {"연합뉴스": 1, "YTN": 2, "한국경제": 3, "매일경제": 4}

    for entry in feed.entries:
        try:
            pub_date = parser.parse(entry.published).astimezone(kst)
            if not (start_time <= pub_date <= end_time): continue
            if entry.link in morning_history: continue
            
            full_title = entry.title.rsplit(' - ', 1)
            title = full_title[0].strip()
            publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
            
            if any(word in title for word in ban_list): continue

            # 우선순위 점수 부여 (기본값은 5순위)
            score = priority_map.get(publisher, 5)
            
            raw_news_list.append({
                'title': title,
                'link': entry.link,
                'publisher': publisher,
                'parsed_date': pub_date,
                'score': score
            })
        except: continue

    # 2. 우선순위 점수(낮을수록 높음) -> 최신 시간순으로 정렬
    raw_news_list.sort(key=lambda x: (x['score'], -x['parsed_date'].timestamp()))

    # 3. 언론사별 최대 2개 제한하며 최종 8개 선별
    final_news = []
    publisher_counts = {}

    for news in raw_news_list:
        if len(final_news) >= 8: break
        
        pub = news['publisher']
        count = publisher_counts.get(pub, 0)
        
        if count < 2:
            # 제목 중복 검사
            title_key = "".join(news['title'].split())[:15]
            if any("".join(n['title'].split())[:15] == title_key for n in final_news):
                continue
                
            final_news.append(news)
            publisher_counts[pub] = count + 1

    # 4. 결과 전송
    if final_news:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n<b>24시간 내 주요 뉴스</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        for i, news in enumerate(final_news, 1):
            pub_info = news['parsed_date'].strftime('%m.%d %H:%M')
            message += f"{i}. <a href='{news['link']}'>{news['title']}</a> [{news['publisher']} / {pub_info}]\n\n"

        for chat_id in CHAT_ID_LIST:
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                             data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
            except: pass

        if 5 <= hour < 12:
            with open(HISTORY_FILE, "w") as f:
                for n in final_news:
                    f.write(n['link'] + "\n")

if __name__ == "__main__":
    main()
