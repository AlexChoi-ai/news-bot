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

    # 구글 뉴스 헤드라인 RSS
    rss_url = "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    raw_list = []
    
    # [설정] 우선순위 언론사
    priority_map = {"연합뉴스": 1, "YTN": 2, "한국경제": 3, "매일경제": 4}
    
    # [추가] 제외 키워드 (연예, 스포츠, 건강/광고성)
    ignore_words = [
        "주요뉴스", "뉴스브리핑", "오늘의", "이 시각", "자막뉴스", "뉴스특보",
        "출연", "데뷔", "결혼", "이혼", "열애", "종영", "시청률", "컴백", "독점", # 연예
        "리그", "경기", "득점", "홈런", "완승", "패배", "감독", "스포츠", "우승", # 스포츠
        "당뇨", "혈당", "다이어트", "효능", "비결", "건강", "치료", "항암"      # 헬스/광고
    ]
    
    # [추가] 제외 언론사 (연예, 스포츠, 헬스 전문지)
    exclude_publishers = [
        "스포츠조선", "스포츠서울", "OSEN", "마이데일리", "스타뉴스", "뉴스엔", 
        "헬스조선", "코메디닷컴", "하이닥", "일간스포츠", "엑스포츠뉴스"
    ]

    for entry in feed.entries:
        try:
            pub_date = parser.parse(entry.published).astimezone(kst)
            # 24시간 이내 기사만
            if (now - datetime.timedelta(hours=24)) <= pub_date <= now:
                if entry.link in morning_history: continue

                full_title = entry.title.rsplit(' - ', 1)
                title = full_title[0].strip()
                publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
                
                # [필터 1] 전문지 제외 (연예/스포츠/헬스 매체)
                if publisher in exclude_publishers: continue
                
                # [필터 2] 제목 키워드 필터링
                if any(word in title for word in ignore_words): continue
                
                # [필터 3] 특정 서브 매체 제외 (광고성 기사 방지)
                if "헬스" in publisher or "스포츠" in publisher: continue
                
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
        if pub_counts.get(p, 0) < 2:
            t_short = "".join(news['title'].split())[:12]
            if not any("".join(n['title'].split())[:12] == t_short for n in final_news):
                final_news.append(news)
                pub_counts[p] = pub_counts.get(p, 0) + 1

    if final_news:
        message = f"<b>📢 [{date_str} {time_tag} 헤드라인]</b>\n"
        message += f"<b>구글 AI 선정 주요 뉴스 ({len(final_news)}건)</b>\n"
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
