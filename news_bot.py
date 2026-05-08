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

    rss_url = "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(rss_url)
    raw_list = []
    
    # [설정] 경제 및 주요 통신사 우선순위 (점수가 낮을수록 상단 배치)
    # 한겨레, 경향신문은 점수를 높게(20점) 설정하여 우선순위에서 뒤로 밀리게 함
    priority_map = {
        "연합뉴스": 1, "YTN": 1, 
        "한국경제": 2, "매일경제": 2, 
        "중앙일보": 3, "동아일보": 3, "조선일보": 3,
        "한겨레": 20, "경향신문": 20 
    }
    
    ignore_words = [
        "주요뉴스", "뉴스브리핑", "뉴스특보",
        "출연", "데뷔", "열애", "결혼", "종영", "시청률", "아이돌", "멤버", "콘서트", # 연예
        "리그", "경기", "득점", "홈런", "완승", "패배", "감독", "스포츠", "우승", "선수", # 스포츠
        "당뇨", "혈당", "다이어트", "효능", "비결", "건강", "치료", "암", "복용", "피부", # 헬스
        "출시", "특가", "사전예약", "스펙", "리뷰", "가성비", "할인", "이벤트", "체험단"  # 광고/기기
    ]
    
    exclude_publishers = [
        "스포츠조선", "스포츠서울", "OSEN", "마이데일리", "스타뉴스", "뉴스엔", "TV리포트",
        "헬스조선", "코메디닷컴", "하이닥", "의학신문", "약업신문",
        "전자신문", "디지털데일리", "테크M", "IT조선", "보드나라", "씨넷코리아"
    ]

    for entry in feed.entries:
        try:
            pub_date = parser.parse(entry.published).astimezone(kst)
            if (now - datetime.timedelta(hours=24)) <= pub_date <= now:
                if entry.link in morning_history: continue

                full_title = entry.title.rsplit(' - ', 1)
                title = full_title[0].strip()
                publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
                
                if publisher in exclude_publishers: continue
                if any(word in title for word in ignore_words): continue
                
                # 전문지 키워드 필터링
                if any(p_word in publisher for p_word in ["스포츠", "헬스", "연예", "게임"]): continue
                
                score = priority_map.get(publisher, 10) # 등록되지 않은 언론사는 중간 점수(10)
                
                raw_list.append({
                    'title': title, 'link': entry.link, 'publisher': publisher,
                    'date': pub_date, 'score': score
                })
        except: continue

    # 정렬: 점수(우선순위) -> 최신순
    raw_list.sort(key=lambda x: (x['score'], -x['date'].timestamp()))

    final_news = []
    seen_titles = [] 
    pub_counts = {} # 언론사별 노출 횟수 체크
    
    for news in raw_list:
        if len(final_news) >= 8: break
        
        # 중복 제목 제거
        title_stripped = "".join(news['title'].split())[:10]
        if any(title_stripped in seen for seen in seen_titles):
            continue

        publisher = news['publisher']
        current_pub_count = pub_counts.get(publisher, 0)

        # [추가] 한겨레, 경향신문 최소화 로직
        # 해당 언론사들은 각각 최대 1개까지만 허용 (다른 곳은 2개)
        limit = 1 if publisher in ["한겨레", "경향신문"] else 2
        
        if current_pub_count < limit:
            final_news.append(news)
            seen_titles.append(title_stripped)
            pub_counts[publisher] = current_pub_count + 1

    if final_news:
        message = f"<b>📢 [{date_str} {time_tag} 주요 실시간 뉴스]</b>\n"
        message += f"<b>국제·경제·정세 주요 소식 ({len(final_news)}건)</b>\n"
        message += "━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, n in enumerate(final_news, 1):
            time_info = n['date'].strftime('%m.%d %H:%M')
            message += f"{i}. <a href='{n['link']}'>{n['title']}</a>\n"
            message += f"    └ {n['publisher']} / {time_info}\n\n"

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
