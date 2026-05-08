import feedparser
import requests
import datetime
import os
from dateutil import parser
from urllib.parse import quote

# 환경 변수 설정
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID_LIST")
CHAT_ID_LIST = [chat_id.strip() for chat_id in CHAT_ID_RAW.split(",")] if CHAT_ID_RAW else []
HISTORY_FILE = "last_news.txt"

def get_news_with_strict_rules(query_str, start_time, end_time, morning_history):
    """구글 뉴스에서 기사를 가져와 기본 필터링만 수행하여 반환"""
    exclude_keywords = "-연예 -스포츠 -야구 -축구 -농구 -배구 -골프 -드라마 -아이돌 -연예인 -뮤직 -차트 -영화 -예능 -방송"
    full_query = f"{query_str} {exclude_keywords} when:1d"
    rss_url = f"https://news.google.com/rss/search?q={quote(full_query)}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    results = []
    ban_list = ['연예', '스포츠', '축구', '야구', '골프', '드라마', '아이돌', '방송', '뮤직', '열애', '결혼', '출연', '데뷔']

    for entry in feed.entries:
        try:
            pub_date = parser.parse(entry.published).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
            
            # 1. 직전 24시간 범위 확인
            if start_time <= pub_date <= end_time:
                # 2. 아침 뉴스 중복 제외
                if entry.link in morning_history:
                    continue

                full_title = entry.title.rsplit(' - ', 1)
                title = full_title[0].strip()
                publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
                
                # 3. 금지어 필터링
                if any(word in title for word in ban_list):
                    continue

                results.append({
                    'title': title,
                    'link': entry.link,
                    'publisher': publisher,
                    'parsed_date': pub_date
                })
        except:
            continue
    return results

def main():
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    date_str = now.strftime("%y년 %m월 %d일")
    hour = now.hour
    
    # 시간 태그 설정
    time_tag = "아침" if 5 <= hour < 12 else "오후"
    
    # [수정] 성공했던 코드처럼 직전 24시간을 여유 있게 설정
    end_time = now
    start_time = now - datetime.timedelta(hours=24)

    # 아침 뉴스 기록 불러오기 (오후 중복 방지용)
    morning_history = set()
    if time_tag == "오후" and os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                morning_history = {line.strip() for line in f.readlines()}
        except: pass

    # 1. 모든 뉴스 통합 수집 (우선순위를 위해 전체 검색)
    all_raw_news = get_news_with_strict_rules("", start_time, end_time, morning_history)

    # 2. 우선순위 및 점유율 제한 적용
    final_news = []
    publisher_counts = {}
    priority_order = ["연합뉴스", "YTN", "한국경제", "매일경제"]

    # 2-1. 우선순위 언론사 기사 먼저 채우기 (언론사당 2개씩)
    for target_pub in priority_order:
        pub_found_count = 0
        for news in all_raw_news:
            if len(final_news) >= 8: break
            if target_pub in news['publisher'] and pub_found_count < 2:
                # 제목 중복 검사
                title_key = "".join(news['title'].split())[:15]
                if not any("".join(n['title'].split())[:15] == title_key for n in final_news):
                    final_news.append(news)
                    publisher_counts[news['publisher']] = publisher_counts.get(news['publisher'], 0) + 1
                    pub_found_count += 1

    # 2-2. 8개가 안 채워졌으면 기타 언론사에서 채우기 (언론사당 2개 제한 유지)
    if len(final_news) < 8:
        for news in all_raw_news:
            if len(final_news) >= 8: break
            pub = news['publisher']
            if publisher_counts.get(pub, 0) < 2:
                title_key = "".join(news['title'].split())[:15]
                if not any("".join(n['title'].split())[:15] == title_key for n in final_news):
                    final_news.append(news)
                    publisher_counts[pub] = publisher_counts.get(pub, 0) + 1

    # 3. 메시지 전송 (성공했던 로직 그대로 사용)
    if final_news:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n<b>24시간 내 주요 뉴스</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        for i, news in enumerate(final_news[:8], 1):
            pub_info = news['parsed_date'].strftime('%m.%d %H:%M')
            message += f"{i}. <a href='{news['link']}'>{news['title']}</a> [{news['publisher']} / {pub_info}]\n\n"

        for chat_id in CHAT_ID_LIST:
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                             data={"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False}, 
                             timeout=15)
            except: pass

        # 아침 실행 시 기록 저장
        if time_tag == "아침":
            with open(HISTORY_FILE, "w") as f:
                for n in final_news[:8]:
                    f.write(n['link'] + "\n")

if __name__ == "__main__":
    main()
