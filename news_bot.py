import feedparser
import requests
import datetime
import os
from dateutil import parser
from urllib.parse import quote

# 환경 변수 로드
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID_RAW = os.environ.get("CHAT_ID_LIST")
CHAT_ID_LIST = [chat_id.strip() for chat_id in CHAT_ID_RAW.split(",")] if CHAT_ID_RAW else []

def main():
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(kst)
    
    print(f"--- 실행 시작: {now} ---")

    # 1. 뉴스 수집 (가장 안정적인 기본 검색어로 테스트)
    # 검색어가 너무 복잡하면 구글이 차단할 수 있어 단순화했습니다.
    query = "주요뉴스" 
    rss_url = f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
    
    print(f"RSS 요청 주소: {rss_url}")
    
    # 2. Feedparser로 데이터 가져오기
    try:
        feed = feedparser.parse(rss_url)
        print(f"RSS 응답 상태: {getattr(feed, 'status', 'N/A')}")
        print(f"가져온 기사 수: {len(feed.entries)}")
    except Exception as e:
        print(f"RSS 파싱 중 에러 발생: {e}")
        return

    final_news = []
    for entry in feed.entries[:8]: # 상위 8개만 테스트
        final_news.append({'title': entry.title, 'link': entry.link})

    # 3. 텔레그램 전송 (메시지 내용을 최소화해서 테스트)
    if not final_news:
        print("전송할 뉴스가 없습니다.")
        return

    print("텔레그램 전송 시도 중...")
    test_message = f"<b>[테스트]</b> 뉴스를 성공적으로 가져왔습니다.\n총 {len(final_news)}건"
    
    for chat_id in CHAT_ID_LIST:
        send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        try:
            res = requests.post(send_url, data={
                "chat_id": chat_id,
                "text": test_message,
                "parse_mode": "HTML"
            }, timeout=10)
            print(f"전송 결과 (ID: {chat_id}): {res.status_code}")
            if res.status_code != 200:
                print(f"상세 에러: {res.text}")
        except Exception as e:
            print(f"전송 중 예외 발생: {e}")

if __name__ == "__main__":
    main()
