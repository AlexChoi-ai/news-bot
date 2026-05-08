import feedparser
import requests
import datetime
import os
from dateutil import parser
from urllib.parse import quote

# 환경 변수 로드 확인
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID_LIST")
CHAT_ID_LIST = [chat_id.strip() for chat_id in CHAT_ID_RAW.split(",")] if CHAT_ID_RAW else []

print(f"--- 환경 설정 확인 ---")
print(f"BOT_TOKEN 존재 여부: {bool(BOT_TOKEN)}")
print(f"CHAT_ID_LIST 개수: {len(CHAT_ID_LIST)}")

def main():
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    
    # 디버깅을 위해 시간 범위를 아주 넓게 잡음 (직전 48시간)
    start_time = now - datetime.timedelta(hours=48)
    end_time = now
    
    print(f"\n--- 시간 설정 ---")
    print(f"현재 시간 (KST): {now}")
    print(f"검색 범위: {start_time} ~ {end_time}")

    # 1. 뉴스 수집
    # 검색어에서 'when:1d'를 제거하여 구글의 필터링을 최소화함
    exclude_keywords = "-연예 -스포츠 -야구 -축구 -농구 -배구 -골프 -드라마 -아이돌 -연예인 -뮤직 -차트 -영화 -예능 -방송"
    rss_url = f"https://news.google.com/rss/search?q={quote(exclude_keywords)}&hl=ko&gl=KR&ceid=KR:ko"
    
    print(f"\n--- 뉴스 수집 시작 ---")
    feed = feedparser.parse(rss_url)
    print(f"RSS에서 가져온 원본 기사 수: {len(feed.entries)}")

    if len(feed.entries) == 0:
        print("!! 경고: RSS 피드로부터 가져온 기사가 0개입니다. URL을 확인하세요.")
        return

    raw_list = []
    priority_map = {"연합뉴스": 1, "YTN": 2, "한국경제": 3, "매일경제": 4}

    for entry in feed.entries:
        try:
            pub_date = parser.parse(entry.published).astimezone(kst)
            
            # 시간 범위 체크 (필터링 로그 출력)
            if start_time <= pub_date <= end_time:
                full_title = entry.title.rsplit(' - ', 1)
                title = full_title[0].strip()
                publisher = full_title[1].strip() if len(full_title) > 1 else "뉴스"
                
                score = priority_map.get(publisher, 5)
                raw_list.append({
                    'title': title, 'link': entry.link, 'publisher': publisher,
                    'parsed_date': pub_date, 'score': score
                })
        except Exception as e:
            continue

    print(f"시간/조건 필터링 후 남은 기사 수: {len(raw_list)}")

    # 2. 선별 (상위 8개)
    raw_list.sort(key=lambda x: (x['score'], -x['parsed_date'].timestamp()))
    final_news = raw_list[:8]

    # 3. 전송 및 결과 출력
    if not final_news:
        print("!! 최종 전송할 기사가 없습니다. 루프를 종료합니다.")
        return

    print(f"\n--- 텔레그램 전송 시도 ---")
    message = f"<b>[디버그 모드] {now.strftime('%H:%M')} 뉴스</b>\n\n"
    for i, n in enumerate(final_news, 1):
        message += f"{i}. {n['title']} [{n['publisher']}]\n"

    for chat_id in CHAT_ID_LIST:
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
                timeout=15
            )
            print(f"ID {chat_id} 전송 결과: {response.status_code}")
            if response.status_code != 200:
                print(f"에러 내용: {response.text}")
        except Exception as e:
            print(f"전송 중 예외 발생: {e}")

if __name__ == "__main__":
    main()
