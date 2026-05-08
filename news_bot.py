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

def collect_news(query_str, start_time, end_time, exclude_links, final_list, target_total, hankyung_max=2):
    """RSS 피드에서 기사를 수집하여 final_list를 채움"""
    exclude_keywords = "-연예 -스포츠 -야구 -축구 -농구 -배구 -골프 -드라마 -아이돌 -연예인 -뮤직 -차트 -영화 -예능 -방송"
    full_query = f"{query_str} {exclude_keywords} when:1d"
    rss_url = f"https://news.google.com/rss/search?q={quote(full_query)}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    ban_list = ['연예', '스포츠', '축구', '야구', '골프', '드라마', '아이돌', '방송', '뮤직', '열애', '결혼', '출연']
    
    for entry in feed.entries:
        if len(final_list) >= target_total:
            break
            
        try:
            # 중복 링크 체크
            if any(n['link'] == entry.link for n in final_list) or entry.link in exclude_links:
                continue

            # 발행 시간을 한국 시간(KST)으로 변환
            pub_date = parser.parse(entry.published).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
            
            # 시간 범위 체크
            if start_time <= pub_date <= end_time:
                full_title = entry.title.rsplit(' - ', 1)
                title = full_title[0].strip()
                publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
                
                # 한국경제 쿼터 체크 (최대 hankyung_max개까지)
                if "한국경제" in publisher:
                    hk_count = sum(1 for n in final_list if "한국경제" in n['publisher'])
                    if hk_count >= hankyung_max:
                        continue
                
                # 금지어 및 제목 중복 체크
                if any(word in title for word in ban_list):
                    continue
                
                title_key = "".join(title.split())[:15]
                if any("".join(n['title'].split())[:15] == title_key for n in final_list):
                    continue

                final_list.append({
                    'title': title,
                    'link': entry.link,
                    'publisher': publisher,
                    'parsed_date': pub_date
                })
        except:
            continue
    return final_list

def main():
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    date_str = now.strftime("%y년 %m월 %d일")
    hour = now.hour
    
    # 기본 24시간 범위 설정
    end_time = now
    start_time = now - datetime.timedelta(days=1)

    morning_history = set()
    if 5 <= hour < 12:
        time_tag = "아침"
    else:
        time_tag = "오후"
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                morning_history = {line.strip() for line in f.readlines()}

    final_news = []
    
    # Step 1: 연합뉴스 우선 수집 (최대 4개)
    final_news = collect_news("source:연합뉴스", start_time, end_time, morning_history, final_news, 4)
    
    # Step 2: 한국경제 수집 (최대 2개 제한 유지하며 6개까지 채우기 시도)
    final_news = collect_news("source:한국경제", start_time, end_time, morning_history, final_news, 6)
            
    # Step 3: 부족분 전체 뉴스사에서 보충 (8개 채우기)
    if len(final_news) < 8:
        final_news = collect_news("", start_time, end_time, morning_history, final_news, 8)

    # Step 4: 비상수단 - 여전히 8개가 안 되면 시간 범위를 48시간 전까지 확장하여 강제 수집
    if len(final_news) < 8:
        start_time_emergency = now - datetime.timedelta(days=2)
        final_news = collect_news("", start_time_emergency, end_time, morning_history, final_news, 8)

    # 메시지 생성 및 전송
    if final_news:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n<b>24시간 내 주요 뉴스</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        for i, news in enumerate(final_news[:8], 1):
            # [수정] 발행 시간 표시 형식 변경: 월.일 시:분
            pub_info = news['parsed_date'].strftime('%m.%d %H:%M')
            message += f"{i}. <a href='{news['link']}'>{news['title']}</a> [{news['publisher']} / {pub_info}]\n\n"

        for chat_id in CHAT_ID_LIST:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                    data={
                        "chat_id": chat_id, 
                        "text": message, 
                        "parse_mode": "HTML", 
                        "disable_web_page_preview": False
                    }, 
                    timeout=10
                )
            except:
                pass

        # 아침 실행 시 역사 기록 저장 (오후 중복 제거용)
        if 5 <= hour < 12:
            with open(HISTORY_FILE, "w") as f:
                for n in final_news[:8]:
                    f.write(n['link'] + "\n")

if __name__ == "__main__":
    main()
