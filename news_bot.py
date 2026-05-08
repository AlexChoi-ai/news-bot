import feedparser
import requests
import datetime
import os
from dateutil import parser

# [환경 변수 설정]
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID_LIST")
CHAT_ID_LIST = [chat_id.strip() for chat_id in CHAT_ID_RAW.split(",")] if CHAT_ID_RAW else []
HISTORY_FILE = "last_news.txt"

def main():
    # 1. 시간 설정 (KST)
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    date_str = now.strftime("%Y년 %m월 %d일")
    
    # 20분 전 발송(06:40, 17:40)을 고려한 시간대 판정
    hour = now.hour
    if 5 <= hour < 11:
        time_tag = "아침"
    elif 16 <= hour < 22:
        time_tag = "오후"
    else:
        time_tag = "실시간"

    # 2. 중복 방지를 위한 히스토리 로드
    sent_links = set()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                sent_links = {line.strip() for line in f.readlines() if line.strip()}
        except Exception as e:
            print(f"히스토리 로드 오류: {e}")

    # 3. 뉴스 데이터 가져오기 (Google News RSS)
    rss_url = "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(rss_url)
    raw_list = []
    
    # [언론사 화이트리스트 및 우선순위]
    trusted_publishers = {
        "연합뉴스": 1, "연합뉴스TV": 1, "연합인포맥스": 1, "YTN": 1,
        "한국경제": 2, "매일경제": 2, "머니투데이": 2, "서울경제": 2, "헤럴드경제": 2,
        "KBS": 3, "MBC 뉴스": 3, "SBS 뉴스": 3, "중앙일보": 3, "세계일보": 3, "문화일보": 3, "서울신문": 3,
        "조선일보": 20, "동아일보": 20, "한겨레": 20, "경향신문": 20
    }
    
    # [차단 키워드]
    ignore_words = [
        "주요뉴스", "뉴스브리핑", "뉴스특보", "출연", "데뷔", "열애", "결혼", "시청률", "아이돌", 
        "리그", "경기", "득점", "홈런", "완승", "패배", "연승", "연패", "감독", "스포츠", "우승", 
        "당뇨", "혈당", "다이어트", "효능", "비결", "건강", "치료", "암", "복용", "피부", "의학",
        "출시", "특가", "사전 예약", "사전예약", "스펙", "리뷰", "가성비", "할인", "이벤트", "체험단"
    ]

    # 4. 필터링 로직
    for entry in feed.entries:
        try:
            pub_date = parser.parse(entry.published).astimezone(kst)
            # 최근 24시간 이내 기사만 대상
            if (now - datetime.timedelta(hours=24)) <= pub_date <= now:
                
                # 중복 링크 체크 (기존 발송 여부)
                if entry.link in sent_links:
                    continue

                full_title = entry.title.rsplit(' - ', 1)
                title = full_title[0].strip()
                raw_pub = full_title[1].strip() if len(full_title) > 1 else ""
                
                # 언론사 매칭 (부분 일치 허용)
                matched_pub = next((p for p in trusted_publishers if p in raw_pub), None)
                if not matched_pub:
                    continue
                
                # 키워드 차단
                if any(word in title for word in ignore_words):
                    continue
                
                score = trusted_publishers.get(matched_pub, 10)
                raw_list.append({
                    'title': title, 'link': entry.link, 'publisher': matched_pub,
                    'date': pub_date, 'score': score
                })
        except:
            continue

    # 5. 정렬 및 최종 8개 선별
    # 우선순위 점수(낮을수록 높음) -> 최신순
    raw_list.sort(key=lambda x: (x['score'], -x['date'].timestamp()))

    final_news = []
    seen_titles = set() 
    pub_counts = {} 
    min_exposure_list = [k for k, v in trusted_publishers.items() if v == 20]

    for news in raw_list:
        if len(final_news) >= 8:
            break
        
        # 제목 중복 제거 (공백 제거 후 앞 10자 비교)
        title_key = "".join(news['title'].split())[:10]
        if title_key in seen_titles:
            continue

        publisher = news['publisher']
        current_count = pub_counts.get(publisher, 0)
        
        # 언론사별 노출 제한 (3순위는 1개, 나머지는 2개)
        limit = 1 if publisher in min_exposure_list else 2
        
        if current_count < limit:
            final_news.append(news)
            seen_titles.add(title_key)
            pub_counts[publisher] = current_count + 1

    # 6. 메시지 생성 및 전송
    if final_news:
        header = f"<b>📢 [{date_str} {time_tag} 주요 뉴스]</b>\n"
        header += f"<b>국제·경제·정세 소식 ({len(final_news)}건)</b>\n"
        header += "━━━━━━━━━━━━━━━━━━\n\n"
        
        body = ""
        for i, n in enumerate(final_news, 1):
            time_info = n['date'].strftime('%m.%d %H:%M')
            body += f"{i}. <a href='{n['link']}'>{n['title']}</a>\n"
            body += f"    └ {n['publisher']} / {time_info}\n\n"

        full_message = header + body

        for chat_id in CHAT_ID_LIST:
            send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            try:
                requests.post(send_url, data={
                    "chat_id": chat_id, "text": full_message, 
                    "parse_mode": "HTML", "disable_web_page_preview": False
                }, timeout=15)
            except Exception as e:
                print(f"전송 실패 ({chat_id}): {e}")

        # 7. 히스토리 저장 (추가 모드 'a'를 사용하여 누적)
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            for n in final_news:
                f.write(n['link'] + "\n")
    else:
        print("조건에 맞는 새로운 뉴스가 없습니다.")

if __name__ == "__main__":
    main()
