import feedparser
import requests
import datetime
import os
from dateutil import parser

# 환경 변수 설정
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID_LIST")
CHAT_ID_LIST = [chat_id.strip() for chat_id in CHAT_ID_RAW.split(",")] if CHAT_ID_RAW else []
HISTORY_FILE = "last_news.txt"

def main():
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    date_str = now.strftime("%y년 %m월 %d일")
    hour = now.hour
    time_tag = "아침" if 5 <= hour < 12 else "오후"
    
    morning_history = set()
    if time_tag == "오후" and os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                morning_history = {line.strip() for line in f.readlines()}
        except: pass

    # [수정] 검색 대신 '구글 뉴스 헤드라인' RSS 주소 사용 (가장 중요한 뉴스 위주)
    rss_url = "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    raw_list = []
    
    # 우선순위 및 제외 단어 설정
    priority_map = {"연합뉴스": 1, "YTN": 2, "한국경제": 3, "매일경제": 4}
    ignore_words = ["주요뉴스", "뉴스브리핑", "오늘의", "이 시각", "자막뉴스", "뉴스특보"]

    for entry in feed.entries:
        try:
            pub_date = parser.parse(entry.published).astimezone(kst)
            # 24시간 이내 기사만
            if (now - datetime.timedelta(hours=24)) <= pub_date <= now:
                if entry.link in morning_history: continue

                full_title = entry.title.rsplit(' - ', 1)
                title = full_title[0].strip()
                publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
                
                # [필터 1] "주요뉴스" 같은 브리핑용 기사 제목은 제외
                if any(word in title for word in ignore_words): continue
                
                # [필터 2] 연합인포맥스, biz.sbs 등 서브 매체 점수 하향 (본진 위주)
                score = priority_map.get(publisher, 10)
                
                raw_list.append({
                    'title': title, 'link': entry.link, 'publisher': publisher,
                    'date': pub_date, 'score': score
                })
        except: continue

    # 정렬: 1순위 언론사 점수, 2순위 최신순
    raw_list.sort(key=lambda x: (x['score'], -x['date'].timestamp()))

    final_news = []
    pub_counts = {}
    
    for news in raw_list:
        if len(final_news) >= 8: break
        
        p = news['publisher']
        # 언론사당 2개 제한하여 다양성 확보
        if pub_counts.get(p, 0) < 2:
            # 제목 중복 제거
            t_short = "".join(news['title'].split())[:12]
            if not any("".join(n['title'].split())[:12] == t_short for n in final_news):
                final_news.append(news)
                pub_counts[p] = pub_counts.get(p, 0) + 1

    if final_news:
        message = f"<b>📢 [{date_str} {time_tag} 헤드라인]</b>\n"
        message += f"<b>구글 AI 선정 주요 뉴스 (8건)</b>\n"
        message += "━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, n in enumerate(final_news, 1):
            time_info = n['date'].strftime('%m.%d %H:%M')
            message += f"{i}. <a href='{n['link']}'>{n['title']}</a>\n"
            message += f"   └ {n['publisher']} / {time_info}\n\n"

        for chat_id in CHAT_ID_LIST:
            send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            requests.post(send_url, data={
                "chat_id": chat_id, "text": message, 
                "parse_mode": "HTML", "disable_web_page_preview": False
            }, timeout=15)

        if time_tag == "아침":
            with open(HISTORY_FILE, "w") as f:
                for n in final_news: f.write(n['link'] + "\n")
    else:
        print("조건에 맞는 뉴스를 찾지 못했습니다.")

if __name__ == "__main__":
    main()
