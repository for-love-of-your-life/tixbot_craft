import sys
import time
import json
import logging
import ddddocr
import time
from bs4 import BeautifulSoup
import re
import aiohttp
import asyncio
from itertools import islice
import requests
import os

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ticket_bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class TixCraftBot:
    def __init__(self):
        try:
            self.config = self.load_config()
            # chrome_options = Options()
            # chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            # self.driver = webdriver.Chrome(options=chrome_options)
            # self.driver.maximize_window()
            # self.wait = WebDriverWait(self.driver, 10)
            self.ocr = ddddocr.DdddOcr(beta=True)
            self.date_keys = []
            self.concertName = re.search(r"(?<=game/)[^/]+", self.config["activity_url"]).group(0)
            logger.info("瀏覽器初始化成功")
            
        except Exception as e:
            logger.error(f"初始化失敗: {str(e)}")
            raise

    def load_config(self):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info("成功載入配置文件")
                return config
        except FileNotFoundError:
            logger.warning("找不到配置文件，創建默認配置")
            print("請先設定 config.json 中的配置信息")
            input("按 Enter 鍵結束程式...")
            sys.exit(1)

    def clear_image_folder(self):
        folder = "image"
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)  # 刪除檔案或連結
                    elif os.path.isdir(file_path):
                        os.rmdir(file_path)  # 刪除空的子資料夾    
                except Exception as e:
                    print(f"刪除 {file_path} 時發生錯誤: {e}")

    async def sendTickets(self, post_data, url):
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://tixcraft.com",
            "Referer": url,
            "Cookie": self.config['cookie'],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=post_data) as response:
                if response.status == 200:
                    response_text = await response.text()
                    soup = BeautifulSoup(response_text, "html.parser")
                    scripts = soup.find_all("script")
                    if "您所輸入的驗證碼不正確，請重新輸入" in scripts[3].text:
                        print("您所輸入的驗證碼不正確，請重新輸入")
                        return await self.handleTicketPage(url=url)
                    elif "區域已售完" in scripts[3].text:
                        print("區域已售完")
                        return False
                    else:
                        print("成功")
                        isSuccess, response2 = await self.apiRequest('https://tixcraft.com/ticket/check')
                        print(response2)

                        # with open("response_data.txt", "w", encoding="utf-8") as file:
                        #     file.write(response_text)
                        return True
                else:
                    print(f"{url} 請求失敗")
                    return False
    
    async def handleTicketPage(self, url):
        try:
            isSuccess, response = await self.apiRequest(url=url)
            with open("response_data.txt", "w", encoding="utf-8") as file:
                file.write(response)
            if isSuccess:
                isBuySuccess = await self.find_lineup_params(response=response, url=url)
                if isBuySuccess:
                    return True
                else:
                    return False
            else:
                print(f"Failed to process {url}")
                return False
        except Exception as e:
            print(f"Error processing {url}: {e}")
            return False

    async def downloadImage(self, soup):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Cookie": self.config['cookie'],
        }
        if not os.path.exists("image"):
            os.makedirs("image")

        captcha_img = soup.find(id="TicketForm_verifyCode-image").get('src')
        captcha_img_url = f"https://tixcraft.com{captcha_img}"
        print('before', captcha_img_url)
        v_value = captcha_img.split("v=")[-1].split(".")[0]
        filename = os.path.join("image", f"{v_value}.png")

        async with aiohttp.ClientSession() as session:
            async with session.get(captcha_img_url, headers=headers) as response:
                response.raise_for_status()  # 確保圖片成功下載
                # 儲存圖片
                with open(filename, 'wb') as f:
                    f.write(await response.read())
        
        return filename

    async def find_lineup_params(self, response, url):
        soup = BeautifulSoup(response, "html.parser")
        choose = soup.find(class_="form-select mobile-select")

        if choose:
            image_filename = await self.downloadImage(soup=soup)
            
            with open(image_filename, "rb") as image_file:
                image = image_file.read()

            csrf = soup.find(id='form-ticket-ticket').find(attrs={"name": "_csrf"}).get('value')
            ticketPrice = choose.find_all('option')[-1].get('value')
            priceSize = 1
            agree = 1
            verifyCode = self.ocr.classification(image)

            nums = choose.get('id').split("TicketForm_ticketPrice_")[1]
            post_data={
                '_csrf': csrf,
                f"TicketForm[ticketPrice][{nums}]": ticketPrice,
                f"TicketForm[priceSize][{nums}]": priceSize,
                f"TicketForm[verifyCode]": verifyCode,
                f"TicketForm[agree]": agree,
            }
            print(post_data)
            # isSuccess = await self.sendTickets(post_data=post_data, url=url)
            # return isSuccess
        else:
            return False

    async def run(self):
        tasks = []
        for item in self.date_keys:
            value = item['value']
            selected_url = f"https://tixcraft.com/ticket/area/{self.concertName}/{value}"
            task = asyncio.create_task(self.apiRequest(url=selected_url))
            tasks.append(task)

        responses = await asyncio.gather(*tasks)
        for isSuccess, response in responses:
            if isSuccess:
                soup = BeautifulSoup(response, "html.parser")
                scripts = soup.find_all("script")
                if len(scripts) >= 20:
                    script_content = scripts[20].string
                    match = re.search(r'var areaUrlList\s*=\s*(\{.*?\});', script_content, re.DOTALL)

                    if match:
                        # 將找到的 JSON 字串轉換為字典
                        area_url_list_json = match.group(1)
                        area_url_list = json.loads(area_url_list_json)

                        # 從哪邊開始抓
                        maxSeatsHandle = list(islice(area_url_list.items(), 1))
                        
                        seatsTasks = []
                        for key, url in maxSeatsHandle:
                            print(url)
                            task = asyncio.create_task(self.handleTicketPage(url=url))
                            seatsTasks.append(task)
                                                    
                        seatsResponses = await asyncio.gather(*seatsTasks)
                        # self.clear_image_folder()

                    else:
                        print("未找到 areaUrlList。")
            else:
                print('請求失敗')

    async def apiRequest(self, url):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Cookie": self.config['cookie'],
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    # print(f"{url}請求成功")
                    return True, await response.text()  # 取得響應內容
                else:
                    print(f"{url}請求失敗")
                    return False, response
            
    async def getAllDate(self):
        url = self.config["activity_url"]
        isSuccess, response = await asyncio.create_task(self.apiRequest(url=url))

        if isSuccess:
            soup = BeautifulSoup(response, "html.parser")
            date_pattern = re.compile(r"\d{4}/\d{2}/\d{2}")
            date_keys = []
            for tr in soup.select("tr.gridc.fcTxt"):
                data_key = tr.get("data-key")
                if data_key:
                    # 從第一個 `td` 取得日期資訊並提取日期部分
                    date_text = tr.select_one("td").get_text(strip=True)
                    date_match = date_pattern.search(date_text)
                    date = date_match.group(0) if date_match else ""
                    # 存入所需格式
                    date_keys.append({"value": data_key, "tag": False, "date": date})
            # 取得所有天數
            self.date_keys = date_keys
            print(f"取得天數成功: {date_keys}")
        else:
            print(f"無法訪問頁面，狀態碼: {response.status}")

if __name__ == "__main__":
    bot = TixCraftBot()
    asyncio.run(bot.getAllDate())
    asyncio.run(bot.run())

    # while True:
    #     now = datetime.now()
    #     # 檢查時間是否達到 3 點 0 分 1 秒
    #     if now.hour == 12 and now.minute >= 00 and now.second >= 1:
    #         try:
    #             asyncio.run(bot.run())
    #             break
    #         except Exception as e:
    #             logger.error(f"程式執行失敗: {str(e)}")
    #             input("\n按 Enter 鍵結束程式...")
    #         # 等待一天後再檢查，以免在當天重複執行
    #         time.sleep(86400)  # 86400 秒 = 24 小時
    #     else:
    #         # 確保每秒檢查一次，避免錯過目標時間
    #         time.sleep(0.2)