from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import sqlite3
from datetime import datetime
import json
from typing import List
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import os
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class TwitterFollowingCrawler:
    def __init__(self, source_account: str, authorization: str, cookie: str, scroll_count: int = 10):
        self.source_account = source_account
        self.authorization = authorization
        self.cookie = cookie
        self.scroll_count = scroll_count
        self.driver = None
        self.db_conn = None
        self.screenshots_dir = "screenshots"
        
    def init_driver(self):
        """初始化Chrome driver并加载cookie"""
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        # 使用 webdriver_manager 自动下载匹配的 ChromeDriver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        
        # 设置更长的隐式等待时间
        self.driver.implicitly_wait(10)
        
        # 首问X(Twitter)以设置cookie
        self.driver.get("https://x.com")
        time.sleep(2)
        
        # 解析并设置cookies
        cookies = self._parse_cookies_from_text(self.cookie)
        
        if not cookies:
            raise Exception("未能从文件中解析到有效的cookies，请检查cookies格式是否正确")
        
        # 设置cookies
        for cookie in cookies:
            cookie_dict = {
                'name': cookie['name'],
                'value': cookie['value'],
                'domain': '.x.com'
            }
            try:
                self.driver.add_cookie(cookie_dict)
            except Exception as e:
                logging.warning(f"添加cookie失败: {cookie['name']}, 错误: {str(e)}")
        
        # 设置authorization和其他headers
        if self.authorization:
            self.driver.execute_cdp_cmd('Network.setExtraHTTPHeaders', {
                'headers': {
                    'authorization': self.authorization,
                    'x-twitter-auth-type': 'OAuth2Session',
                    'x-twitter-active-user': 'yes',
                    'x-twitter-client-language': 'en'
                }
            })
        else:
            raise Exception("未找到authorization信息，请确保提供了authorization")
        
        # 验证cookies是否生效
        logging.info("正在验证cookies...")
        self.driver.get("https://x.com/home")
        time.sleep(3)  # 等待页面加载
        
        # 检查是否被重定向到登录页面
        if "x.com/login" in self.driver.current_url:
            raise Exception("Cookie验证失败：被重定向到登录页面，请更新cookies")
        
        # 检查是否能找到首页特有的元素
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="primaryColumn"]'))
            )
            logging.info("Cookies验证成功！")
        except Exception as e:
            raise Exception("Cookie验证失败：无法加载Twitter首页，请检查cookies是否有效") from e
    
    def _parse_cookies_from_text(self, cookies_text):
        """从文本中解析cookies"""
        cookies_list = []
        lines = cookies_text.strip().split(';')
        
        for line in lines:
            line = line.strip()
            if '=' in line:
                name, value = line.split('=', 1)
                cookies_list.append({
                    "name": name.strip(),
                    "value": value.strip()
                })
        
        return cookies_list

    def init_db(self):
        """初始化SQLite数据库"""
        self.db_conn = sqlite3.connect('twitter_following.db')
        cursor = self.db_conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS following (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_account TEXT,
            following_account TEXT,
            display_name TEXT,
            bio TEXT,
            detected_time DATETIME,
            detected_order DATETIME,
            UNIQUE(source_account, following_account)
        )
        ''')
        self.db_conn.commit()
    
    def scroll_page(self):
        """滚动页面到指定高度，并增加更多等待时间"""
        current_position = self.driver.execute_script("return window.pageYOffset;")
        self.driver.execute_script(f"window.scrollTo(0, {current_position + 1500});")
        time.sleep(3)  # 增加等待时间，确保内容加载
        
    def parse_following_list(self, html: str) -> List[tuple]:
        """解析页面HTML获取following列表"""
        soup = BeautifulSoup(html, 'html.parser')
        following_accounts = []
        seen_accounts = set()  # 用于去重
        
        timeline_div = soup.find('div', attrs={'aria-label': 'Timeline: Following'})
        if not timeline_div:
            logging.warning("未找到Following Timeline容器")
            return []
        
        user_cells = timeline_div.find_all('div', attrs={'data-testid': 'cellInnerDiv'})
        logging.info(f"找到 {len(user_cells)} 个用户单元格")
        
        for index, cell in enumerate(user_cells):
            try:
                follow_button = cell.find('button', attrs={'aria-label': lambda x: x and 'Follow @' in x})
                if not follow_button:
                    continue
                    
                username = follow_button.get('aria-label', '').replace('Follow @', '@')
                
                display_name_div = cell.find('div', attrs={'style': lambda x: x and 'color: rgb(231, 233, 234)' in x})
                display_name = display_name_div.text.strip() if display_name_div else username.replace('@', '')
                
                bio_div = cell.find('div', class_='r-1jeg54m')
                bio = bio_div.text.strip() if bio_div else ""
                
                if username not in seen_accounts:
                    seen_accounts.add(username)
                    account_info = {
                        "username": username,
                        "display_name": display_name,
                        "bio": bio
                    }
                    following_accounts.append((account_info, index))
                    logging.info(f"找到账号 {index+1}: {username} ({display_name})")
                    
            except Exception as e:
                logging.error(f"解析元素时出错: {str(e)}")
                continue
        
        return following_accounts
    
    def save_to_db(self, following_accounts: List[tuple]):
        """保存following数据到数据库"""
        cursor = self.db_conn.cursor()
        current_time = datetime.now()
        base_timestamp = current_time.timestamp()
        
        for (account_info, order) in following_accounts:
            try:
                order_time = datetime.fromtimestamp(base_timestamp - order/1000)
                
                username = account_info['username'].replace('@', '')
                display_name = account_info['display_name']
                bio = account_info['bio']
                
                cursor.execute('''
                SELECT id FROM following 
                WHERE source_account = ? AND following_account = ?
                ''', (self.source_account, username))
                
                if cursor.fetchone() is None:
                    cursor.execute('''
                    INSERT INTO following (
                        source_account, 
                        following_account,
                        display_name,
                        bio, 
                        detected_time,
                        detected_order
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''', (self.source_account, username, display_name, bio, current_time, order_time))
                else:
                    cursor.execute('''
                    UPDATE following 
                    SET display_name = ?,
                        bio = ?,
                        detected_time = ?
                    WHERE source_account = ? AND following_account = ?
                    ''', (display_name, bio, current_time, self.source_account, username))
                    
            except sqlite3.Error as e:
                logging.error(f"数据库操作失败: {self.source_account} -> {username}, 错误: {str(e)}")
                
        self.db_conn.commit()
    
    def run(self):
        """运行爬虫程序"""
        try:
            self.init_driver()
            self.init_db()
            
            url = f"https://x.com/{self.source_account}/following"
            self.driver.get(url)
            
            account_screenshot_dir = os.path.join(self.screenshots_dir, self.source_account)
            os.makedirs(account_screenshot_dir, exist_ok=True)
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            try:
                WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="primaryColumn"]'))
                )
                
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="cellInnerDiv"]'))
                )
                
                screenshot_path = os.path.join(
                    account_screenshot_dir, 
                    f"{current_time}_initial_{self.source_account}.png"
                )
                self.driver.save_screenshot(screenshot_path)
                
                logging.info(f"开始为 {self.source_account} 滚动页面...")
                for i in range(self.scroll_count):
                    logging.info(f"第 {i+1} 次滚动")
                    self.scroll_page()
                    
                    screenshot_path = os.path.join(
                        account_screenshot_dir,
                        f"{current_time}_scroll_{i+1}_{self.source_account}.png"
                    )
                    self.driver.save_screenshot(screenshot_path)
                
                following_accounts = self.parse_following_list(self.driver.page_source)
                logging.info(f"\n为 {self.source_account} 找到 {len(following_accounts)} 个关注账号:")
                for account_info, _ in following_accounts:
                    logging.info(f"  {account_info['display_name']} ({account_info['username']})")
                    if account_info['bio']:
                        logging.info(f"    Bio: {account_info['bio']}")
                
                self.save_to_db(following_accounts)
                
            except Exception as e:
                logging.error(f"抓取账号 {self.source_account} 时发生错误: {str(e)}")
                error_screenshot = os.path.join(
                    account_screenshot_dir,
                    f"{current_time}_error_{self.source_account}.png"
                )
                self.driver.save_screenshot(error_screenshot)
                error_html = os.path.join(
                    account_screenshot_dir,
                    f"{current_time}_error_{self.source_account}.html"
                )
                with open(error_html, "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                raise
                
        finally:
            if self.driver:
                self.driver.quit()
            if self.db_conn:
                self.db_conn.close()
