import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import json
import logging
from PIL import Image  # 确保你已经导入了 PIL 库
import numpy as np
import ddddocr
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import re


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
            self.select_url = ''
            self.date_keys = []
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

    def find_and_click_button(self, possible_selectors, notToggle):
        """嘗試多個可能的選擇器來找到並點擊按鈕"""
        for selector_type, selector_value in possible_selectors:
            try:
                logger.info(f"嘗試找尋按鈕: {selector_value}")
                elements = self.wait.until(
                    EC.presence_of_all_elements_located((selector_type, selector_value))
                )
                for element in elements:
                    if element.is_displayed() and element.is_enabled():

                        if not notToggle:
                            # 滾動到元素
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                            time.sleep(0.5)  # 等待滾動完成

                        button_text = element.text
                        logger.info(f"找到按鈕: {button_text}")
                    
                        # 只點擊包含「立即購票」或「購票」的按鈕
                        if "立即訂購" in button_text:
                            logger.info("點擊購票按鈕")
                            element.click()
                            return True
                        # 點擊「確認張數」按鈕
                        elif "確認張數" in button_text:
                            logger.info("點擊確認張數按鈕")
                            element.click()
                            return True
            except Exception:
                continue
        return False
        
    def go_to_area_selection(self):
        """前往區域選擇頁面"""
        concertName = re.search(r"(?<=game/)[^/]+", self.config["activity_url"]).group(0)

        # 先找是否有符合的date
        matched = False
        matched_value = None
        for item in self.date_keys:
            if item["date"] == self.config["date"] and not item["tag"]:
                item["tag"] = True  # 找到符合條件的項目後設定 tag 為 True
                matched = True
                matched_value = item["value"]
                break
    
        # 若找不到符合日期的項目，再從第一個未標記的項目開始找
        if not matched:
            for item in self.date_keys:
                if not item["tag"]:
                    item["tag"] = True
                    matched_value = item["value"]
                    matched = True
                    break
        
        if matched:
            # 符合則前往頁面
            selected_url = f"https://tixcraft.com/ticket/area/{concertName}/{matched_value}"
            self.driver.get(f"https://tixcraft.com/ticket/area/{concertName}/{matched_value}")
            time.sleep(.2)

            if self.driver.current_url != selected_url:
                # 若被轉址則重跑
                self.go_to_area_selection()
        else:
            for item in self.date_keys:
                if item["tag"]:
                    item["tag"] = False
            self.go_to_area_selection()
        
    def check_page_transition(self):
        """檢查頁面是否跳轉"""
        try:
            # 等待下一頁的某個關鍵元素（例如票價區域列表）加載完成
            self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "area-list")))
            return True  # 頁面跳轉成功
        except Exception:
            self.run()
            return False # 頁面跳轉失敗

    def select_area(self):
        """選擇區域"""
        try:
            logger.info("正在尋找票價區域...")
            target_price = self.config.get("target_price", "4800")
            self.select_url = self.driver.current_url
            time.sleep(0.2)  # 等待頁面完全載入
            
             # 等待区域列表载入，使用更短的超时时间
            WebDriverWait(self.driver, 60).until(
                EC.visibility_of_element_located((By.CLASS_NAME, "area-list"))
            )

            # 獲取頁面初始高度
            total_height = self.driver.execute_script("return document.documentElement.scrollHeight")
            current_scroll = 0
            scroll_step = 600  # 每次滾動的像素

            # 確保滾動之前頁面已經載入
            logger.info("開始滾動查找票價區域...")
            
            found_available_area = False  # 用于跟踪是否找到可用区域
            while current_scroll <= total_height:
                area_lists = self.driver.find_elements(By.CLASS_NAME, "area-list")

                for area_list in area_lists:
                    area_items = area_list.find_elements(By.TAG_NAME, "li")

                    for item in area_items:
                        if not self.is_element_in_viewport(item):
                            continue

                        price_text = item.text
                        logger.info(f"檢查票價區域: {price_text}")

                        # 檢查是否有可用座位
                        if "剩餘" in price_text or "熱賣中" in price_text:
                            logger.info(f"找到可用票價區域: {price_text}")
                            found_available_area = True  # 找到了可用区域

                            try:
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", item)

                                # 等待按鈕變為可點擊
                                WebDriverWait(self.driver, 5).until(
                                    EC.element_to_be_clickable(item)
                                )

                                item.click()  # 點擊可用的區域
                                logger.info(f"已選擇座位: {price_text}")
                                return True

                            except Exception as e:
                                logger.warning(f"點擊元素時發生錯誤: {str(e)}")
                                try:
                                    self.driver.execute_script("arguments[0].click();", item)
                                    logger.info(f"使用JavaScript選擇座位: {price_text}")
                                    return True
                                except Exception as js_e:
                                    logger.warning(f"使用JavaScript點擊元素時發生錯誤: {str(js_e)}")

                current_scroll += scroll_step
                self.driver.execute_script(f"window.scrollTo(0, {current_scroll});")
                time.sleep(0.5)  # 增加等待時間

                # 更新頁面高度
                total_height = self.driver.execute_script("return document.documentElement.scrollHeight")

            if not found_available_area:
                logger.warning("完整搜索後未找到可選的區域")
                self.select_area()  # 如果未找到可用区域，重新选择
                return False  # 返回 False

        except Exception as e:
            logger.error(f"選擇區域失敗: {str(e)}")
            self.run()
            return False

    def is_element_in_viewport(self, element):
        """檢查元素是否在可視區域內"""
        return self.driver.execute_script("""
            var rect = arguments[0].getBoundingClientRect();
            return (
                rect.top >= 0 &&
                rect.left >= 0 &&
                rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
                rect.right <= (window.innerWidth || document.documentElement.clientWidth)
            );
        """, element)
        
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
                self.find_and_click_button(possible_selectors, notToggle=True)
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

    def run(self, reRun):
        if not reRun:
            self.go_to_area_selection() # 進入到選位頁面

        try:
            retry_count = 0
            if self.select_area():
                try:
                    alert = None
                    alert = WebDriverWait(self.driver, 1).until(EC.alert_is_present())
                except Exception as e:
                    print(e)

                if alert:
                    self.reload(alert=alert)
                else:
                    while True:
                        retry_count += 1
                        logger.info(f"第 {retry_count} 次尝试")
                        if self.select_ticket_quantity():
                            # 在这里获取验证码图片的路径，假设你已经有一个方法获取验证码图片
                            captcha_image_path = self.get_captcha_image_path()  # 替换为你的获取验证码图片的逻辑
                            if captcha_image_path and self.handle_captcha():  # 传递验证码图片路径
                                try:
                                    alert = None
                                    alert = WebDriverWait(self.driver, 10).until(EC.alert_is_present())
                                except Exception as e:
                                    print(e)

                                if alert:
                                    logger.info(f"Alert found: {alert.text}")
                                    if alert.text == "此場次/區域已售完":
                                        # 重跑
                                        self.reload(alert=alert)
                                    elif alert.text == '您所輸入的驗證碼不正確，請重新輸入':
                                        alert.accept()
                                    else:
                                        self.reload(alert=alert)
                                else:
                                    # 成功
                                    break
        except KeyboardInterrupt:
            logger.info("程序已被用户中断")
        except Exception as e:
            print(e)
            logger.error(f"抢票过程中发生错误: {str(e)}")
        finally:
            print("\n按 Enter 键结束程序...")
            input()
            self.driver.quit()
            
    def getAllDate(self):
        url = self.config["activity_url"]
        # 設定user agent
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
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
                    date_keys.append({"value": data_key, "tag": True, "date": date})
            # 取得所有天數
            self.date_keys = date_keys
            print(f"取得天數成功: {date_keys}")
        else:
            print(f"無法訪問頁面，狀態碼: {response.status_code}")

    def reload(self, alert):
        alert.accept()
        self.driver.get(self.select_url)
        self.run(reRun=True)

if __name__ == "__main__":
    bot = TixCraftBot()
    bot.getAllDate()
    bot.run(reRun=False)

    while True:
        now = datetime.now()
        # 檢查時間是否達到 3 點 0 分 1 秒
        if now.hour == 15 and now.minute >= 00 and now.second >= 1:
            try:
                bot.run()
            except Exception as e:
                logger.error(f"程式執行失敗: {str(e)}")
                input("\n按 Enter 鍵結束程式...")
            # 等待一天後再檢查，以免在當天重複執行
            time.sleep(86400)  # 86400 秒 = 24 小時
        else:
            # 確保每秒檢查一次，避免錯過目標時間
            time.sleep(0.2)
