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

def get_news_by_time(query_str, target_count, start_time, end_time, exclude_links):
    """지정된 시간 내 인기 뉴스를 가져오되, exclude_links에 포함된 것은 제외"""
    exclude_keywords = "-연예 -스포츠 -야구 -축구 -농구 -배구 -골프 -드라마 -아이돌 -연예인 -뮤직 -차트 -영화 -예능 -방송"
    full_query = f"{query_str} {exclude_keywords} when:1d"
    rss_url = f"https://news.google.com/rss/search?q={quote(full_query)}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    results = []
    seen_titles = set()
    ban_list = ['연예', '스포츠', '축구', '야구', '골프', '드라마', '아이돌', '방송', '뮤직', '열애', '결혼', '출연']
    
    for entry in feed.entries:
        if len(results) >= target_count:
            break
            
        try:
            # 아침에 보낸 기사 링크와 완전히 동일하면 제외
            if entry.link in exclude_links:
                continue

            pub_date = parser.parse(entry.published).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
            
            if start_time <= pub_date <= end_time:
                full_title = entry.title.rsplit(' - ', 1)
                title = full_title[0].strip()
                publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
                
                if any(word in title for word in ban_list):
                    continue
                    
                title_key = "".join(title.split())[:15]
                if title_key not in seen_titles:
                    results.append({
                        'title': title,
                        'link': entry.link,
                        'publisher': publisher,
                        'parsed_date': pub_date
                    })
                    seen_titles.add(title_key)
        except:
            continue
    return results

def main():
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    date_str = now.strftime("%y년 %m월 %d일")
    hour = now.hour
    
    # 24시간 범위 설정
    end_time = now
    start_time = now - datetime.timedelta(days=1)

    # 오전/오후 문구 및 상태값 설정
    morning_history = set()
    if 5 <= hour < 12: # 아침 실행 (7시 전후)
        time_tag = "아침"
        # 아침에는 이전 기록을 무시 (새로운 하루 시작)
    else: # 오후 실행 (18시 전후)
        time_tag = "오후"
        # 아침에 보낸 기록 읽기
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                morning_history = {line.strip() for line in f.readlines()}

    final_news = []
    collected_links = set()
    
    # 1. 연합뉴스 우선 수집
    yonhap = get_news_by_time("source:연합뉴스", 4, start_time, end_time, morning_history)
    final_news.extend(yonhap)
    for n in yonhap: collected_links.add(n['link'])
    
    # 2. 한국경제 수집
    hankyung = get_news_by_time("source:한국경제", 2, start_time, end_time, morning_history | collected_links)
    for n in hankyung:
        final_news.append(n)
        collected_links.add(n['link'])
            
    # 3. 8개 채우기
    if len(final_news) < 8:
        general = get_news_by_time("", 50, start_time, end_time, morning_history | collected_links)
        for n in general:
            if len(final_news) >= 8: break
            final_news.append(n)
            collected_links.add(n['link'])

    if final_news:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n<b>24시간 내 주요 뉴스</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        for i, news in enumerate(final_news[:8], 1):
            pub_time = news['parsed_date'].strftime('%H:%M')
            message += f"{i}. <a href='{news['link']}'>{news['title']}</a> [{news['publisher']} / {pub_time}]\n\n"

        # 전송
        for chat_id in CHAT_ID_LIST:
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                             data={"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False})
            except: pass

        # [중요] 아침에 실행된 경우라면 현재 보낸 링크들을 파일에 기록
        if 5 <= hour < 12:
            with open(HISTORY_FILE, "w") as f:
                for n in final_news[:8]:
                    f.write(n['link'] + "\n")

if __name__ == "__main__":
    main()
