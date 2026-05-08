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
    
    # [화이트리스트] 대한민국 주요 신뢰 언론사 20선 (이 외 언론사는 자동 제외)
    # 1순위: 통신사 및 경제지 / 2순위: 지상파 및 주요 일간지 / 3순위: 최소 노출 일간지
    trusted_publishers = {
        # 1순위 (강력 추천)
        "연합뉴스": 1, "연합뉴스TV": 1, "연합인포맥스": 1, "YTN": 1,
        "한국경제": 2, "매일경제": 2, "머니투데이": 2, "서울경제": 2, "헤럴드경제": 2,
        # 2순위 (지상파 및 주요지)
        "KBS": 3, "MBC 뉴스": 3, "SBS 뉴스": 3, "중앙일보": 3, "세계일보": 3, "문화일보": 3, "서울신문": 3,
        # 3순위 (최소 노출 대상)
        "조선일보": 20, "동아일보": 20, "한겨레": 20, "경향신문": 20
    }
    
    # [강력 차단 키워드] 스포츠, 헬스 관련 정밀 필터링
    ignore_words = [
        "주요뉴스", "뉴스브리핑", "뉴스특보",
        "출연", "데뷔", "열애", "결혼", "시청률", "아이돌", "멤버", "콘서트", 
        "리그", "경기", "득점", "홈런", "완승", "패배", "연승", "연패", "감독", "스포츠", "우승", "선수", "타점", # 스포츠 강화
        "당뇨", "혈당", "다이어트", "효능", "비결", "건강", "치료", "암", "복용", "피부", "의학", "교수 연구팀", # 헬스 강화
        "출시", "특가", "사전 예약", "사전예약", "스펙", "리뷰", "가성비", "할인", "이벤트", "체험단"
    ]

    for entry in feed.entries:
        try:
            pub_date = parser.parse(entry.published).astimezone(kst)
            if (now - datetime.timedelta(hours=24)) <= pub_date <= now:
                if entry.link in morning_history: continue

                full_title = entry.title.rsplit(' - ', 1)
                title = full_title[0].strip()
                publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
                
                # [로직 1] 화이트리스트 검사: 신뢰 언론사 리스트에 없으면 무조건 제외
                if publisher not in trusted_publishers:
                    continue
                
                # [로직 2] 키워드 검사: "연승", "교수 연구팀" 등 불필요한 주제 제외
                if any(word in title for word in ignore_words):
                    continue
                
                score = trusted_publishers.get(publisher, 10)
                
                raw_list.append({
                    'title': title, 'link': entry.link, 'publisher': publisher,
                    'date': pub_date, 'score': score
                })
        except: continue

    # 정렬: 우선순위 점수 -> 최신순
    raw_list.sort(key=lambda x: (x['score'], -x['date'].timestamp()))

    final_news = []
    seen_titles = [] 
    pub_counts = {} 
    
    # 최소 노출을 적용할 언론사 리스트 (점수 20점 그룹)
    min_exposure_list = [k for k, v in trusted_publishers.items() if v == 20]

    for news in raw_list:
        if len(final_news) >= 8: break
        
        # 중복 제목 제거 (공백 제거 후 앞 10글자 비교)
        title_stripped = "".join(news['title'].split())[:10]
        if any(title_stripped in seen for seen in seen_titles):
            continue

        publisher = news['publisher']
        current_pub_count = pub_counts.get(publisher, 0)
        
        # 노출 제한: 3순위 언론사는 최대 1개, 나머지는 최대 2개
        limit = 1 if publisher in min_exposure_list else 2
        
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
