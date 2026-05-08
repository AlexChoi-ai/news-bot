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
    
    # 직전 24시간 범위 (절대 유지)
    end_time = now
    start_time = now - datetime.timedelta(days=1)

    morning_history = set()
    if 5 <= hour < 12:
        time_tag = "아침"
    else:
        time_tag = "오후"
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    morning_history = {line.strip() for line in f.readlines()}
            except: pass

    # 1. 뉴스 수집 (검색 범위를 넓히기 위해 when:1d 제거)
    exclude_keywords = "-연예 -스포츠 -야구 -축구 -농구 -배구 -골프 -드라마 -아이돌 -연예인 -뮤직 -차트 -영화 -예능 -방송"
    # 검색 쿼리에 '뉴스'를 추가하여 결과값 확보
    rss_url = f"https://news.google.com/rss/search?q={quote(exclude_keywords)}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(rss_url)
    
    raw_news_list = []
    ban_list = ['연예', '스포츠', '축구', '야구', '골프', '드라마', '아이돌', '방송', '뮤직', '열애', '결혼', '출연', '콘서트', '데뷔']
    priority_map = {"연합뉴스": 1, "YTN": 2, "한국경제": 3, "매일경제": 4}

    if not feed.entries:
        print("RSS 피드에서 기사를 가져오지 못했습니다.")

    for entry in feed.entries:
        try:
            pub_date = parser.parse(entry.published).astimezone(kst)
            
            # 시간 범위 체크 (24시간 내)
            if not (start_time <= pub_date <= end_time): continue
            # 아침 중복 제외
            if entry.link in morning_history: continue
            
            full_title = entry.title.rsplit(' - ', 1)
            title = full_title[0].strip()
            publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
            
            if any(word in title for word in ban_list): continue

            score = priority_map.get(publisher, 5)
            raw_news_list.append({
                'title': title, 'link': entry.link, 'publisher': publisher,
                'parsed_date': pub_date, 'score': score
            })
        except: continue

    # 우선순위(점수 낮은 순) -> 최신순 정렬
    raw_news_list.sort(key=lambda x: (x['score'], -x['parsed_date'].timestamp()))

    # 2. 선별 로직 (점유율 제한을 2개에서 시작하되, 부족하면 점진적 완화)
    final_news = []
    max_per_pub = 2
    
    while len(final_news) < 8 and max_per_pub <= 4:
        final_news = []
        publisher_counts = {}
        for news in raw_news_list:
            if len(final_news) >= 8: break
            pub = news['publisher']
            count = publisher_counts.get(pub, 0)
            
            if count < max_per_pub:
                title_key = "".join(news['title'].split())[:15]
                if any("".join(n['title'].split())[:15] == title_key for n in final_news):
                    continue
                final_news.append(news)
                publisher_counts[pub] = count + 1
        
        if len(final_news) >= 8: break
        max_per_pub += 1 # 8개가 안 채워지면 언론사당 제한을 1개씩 늘림

    # 3. 메시지 전송 및 에러 핸들링
    if final_news:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n<b>24시간 내 주요 뉴스</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        for i, news in enumerate(final_news, 1):
            pub_info = news['parsed_date'].strftime('%m.%d %H:%M')
            message += f"{i}. <a href='{news['link']}'>{news['title']}</a> [{news['publisher']} / {pub_info}]\n\n"

        for chat_id in CHAT_ID_LIST:
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, 
                timeout=15
            )
            if response.status_code != 200:
                print(f"전송 실패: {response.text}")

        if 5 <= hour < 12:
            with open(HISTORY_FILE, "w") as f:
                for n in final_news:
                    f.write(n['link'] + "\n")
    else:
        print("조건에 맞는 뉴스 기사가 검색되지 않았습니다.")

if __name__ == "__main__":
    main()
