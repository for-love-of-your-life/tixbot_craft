1. 下載https://googlechromelabs.github.io/chrome-for-testing/ (chrome 自己更新到最新)

2. 建立資料夾將下載的 chromedriver 放入到這邊跟此檔案同一層

3. cmd 輸入(利用此command 打開瀏覽器，並且先做售票系統的登入)
    - **mac**：/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debugRE
    - **window**："C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug"
4. pip install -r requirements.txt (安裝此檔案的所有路徑)

5. 自行新增config.json 檔案
```json
    {
        "activity_url": "https://tixcraft.com/activity/game/24_p12tpdome",
        "ticket_quantity": 2,
        "target_price": "3800",
        "date": "2024/11/14",
        "cookie": [
            {
                "SID": "tg3dfq2qo8a5gaoh0jhm1fiu52", 
                "_csrf":"a611ef3c277a2422a17cffd2e54bca349a0954c5a756802d3c2620969fc93263a%3A2%3A%7Bi%3A0%3Bs%3A5%3A%22_csrf%22%3Bi%3A1%3Bs%3A32%3A%220FKgO3naQUXm7Ai9C8Fwg8CvjY--ieeW%22%3B%7D",
                "selectedIndex": 0
            }
        ]
    }
```

**其他**
    - 日期只能選擇一天
    - 進入到拓元網站後登入會員，複製登入會員後的cookie sid及_csrf token 到config.json。
    - selectedIndex為當前的可選座位的從上到下的第幾個index