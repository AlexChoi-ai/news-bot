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

def get_news_robust(query_str, start_time, end_time, exclude_links, current_final_news, limit_count, hankyung_limit=None):
    """지정된 쿼리로 기사를 가져와서 리스트에 추가 (언론사별 제한 기능 포함)"""
    exclude_keywords = "-연예 -스포츠 -야구 -축구 -농구 -배구 -골프 -드라마 -아이돌 -연예인 -뮤직 -차트 -영화 -예능 -방송"
    full_query = f"{query_str} {exclude_keywords} when:1d"
    rss_url = f"https://news.google.com/rss/search?q={quote(full_query)}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    ban_list = ['연예', '스포츠', '축구', '야구', '골프', '드라마', '아이돌', '방송', '뮤직', '열애', '결혼', '출연']
    
    # 중복 체크를 위한 현재 링크 세트
    collected_links = {n['link'] for n in current_final_news}
    
    # 현재 한국경제 기사 수 카운트
    hankyung_count = sum(1 for n in current_final_news if "한국경제" in n['publisher'])

    for entry in feed.entries:
        if len(current_final_news) >= limit_count:
            break
            
        try:
            if entry.link in exclude_links or entry.link in collected_links:
                continue

            pub_date = parser.parse(entry.published).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
            
            if start_time <= pub_date <= end_time:
                full_title = entry.title.rsplit(' - ', 1)
                title = full_title[0].strip()
                publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
                
                # [수정] 한국경제 기사 수 제한 로직
                if "한국경제" in publisher:
                    if hankyung_limit is not None and hankyung_count >= hankyung_limit:
                        continue
                
                if any(word in title for word in ban_list):
                    continue
                    
                # 제목 중복 방지 (공백제외 15자)
                title_key = "".join(title.split())[:15]
                if any("".join(n['title'].split())[:15] == title_key for n in current_final_news):
                    continue

                current_final_news.append({
                    'title': title,
                    'link': entry.link,
                    'publisher': publisher,
                    'parsed_date': pub_date
                })
                collected_links.add(entry.link)
                if "한국경제" in publisher: hankyung_count += 1
        except:
            continue
    return current_final_news

def main():
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    date_str = now.strftime("%y년 %m월 %d일")
    hour = now.hour
    
    # 24시간 범위 설정
    end_time = now
    start_time = now - datetime.timedelta(days=1)

    morning_history = set()
    if 5 <= hour < 12: # 아침
        time_tag = "아침"
    else: # 오후
        time_tag = "오후"
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                morning_history = {line.strip() for line in f.readlines()}

    final_news = []
    
    # 1단계: 연합뉴스 우선 수집 (최대 4개)
    final_news = get_news_robust("source:연합뉴스", start_time, end_time, morning_history, final_news, 4)
    
    # 2단계: 한국경제 수집 (한국경제는 최종 2개까지만 허용)
    final_news = get_news_robust("source:한국경제", start_time, end_time, morning_history, final_news, 6, hankyung_limit=2)
            
    # 3단계: 8개가 채워질 때까지 전체 인기 뉴스로 보충 (한국경제는 여전히 2개 제한 유지)
    if len(final_news) < 8:
        final_news = get_news_robust("", start_time, end_time, morning_history, final_news, 8, hankyung_limit=2)

    # 4단계: 만약 아직도 8개가 안 된다면 (시간 범위를 약간 더 넓혀서라도 8개 강제 확보)
    if len(final_news) < 8:
        start_time_wide = start_time - datetime.timedelta(hours=12) # 범위를 12시간 더 확장
        final_news = get_news_robust("", start_time_wide, end_time, morning_history, final_news, 8, hankyung_limit=2)

    if final_news:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n<b>24시간 내 주요 뉴스</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        for i, news in enumerate(final_news[:8], 1):
            pub_time = news['parsed_date'].strftime('%H:%M')
            message += f"{i}. <a href='{news['link']}'>{news['title']}</a> [{news['publisher']} / {pub_time}]\n\n"

        for chat_id in CHAT_ID_LIST:
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                             data={"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False}, timeout=10)
            except: pass

        if 5 <= hour < 12:
            with open(HISTORY_FILE, "w") as f:
                for n in final_news[:8]:
                    f.write(n['link'] + "\n")

if __name__ == "__main__":
    main()
