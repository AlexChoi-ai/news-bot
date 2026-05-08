import feedparser
import requests
import datetime
import os
from dateutil import parser
from urllib.parse import quote

# [기존 유지] 환경 변수 및 설정
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID_LIST")
CHAT_ID_LIST = [chat_id.strip() for chat_id in CHAT_ID_RAW.split(",")] if CHAT_ID_RAW else []

def get_news_by_time(query_str, target_count, start_time, end_time):
    """구글 뉴스에서 인기순으로 가져오되, 연예/스포츠를 배제하고 시간 구간 필터링"""
    
    exclude_keywords = "-연예 -스포츠 -야구 -축구 -농구 -배구 -골프 -드라마 -아이돌 -연예인 -뮤직 -차트 -영화 -예능 -방송"
    full_query = f"{query_str} {exclude_keywords} when:1d"
    rss_url = f"https://news.google.com/rss/search?q={quote(full_query)}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    results = []
    seen_titles = set()
    
    # [개선] 금지어 목록 확장 (안정성 강화)
    ban_list = ['연예', '스포츠', '축구', '야구', '골프', '드라마', '아이돌', '방송', '뮤직', '열애', '결혼', '출연']
    
    for entry in feed.entries:
        if len(results) >= target_count:
            break
            
        try:
            # 발행 시간을 한국 시간(KST)으로 변환
            pub_date = parser.parse(entry.published).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
            
            # [기존 유지] 지정된 시간 구간 내의 기사인지 확인
            if start_time <= pub_date <= end_time:
                full_title = entry.title.rsplit(' - ', 1)
                title = full_title[0].strip()
                publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
                
                # [기존 유지] 제목 금지어 필터링
                if any(word in title for word in ban_list):
                    continue
                    
                # [기존 유지] 제목 유사도 기반 중복 방지
                title_key = "".join(title.split())[:15]
                if title_key not in seen_titles:
                    results.append({
                        'title': title,
                        'link': entry.link,
                        'publisher': publisher,
                        'parsed_date': pub_date
                    })
                    seen_titles.add(title_key)
        except Exception as e:
            print(f"기사 파싱 중 오류 발생: {e}")
            continue
            
    return results

def main():
    # [개선] GitHub Actions 서버 시간(UTC)에 관계없이 한국 시간 강제 지정
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    date_str = now.strftime("%y년 %m월 %d일")
    hour = now.hour
    
    # [기존 유지] 시간 구간 설정 로직
    if 7 <= hour < 18:
        time_tag = "07시"
        sub_header = "어제 저녁부터 오늘 아침까지의 주요 뉴스"
        end_time = now.replace(hour=6, minute=59, second=59, microsecond=0)
        start_time = (end_time - datetime.timedelta(days=1)).replace(hour=18, minute=1, second=0, microsecond=0)
    else:
        time_tag = "18시"
        sub_header = "오늘 하루의 주요 뉴스 8개"
        start_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
        end_time = now.replace(hour=17, minute=59, second=59, microsecond=0)

    final_news = []
    
    # 1. 연합뉴스 (최대 4개)
    final_news.extend(get_news_by_time("source:연합뉴스", 4, start_time, end_time))
    
    # 2. 한국경제 (최대 2개, 중복 제외)
    collected_links = {n['link'] for n in final_news}
    hankyung_candidates = get_news_by_time("source:한국경제", 2, start_time, end_time)
    for n in hankyung_candidates:
        if n['link'] not in collected_links:
            final_news.append(n)
            collected_links.add(n['link'])
            
    # 3. 전체 인기 뉴스로 8개 채우기
    if len(final_news) < 8:
        general_candidates = get_news_by_time("", 10, start_time, end_time)
        for n in general_candidates:
            if len(final_news) >= 8: break
            if n['link'] not in collected_links:
                final_news.append(n)
                collected_links.add(n['link'])

    # [개선] 메시지 생성 및 전송 (에러 처리 및 가독성 강화)
    if final_news:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n<b>{sub_header}</b>\n━━━━━━━━━━━━━━━━━━\n\n"
        for i, news in enumerate(final_news[:8], 1):
            pub_time = news['parsed_date'].strftime('%H:%M')
            # HTML 특수문자 탈출 처리는 하지 않으나, 링크 안정성을 위해 f-string 사용
            message += f"{i}. <a href='{news['link']}'>{news['title']}</a> [{news['publisher']} / {pub_time}]\n\n"

        send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        for chat_id in CHAT_ID_LIST:
            try:
                response = requests.post(
                    send_url, 
                    data={
                        "chat_id": chat_id, 
                        "text": message, 
                        "parse_mode": "HTML", 
                        "disable_web_page_preview": False
                    },
                    timeout=10 # [개선] 타임아웃 설정으로 무한 대기 방지
                )
                response.raise_for_status() # 4xx, 5xx 에러 시 예외 발생
            except Exception as e:
                print(f"텔레그램 전송 중 오류 발생 (Chat ID: {chat_id}): {e}")

if __name__ == "__main__":
    main()
