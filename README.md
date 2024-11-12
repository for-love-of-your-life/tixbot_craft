1. 下載https://googlechromelabs.github.io/chrome-for-testing/ (chrome 自己更新到最新)

2. 建立資料夾將下載的 chromedriver 放入到這邊跟此檔案同一層

3. cmd 輸入(利用此command 打開瀏覽器，並且先做售票系統的登入)
    - **mac**：/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debugRE
    - **window**："C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug"
4. pip install -r requirements.txt (安裝此檔案的所有路徑)

5. 自行新增config.json 格式

**其他**
    - 日期只能選擇一天
    - 進入到拓元網站後登入會員，複製登入會員後的sid及_csrf token 到config.json。