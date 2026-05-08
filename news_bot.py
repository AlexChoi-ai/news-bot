import feedparser
import requests
import datetime
import os
from dateutil import parser
from urllib.parse import quote

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID_LIST")
CHAT_ID_LIST = [chat_id.strip() for chat_id in CHAT_ID_RAW.split(",")] if CHAT_ID_RAW else []

def get_google_news(publisher, target_count):
    exclude_query = "-연예 -스포츠 -야구 -축구 -골프 -드라마 -아이돌"
    query = quote(f"source:{publisher} when:1d {exclude_query}")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    news_list = []
    seen_titles = set()
    
    for entry in feed.entries:
        title = entry.title.split(' - ')[0].strip()
        title_key = "".join(title.split())[:15]
        if title_key not in seen_titles:
            news_list.append({
                'title': title,
                'link': entry.link,
                'publisher': publisher,
                'parsed_date': parser.parse(entry.published).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
            })
            seen_titles.add(title_key)
        if len(news_list) >= target_count * 3:
            break
    return news_list

def main():
    # 한국 시간 기준 설정
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    date_str = now.strftime("%y년 %m월 %d일")
    hour = now.hour
    
    # [수정] 사용자 요청에 따른 수동 실행 검증 구간 설정
    if 7 <= hour < 18:
        # 07:00 ~ 17:59 사이 실행 시
        time_tag = "07시"
        sub_header = "어제 저녁부터 오늘 아침까지의 주요 뉴스"
    else:
        # 18:00 ~ 익일 06:59 사이 실행 시
        time_tag = "18시"
        sub_header = "오늘 하루의 주요 뉴스 8개"

    # 1. 언론사별 수집
    raw_yeonhap = get_google_news("연합뉴스", 4)
    raw_hankyung = get_google_news("한국경제", 2)
    raw_ytn = get_google_news("YTN", 2)
    
    # 2. 비중대로 우선 수집
    final_news = []
    final_news.extend(raw_yeonhap[:4])
    final_news.extend(raw_hankyung[:2])
    final_news.extend(raw_ytn[:2])
    
    # 3. 8개가 부족할 시 보충 로직
    if len(final_news) < 8:
        current_links = {n['link'] for n in final_news}
        pool = raw_yeonhap[4:] + raw_hankyung[2:] + raw_ytn[2:]
        pool.sort(key=lambda x: x['parsed_date'], reverse=True)
        for extra in pool:
            if len(final_news) >= 8: break
            if extra['link'] not in current_links:
                final_news.append(extra)
                current_links.add(extra['link'])

    # 4. [보완] 최종 뉴스 8개를 다시 한번 최신순으로 정렬 (사용자 가독성)
    final_news.sort(key=lambda x: x['parsed_date'], reverse=True)

    # 메시지 생성
    if not final_news:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n<b>{sub_header}</b>\n\n새로운 소식이 없습니다."
    else:
        message = f"<b>📢 [{date_str} {time_tag} 뉴스요약]</b>\n"
        message += f"<b>{sub_header}</b>\n"
        message += "━━━━━━━━━━━━━━━━━━\n\n"
        for i, news in enumerate(final_news, 1):
            pub_time = news['parsed_date'].strftime('%H:%M')
            message += f"{i}. <a href='{news['link']}'>{news['title']}</a> [{pub_time}]\n\n"

    # 전송
    send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for chat_id in CHAT_ID_LIST:
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False}
        requests.post(send_url, data=payload)

if __name__ == "__main__":
    main()
