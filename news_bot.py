import feedparser
import requests
import datetime
import os
from dateutil import parser
from urllib.parse import quote

# 1. 환경 변수 설정
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID_LIST")
CHAT_ID_LIST = [chat_id.strip() for chat_id in CHAT_ID_RAW.split(",")] if CHAT_ID_RAW else []
HISTORY_FILE = "last_news.txt"

def main():
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    date_str = now.strftime("%y년 %m월 %d일")
    hour = now.hour
    
    # 시간 태그 (아침/오후)
    time_tag = "아침" if 5 <= hour < 12 else "오후"
    
    # 아침 뉴스 기록 불러오기 (오후 중복 방지용)
    morning_history = set()
    if time_tag == "오후" and os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                morning_history = {line.strip() for line in f.readlines()}
        except: pass

    # 2. 구글 뉴스 수집
    # 검색어가 너무 복잡하면 오류가 날 수 있어 핵심 제외어만 포함
    exclude = "-연예 -스포츠 -드라마 -아이돌 -방송"
    query = f"주요뉴스 {exclude} when:1d"
    rss_url = f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    raw_list = []
    
    # 우선순위 설정
    priority_map = {"연합뉴스": 1, "YTN": 2, "한국경제": 3, "매일경제": 4}

    for entry in feed.entries:
        try:
            # 24시간 내 기사만 필터링
            pub_date = parser.parse(entry.published).astimezone(kst)
            if (now - datetime.timedelta(hours=24)) <= pub_date <= now:
                if entry.link in morning_history: continue

                full_title = entry.title.rsplit(' - ', 1)
                title = full_title[0].strip()
                publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
                
                # 우선순위 점수 부여
                score = priority_map.get(publisher, 5)
                raw_list.append({
                    'title': title, 'link': entry.link, 'publisher': publisher,
                    'date': pub_date, 'score': score
                })
        except: continue

    # 3. 우선순위 및 중복 제거 정렬
    # 1순위: 언론사 점수(낮을수록 높음), 2순위: 최신 시간순
    raw_list.sort(key=lambda x: (x['score'], -x['date'].timestamp()))

    final_news = []
    pub_counts = {}
    
    for news in raw_list:
        if len(final_news) >= 8: break
        
        p = news['publisher']
        if pub_counts.get(p, 0) < 2: # 언론사당 최대 2개
            # 제목 앞글자 중복 방지
            t_short = "".join(news['title'].split())[:12]
            if not any("".join(n['title'].split())[:12] == t_short for n in final_news):
                final_news.append(news)
                pub_counts[p] = pub_counts.get(p, 0) + 1

    # 4. 텔레그램 전송
    if final_news:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n"
        message += f"<b>주요 언론사 우선 선별 (8건)</b>\n"
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

        # 아침 기록 저장
        if time_tag == "아침":
            with open(HISTORY_FILE, "w") as f:
                for n in final_news:
                    f.write(n['link'] + "\n")
    else:
        print("전송할 뉴스를 찾지 못했습니다.")

if __name__ == "__main__":
    main()
