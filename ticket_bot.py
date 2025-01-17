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
from datetime import datetime
from io import BytesIO

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

    async def sendCheck(self, index=0):
        isSuccess, response = await self.apiRequest('https://tixcraft.com/ticket/check', type="json", index=index)
        if isSuccess:
            if response.get('waiting') == True:
                print(f"等候{response.get('time')}秒")
                await asyncio.sleep(int(response.get('time')))
                return await self.sendCheck(index=index)
            else:
                if "您的選購條件已無足夠" in response.get('message'):
                    print("選購條件不足")
                    return False
                elif "已超過每筆訂單張數限制" in response.get('message'):
                    print("已超過每筆訂單張數限制")
                    return False
                else:
                    if "即將前往結帳，請勿進行任何操作" in response.get('message'):
                        return True
                    else:
                        return False
        else:
            return False

    async def sendTickets(self, post_data, url, index=0):
        isSuccess, response = await self.apiRequest(url=url, method="post", data=post_data, index=index)

        if isSuccess:
            soup = BeautifulSoup(response, "lxml")
            scripts = soup.find_all("script")
            if "您所輸入的驗證碼不正確，請重新輸入" in scripts[3].text:
                print("驗證碼錯誤")
                return await self.handleTicketPage(url=url, retry=True, index=index)
            elif "區域已售完" in scripts[3].text:
                print("區域已售完")
                return False
            else:
                print("成功送出")
                return await self.sendCheck(index=index)
        else:
            print(f"{url} 請求失敗")
            return False
    
    async def handleTicketPage(self, url, retry=False, index=0):
        try:
            isSuccess, response = await self.apiRequest(url=url, index=index)
            if isSuccess:
                print("進入選票頁面")
                soup = BeautifulSoup(response, "lxml")
                lineupSuccess, ticketPrice = await self.find_lineup_params(url=url, soup=soup, index=index)
                if not retry:
                    seat = soup.find(class_="select-area").text
                    start = seat.find("所選擇區域")  # 找到 "所選擇區域" 的位置
                    end = seat.find("最多可選 4 張")  # 找到 "最多可選 4 張" 的位置

                    if start != -1 and end != -1:
                        # 取出兩個固定字串之間的部分
                        selected_area = seat[start:end].strip()
                        cleaned_area = ' '.join(selected_area.split()).split(' ')[1]

                        if lineupSuccess:
                            print(f"{cleaned_area}已購買{ticketPrice}張")
                        else:
                            print(f"{cleaned_area}購買失敗")
                    else:
                        print("未找到指定的範圍")
                return lineupSuccess
            else:
                print(f"Failed to process {url}")
                return False
        except Exception as e:
            print(f"Error processing {url}: {e}")
            return False

    async def downloadImage(self, soup, index=0):
        captcha_img = soup.find(id="TicketForm_verifyCode-image").get('src')
        captcha_img_url = f"https://tixcraft.com{captcha_img}"
        isSuccess, image_data = await self.apiRequest(url=captcha_img_url, type="image", index=index)
        return BytesIO(image_data)

    async def find_lineup_params(self, url, soup, index=0):
        choose = soup.find(class_="form-select mobile-select")

        if choose:
            image_data = await self.downloadImage(soup=soup, index=index)
            print("下載圖片完成")

            csrf = soup.find(id='form-ticket-ticket').find(attrs={"name": "_csrf"}).get('value')
            ticketPrice = choose.find_all('option')[-1].get('value')
            if int(self.config['ticket_quantity']) < int(ticketPrice):
                ticketPrice = self.config['ticket_quantity']
            priceSize = 1
            agree = 1
            verifyCode = self.ocr.classification(image_data.getvalue())

            nums = choose.get('id').split("TicketForm_ticketPrice_")[1]
            post_data={
                '_csrf': csrf,
                f"TicketForm[ticketPrice][{nums}]": ticketPrice,
                f"TicketForm[priceSize][{nums}]": priceSize,
                f"TicketForm[verifyCode]": verifyCode,
                f"TicketForm[agree]": agree,
            }
            isSuccess = await self.sendTickets(post_data=post_data, url=url, index=index)
            # 等待結果並獲取回傳值
            return isSuccess, ticketPrice
        else:
            return False, None

    async def run(self):
        print("開始")
        selected_url = f"https://tixcraft.com/ticket/area/{self.concertName}/{self.date_keys[0]['value']}"
        isSuccess, response = await self.apiRequest(url=selected_url)

        if isSuccess:
            if self.config['No_selection']:
                seatsTasks = []
                for index, cookie in enumerate(self.config['cookie']):
                    # 從哪邊開始抓
                    lockedSeat = list(area_url_list.items())[cookie['selectedIndex']]
                    uid, url = lockedSeat
                    print(url)
                    task = asyncio.create_task(self.handleTicketPage(url=selected_url, index=index))
                    seatsTasks.append(task)
            else:
                soup = BeautifulSoup(response, "lxml")
                scripts = soup.find_all("script")
                if len(scripts) >= 20:
                    script_content = scripts[20].string
                    match = re.search(r'var areaUrlList\s*=\s*(\{.*?\});', script_content, re.DOTALL)

                    if match:
                        # 將找到的 JSON 字串轉換為字典
                        area_url_list_json = match.group(1)
                        area_url_list = json.loads(area_url_list_json)
                        
                        seatsTasks = []
                        for index, cookie in enumerate(self.config['cookie']):
                            # 從哪邊開始抓
                            lockedSeat = list(area_url_list.items())[cookie['selectedIndex']]
                            uid, url = lockedSeat
                            print(url)
                            task = asyncio.create_task(self.handleTicketPage(url=url, index=index))
                            seatsTasks.append(task)
                                                    
                        await asyncio.gather(*seatsTasks)

                    else:
                        print("未找到 areaUrlList。")
        else:
            print('請求失敗')

    async def apiRequest(self, url, type="text", method="get", data="", index=0):
        cookie = self.config['cookie'][index]
        token = f"SID={cookie['SID']}; _csrf={cookie['_csrf']}"

        if method == "post":
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://tixcraft.com",
                "Referer": url,
                "Cookie": token,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
            }
        else:
            headers = {
                "Cookie": token,
            }
        async with aiohttp.ClientSession() as session:
            request_kwargs = {"url": url, "headers": headers}
            if method == "post":
                request_kwargs["data"] = data

            async with getattr(session, method)(**request_kwargs) as response:
                if response.status == 200:
                    if type == "json":
                        return True, await response.json()
                    elif type == "image":
                        return True, await response.read()
                    else:
                        return True, await response.text()
                else:
                    print(f"{url} 請求失敗，狀態碼：{response.status}")
                    return False, response

    async def getAllDate(self):
        url = self.config["activity_url"]
        isSuccess, response = await asyncio.create_task(self.apiRequest(url=url))

        if isSuccess:
            soup = BeautifulSoup(response, "lxml")
            date_pattern = re.compile(r"\d{4}/\d{2}/\d{2}")
            date_keys = []
            find = False
            for tr in soup.select("tr.gridc.fcTxt"):
                data_key = tr.get("data-key")
                if data_key:
                    # 從第一個 `td` 取得日期資訊並提取日期部分
                    date_text = tr.select_one("td").get_text(strip=True)
                    date_match = date_pattern.search(date_text)
                    date = date_match.group(0) if date_match else ""
                    # 存入所需格式
                    if date == self.config['date']:
                        find = True
                        date_keys.append({"value": data_key, "tag": False, "date": date})
            if not find:
                print('找不到所選日期')
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
    #     if now.hour == 12 and now.minute >= 30 and now.second >= 1:
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