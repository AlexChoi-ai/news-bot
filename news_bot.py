import feedparser
import requests
import datetime
import os
from dateutil import parser
from urllib.parse import quote

# [기존 유지] 환경 변수 설정
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID_LIST")
CHAT_ID_LIST = [chat_id.strip() for chat_id in CHAT_ID_RAW.split(",")] if CHAT_ID_RAW else []
HISTORY_FILE = "last_news.txt"

def main():
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    date_str = now.strftime("%y년 %m월 %d일")
    hour = now.hour
    
    # 시간 태그 설정
    time_tag = "아침" if 5 <= hour < 12 else "오후"
    
    # [핵심] 실행 시간 기준 직전 24시간을 절대 범위로 설정
    end_time = now
    start_time = now - datetime.timedelta(hours=24)

    # 아침 뉴스 기록 불러오기 (오후 실행 시 중복 제거용)
    morning_history = set()
    if time_tag == "오후" and os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                morning_history = {line.strip() for line in f.readlines()}
        except: pass

    # 1. 뉴스 데이터 수집 (전체 뉴스 100개를 가져와서 필터링)
    exclude_keywords = "-연예 -스포츠 -야구 -축구 -농구 -배구 -골프 -드라마 -아이돌 -연예인 -뮤직 -차트 -영화 -예능 -방송"
    query = f"{exclude_keywords} when:1d"
    rss_url = f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(rss_url)
    
    raw_list = []
    ban_list = ['연예', '스포츠', '축구', '야구', '골프', '드라마', '아이돌', '방송', '뮤직', '열애', '결혼', '출연', '콘서트', '데뷔']
    priority_map = {"연합뉴스": 1, "YTN": 2, "한국경제": 3, "매일경제": 4}

    for entry in feed.entries:
        try:
            pub_date = parser.parse(entry.published).astimezone(kst)
            
            # 시간 범위 체크 및 중복 체크
            if (start_time <= pub_date <= end_time) and (entry.link not in morning_history):
                full_title = entry.title.rsplit(' - ', 1)
                title = full_title[0].strip()
                publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
                
                if any(word in title for word in ban_list): continue
                
                score = priority_map.get(publisher, 5) # 우선순위 외는 5점
                raw_list.append({
                    'title': title, 'link': entry.link, 'publisher': publisher,
                    'parsed_date': pub_date, 'score': score
                })
        except: continue

    # 2. 우선순위 정렬 (우선순위 점수 순 -> 최신 시간 순)
    raw_list.sort(key=lambda x: (x['score'], -x['parsed_date'].timestamp()))

    # 3. 언론사별 2개 제한하며 8개 선별
    final_news = []
    pub_counts = {}
    
    for news in raw_list:
        if len(final_news) >= 8: break
        
        p = news['publisher']
        count = pub_counts.get(p, 0)
        
        if count < 2:
            # 제목 중복 방지 (앞 15자 비교)
            t_key = "".join(news['title'].split())[:15]
            if not any("".join(n['title'].split())[:15] == t_key for n in final_news):
                final_news.append(news)
                pub_counts[p] = count + 1

    # 4. 메시지 전송
    if final_news:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n<b>24시간 내 주요 뉴스</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        for i, news in enumerate(final_news, 1):
            p_info = news['parsed_date'].strftime('%m.%d %H:%M')
            message += f"{i}. <a href='{news['link']}'>{news['title']}</a> [{news['publisher']} / {p_info}]\n\n"

        send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        for chat_id in CHAT_ID_LIST:
            try:
                requests.post(send_url, data={
                    "chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False
                }, timeout=15)
            except: pass

        # 아침 실행 시 역사 기록 저장
        if time_tag == "아침":
            with open(HISTORY_FILE, "w") as f:
                for n in final_news:
                    f.write(n['link'] + "\n")
