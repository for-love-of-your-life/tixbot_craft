import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
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
            chrome_options = Options()
            chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.maximize_window()
            self.wait = WebDriverWait(self.driver, 10)
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

    def find_and_click_button(self, possible_selectors):
        """嘗試多個可能的選擇器來找到並點擊按鈕"""
        for selector_type, selector_value in possible_selectors:
            try:
                logger.info(f"嘗試找尋按鈕: {selector_value}")
                elements = self.wait.until(
                    EC.presence_of_all_elements_located((selector_type, selector_value))
                )
                for element in elements:
                    if element.is_displayed() and element.is_enabled():

                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                        time.sleep(0.5)  # 等待滾動完成

                        button_text = element.text
                        logger.info(f"找到按鈕: {button_text}")
                    
                        if "確認張數" in button_text:
                            logger.info("點擊確認張數按鈕")
                            element.click()
                            return True
            except Exception:
                continue
        return False

    def select_ticket_quantity(self):
        """選擇票數"""
        try:
            possible_selectors = [
                (By.XPATH, "//select[starts-with(@id, 'TicketForm_ticketPrice_')]"),
                (By.CSS_SELECTOR, "select[name^='TicketForm[ticketPrice]']"),
                (By.CLASS_NAME, "form-select")  # 根據類名選擇下拉框
            ]
            
            for selector_type, selector_value in possible_selectors:
                try:
                    # 等待下拉框可用
                    quantity_select = self.wait.until(
                        EC.presence_of_element_located((selector_type, selector_value))
                    )
                    highest_select = Select(quantity_select).options[-1].get_attribute("value")
                    highest_select = int(highest_select)
                    value = self.config['ticket_quantity']
                    if value >= highest_select:
                        value = highest_select

                    # 點擊下拉框以顯示選項
                    quantity_select.click()  
                    time.sleep(0.2)  # 等待下拉框展開
                    
                    # 選擇票數
                    quantity_option = self.driver.find_element(
                        By.XPATH, 
                        f"//option[@value='{value}']"
                    )
                    quantity_option.click()  # 點擊選擇的票數
                    logger.info(f"已選擇 {value} 張票")

                     # 等待 checkbox 元素加載
                    checkbox = self.wait.until(
                        EC.presence_of_element_located((By.ID, "TicketForm_agree"))
                    )

                    # 檢查 checkbox 是否已經被勾選
                    if not checkbox.is_selected():
                        # 若尚未勾選，點擊打勾
                        checkbox.click()
                        logger.info("已勾選會員服務條款")
                    else:
                        logger.info("會員服務條款已被勾選")

                    return True
                except NoSuchElementException:
                    logger.warning(f"未找到選擇器: {selector_value}")
                    continue
                except Exception as e:
                    logger.error(f"在選擇票數過程中出現錯誤: {str(e)}")
            
            logger.error("未找到票數選擇框")
            return False
            
        except Exception as e:
            logger.error(f"選擇票數失敗: {str(e)}")
            return False

    def handle_captcha(self):
        """处理验证码的获取和识别过程"""
        try:
            image = open("captcha_image.png", "rb").read()
            captcha_result = self.ocr.classification(image)
            
            if captcha_result:
                self.fill_in_captcha(captcha_result)  # 使用 self 调用方法
                possible_selectors = [
                    (By.CLASS_NAME, "btn-primary"),  # 根據 class 名稱
                    (By.XPATH, "//button[contains(text(), '確認張數')]")
                ]
                self.find_and_click_button(possible_selectors)
                return True
            else:
                logger.error("验证码识别失败，请重试")
                
        except Exception as e:
            logger.error(f"处理验证码时发生错误: {str(e)}")

    def fill_in_captcha(self, captcha_result):
        """填写验证码"""
        captcha_input = self.wait.until(
            EC.presence_of_element_located((By.ID, "TicketForm_verifyCode"))
        )
        captcha_input.clear()
        captcha_input.send_keys(captcha_result)
        logger.info("填写验证码成功")

    def get_captcha_image_path(self):
        """获取验证码图片的路径"""
        try:
            # 使用 ID 定位验证码图片元素
            captcha_image_element = self.wait.until(
                EC.presence_of_element_located((By.ID, "TicketForm_verifyCode-image"))  # 使用 ID
            )
            # 输出验证码元素的 HTML
            logger.info("获取验证码元素 HTML: %s", captcha_image_element.get_attribute('outerHTML'))

            # 截图并保存
            captcha_image_element.screenshot("captcha_image.png")
            logger.info("验证码图片已保存为 captcha_image.png")
            return "captcha_image.png"
            
        except Exception as e:
            logger.error(f"获取验证码图片时发生错误: {str(e)}")
            return None

    def ticket_page(self):
        retry_count = 0
        while True:
            retry_count += 1
            logger.info(f"第 {retry_count} 次尝试")
            if self.select_ticket_quantity():

                captcha_image_path = self.get_captcha_image_path()  # 替换为你的获取验证码图片的逻辑
                if captcha_image_path and self.handle_captcha():  # 传递验证码图片路径
                    try:
                        alert = None
                        alert = WebDriverWait(self.driver, 1).until(EC.alert_is_present())
                    except Exception as e:
                        print(e)

                    if alert:
                        logger.info(f"Alert found: {alert.text}")
                        if alert.text == '您所輸入的驗證碼不正確，請重新輸入':
                            alert.accept()     
    
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
                        
                        for key, url in maxSeatsHandle:
                            print(url)
                            self.driver.get(url)
                            self.ticket_page()

                    else:
                        print("未找到 areaUrlList。")
            else:
                print('請求失敗')

    async def apiRequest(self, url):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
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