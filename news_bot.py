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
    
    # [설정] 경제 및 시사 중심 언론사 우선순위
    priority_map = {"연합뉴스": 1, "YTN": 1, "한국경제": 2, "매일경제": 2, "경향신문": 3, "한겨레": 3, "중앙일보": 3, "동아일보": 3}
    
    # [강화] 제외 키워드 (전자제품 광고, 헬스, 스포츠, 연예)
    ignore_words = [
        "주요뉴스", "뉴스브리핑", "뉴스특보",
        "출연", "데뷔", "열애", "결혼", "종영", "시청률", "아이돌", "멤버", "콘서트", # 연예
        "리그", "경기", "득점", "홈런", "완승", "패배", "감독", "스포츠", "우승", "선수", # 스포츠
        "당뇨", "혈당", "다이어트", "효능", "비결", "건강", "치료", "암", "복용", "피부", # 헬스
        "출시", "특가", "사전예약", "스펙", "리뷰", "가성비", "할인", "이벤트", "체험단"  # 전자제품/광고
    ]
    
    # [강화] 제외 언론사 리스트 (전문지 및 광고성 매체)
    exclude_publishers = [
        "스포츠조선", "스포츠서울", "OSEN", "마이데일리", "스타뉴스", "뉴스엔", "TV리포트", # 연예/스포츠
        "헬스조선", "코메디닷컴", "하이닥", "의학신문", "약업신문", # 헬스
        "전자신문", "디지털데일리", "테크M", "IT조선", "보드나라", "씨넷코리아", # IT/기기
        "머니S", "조세일보", "파이낸셜뉴스" # 일부 광고성 기사가 잦은 매체 (선택적 제외 가능)
    ]

    for entry in feed.entries:
        try:
            pub_date = parser.parse(entry.published).astimezone(kst)
            if (now - datetime.timedelta(hours=24)) <= pub_date <= now:
                if entry.link in morning_history: continue

                full_title = entry.title.rsplit(' - ', 1)
                title = full_title[0].strip()
                publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
                
                # 필터링 적용
                if publisher in exclude_publishers: continue
                if any(word in title for word in ignore_words): continue
                if any(p_word in publisher for p_word in ["스포츠", "헬스", "연예", "게임", "리뷰"]): continue
                
                score = priority_map.get(publisher, 10)
                
                raw_list.append({
                    'title': title, 'link': entry.link, 'publisher': publisher,
                    'date': pub_date, 'score': score
                })
        except: continue

    # 정렬: 점수(언론사) -> 최신순
    raw_list.sort(key=lambda x: (x['score'], -x['date'].timestamp()))

    final_news = []
    seen_titles = [] # 중복 체크용 리스트
    
    for news in raw_list:
        if len(final_news) >= 8: break
        
        # [중복 제거 로직 강화] 
        # 공백 제거 후 앞 10글자가 같거나, 제목의 70% 이상이 유사한 경우 제외
        title_stripped = "".join(news['title'].split())[:10]
        if any(title_stripped in seen for seen in seen_titles):
            continue

        p = news['publisher']
        if final_news.count(p) < 2: # 동일 언론사 도배 방지
            final_news.append(news)
            seen_titles.append(title_stripped)

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
