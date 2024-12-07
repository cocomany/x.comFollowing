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
        # 设置 selenium 和 urllib3 的日志为 WARNING 以上
        selenium_logger = logging.getLogger('selenium')
        selenium_logger.setLevel(logging.WARNING)
        urllib3_logger = logging.getLogger('urllib3')
        urllib3_logger.setLevel(logging.WARNING)
        
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        # SSL相关选项
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')
        options.add_argument('--allow-insecure-localhost')
        # 性能优化选项
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-logging')  # 禁用 Chrome 日志
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-default-apps')
        # 添加日志控制
        options.add_experimental_option('excludeSwitches', ['enable-logging'])  # 禁用 DevTools 日志
        
        try:
            # 使用 webdriver_manager 自动下载匹配的 ChromeDriver
            driver_path = ChromeDriverManager().install()
            # 确保使用正确的 chromedriver.exe 路径
            if os.path.exists(driver_path):
                driver_dir = os.path.dirname(driver_path)
                if 'win32' in driver_dir:
                    chromedriver_path = os.path.join(driver_dir, 'chromedriver.exe')
                else:
                    chromedriver_path = os.path.join(driver_dir, 'chromedriver')
                    
                if os.path.exists(chromedriver_path):
                    service = Service(chromedriver_path)
                    logging.info(f"使用 ChromeDriver 路径: {chromedriver_path}")
                else:
                    raise Exception(f"ChromeDriver 可执行文件未找到: {chromedriver_path}")
            else:
                raise Exception(f"ChromeDriver 路径无效: {driver_path}")
            
            self.driver = webdriver.Chrome(service=service, options=options)
            logging.info(f"Chrome 浏览器版本: {self.driver.capabilities['browserVersion']}")
            
            # 设置更长的隐式等待时间
            self.driver.implicitly_wait(10)
            
            # 首问X(Twitter)以设置cookie
            try:
                self.driver.get("https://x.com")
                time.sleep(2)
            except Exception as e:
                logging.error(f"访问 X.com 失败: {str(e)}")
                if "net::ERR_CERT_" in str(e):
                    logging.info("尝试通过 SSL 证书错误...")
                    self.driver.get("javascript:document.querySelector('#proceed-button').click()")
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
                
        except Exception as e:
            logging.error(f"Chrome driver 初始化或访问X.com失败: {str(e)}")
            if hasattr(e, '__cause__'):
                logging.error(f"原始错误: {e.__cause__}")
            if self.driver:
                self.driver.quit()
            raise Exception("浏览器初始化失败，请确保Chrome浏览器已正确安装且版本兼容") from e
    
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
        
        # 原有的following表
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
        
        # 新增用户统计信息表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            following_count INTEGER,
            follower_count INTEGER,
            detected_time DATETIME,
            UNIQUE(username, detected_time)
        )
        ''')
        
        self.db_conn.commit()
    
    def scroll_page(self):
        """滚动页面到指定高度，并增加更多等待时间"""
        current_position = self.driver.execute_script("return window.pageYOffset;")
        self.driver.execute_script(f"window.scrollTo(0, {current_position + 2500});")
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
        
        user_cells = timeline_div.find_all('button', attrs={'data-testid': 'UserCell'})
        logging.info(f"找到 {len(user_cells)} 个following用户")
        
        for index, cell in enumerate(user_cells):
            try:
                # 查找"Click to Follow"提示文本 - 使用更精确的选择器
                follow_hint_div = cell.find('div', attrs={
                    'dir': 'auto',
                    'style': 'display: none;',
                    'id': lambda x: x and x.startswith('id__')  # 确保是带有id__前缀的div
                })
                
                if follow_hint_div and 'Click to Follow' in follow_hint_div.text:
                    # 从"Click to Follow xxx"中提取用户名
                    username = '@' + follow_hint_div.text.replace('Click to Follow ', '')
                    # logging.info(f"--原始提示文本: {follow_hint_div.text}")
                    # logging.info(f"--找到账号 {index+1}: {username}")
                    
                    # 找到用信息区域获取其他信息
                    user_info_div = cell.find('div', class_='r-1iusvr4')
                    if not user_info_div:
                        continue
                    
                    # 获取显示名称 - 使用更精确的选择器
                    display_name_div = user_info_div.find('div', attrs={
                        'class': lambda x: x and 'r-bcqeeo' in x and 'r-qvutc0' in x and 'r-b88u0q' in x
                    })
                    display_name = display_name_div.get_text().strip() if display_name_div else username.replace('@', '')
                    
                    # 打印更多调试信息
                    logging.info(f"--找到账号 {index+1}: : {username}, {display_name}")
                    
                    # 获取bio
                    bio_div = cell.find('div', class_='r-1jeg54m')
                    bio = bio_div.get_text().strip() if bio_div else ""
                    
                    if username and username not in seen_accounts:
                        seen_accounts.add(username)
                        account_info = {
                            "username": username,
                            "display_name": display_name,
                            "bio": bio
                        }
                        following_accounts.append((account_info, index))
                        
                else:
                    # 如果没有找到Click to Follow提示，打印调试信息
                    logging.warning(f"第 {index+1} 个用户单元未找到有效的Follow提示文本")
                    if follow_hint_div:
                        logging.warning(f"--找到的提示文本: {follow_hint_div.text}")
                
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
    
    def get_user_stats(self, username: str) -> dict:
        """获取用户主页的统计数据"""
        url = f"https://x.com/{username}"
        self.driver.get(url)
        time.sleep(5)  # 增加等待时间
        
        try:
            # 等待用户统计信息加载
            stats_container = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="primaryColumn"]'))
            )
            
            # 保存主页截图
            account_screenshot_dir = os.path.join(self.screenshots_dir, username)
            os.makedirs(account_screenshot_dir, exist_ok=True)
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            profile_screenshot_path = os.path.join(
                account_screenshot_dir,
                f"{current_time}_profile_{username}.png"
            )
            self.driver.save_screenshot(profile_screenshot_path)
            logging.info(f"已保存用户 {username} 的主页截图")
            
            try:
                # 使用不区分大小写的XPath来查找链接
                xpath_query = (
                    f"//a[contains(translate(@href, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
                    f"'/{username.lower()}/following') or "
                    f"contains(translate(@href, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
                    f"'/{username.lower()}/followers') or "
                    f"contains(translate(@href, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
                    f"'/{username.lower()}/verified_followers')]"
                )
                
                stats_links = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, xpath_query))
                )
                
                # 提取数字的辅助函数
                def parse_count(text):
                    if not text:
                        return 0
                    text = text.strip().split()[0].replace(',', '')
                    if 'K' in text:
                        return int(float(text.replace('K', '')) * 1000)
                    if 'M' in text:
                        return int(float(text.replace('M', '')) * 1000000)
                    return int(text) if text.isdigit() else 0
                
                following_count = 0
                follower_count = 0
                
                for link in stats_links:
                    href = link.get_attribute('href').lower()
                    # 获取链接中的第一个数字文本
                    spans = link.find_elements(By.CSS_SELECTOR, 'span')
                    count_text = ''
                    for span in spans:
                        text = span.text.strip()
                        if text and (text.replace(',', '').replace('.', '').replace('K', '').replace('M', '').isdigit() or 
                                   any(char in text for char in ['K', 'M'])):
                            count_text = text
                            break
                    
                    if f'/{username.lower()}/following' in href:
                        following_count = parse_count(count_text)
                    elif f'/{username.lower()}/followers' in href or f'/{username.lower()}/verified_followers' in href:
                        follower_count = parse_count(count_text)
                
                if following_count == 0 and follower_count == 0:
                    logging.warning(f"未能找到用户 {username} 的统计信息")
                    return None
                    
                logging.info(f"成功获取用户 {username} 的统计信息: Following: {following_count}, Followers: {follower_count}")
                return {
                    'following_count': following_count,
                    'follower_count': follower_count
                }
                
            except Exception as e:
                # 保存错误信息和截图
                error_screenshot = os.path.join(
                    account_screenshot_dir,
                    f"{current_time}_profile_error_{username}.png"
                )
                self.driver.save_screenshot(error_screenshot)
                
                error_html = os.path.join(
                    account_screenshot_dir,
                    f"{current_time}_profile_error_{username}.html"
                )
                with open(error_html, "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                    
                logging.error(f"获取用户 {username} 统计信息失败: {str(e)}")
                return None
                
        except Exception as e:
            logging.error(f"获取用户 {username} 统计信息失败: {str(e)}")
            return None
    
    def save_user_stats(self, username: str, stats: dict):
        """保存用户统计信息到数据库"""
        if not stats:
            return
        
        cursor = self.db_conn.cursor()
        current_time = datetime.now()
        
        try:
            cursor.execute('''
            INSERT INTO user_stats (
                username,
                following_count,
                follower_count,
                detected_time
            )
            VALUES (?, ?, ?, ?)
            ''', (
                username,
                stats['following_count'],
                stats['follower_count'],
                current_time
            ))
            self.db_conn.commit()
            logging.info(f"已保存用户 {username} 的统计信息")
        except sqlite3.Error as e:
            logging.error(f"保存用户统计信息失败: {str(e)}")
    
    def close(self):
        """关闭爬虫实例，释放资源"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
            if self.db_conn:
                self.db_conn.close()
                self.db_conn = None
        except Exception as e:
            logging.error(f"关闭爬虫实例时发生错误: {str(e)}")
    
    def run(self, progress_callback=None):
        """运行爬虫程序"""
        try:
            self.init_driver()
            self.init_db()
            
            url = f"https://x.com/{self.source_account.lower()}/following"
            self.driver.get(url)
            time.sleep(5)  # 等待初始页面加载
            
            if progress_callback:
                progress_callback(f"开始爬取账号 {self.source_account} 的 following 列表...")
            
            try:
                # 等待Following列表加载
                WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="UserCell"]'))
                )
                
                # 执行滚动加载
                last_height = 0
                scroll_count = 0
                all_following_accounts = []
                
                while scroll_count < self.scroll_count:
                    # 获取当前页面内容
                    following_accounts = self.parse_following_list(self.driver.page_source)
                    all_following_accounts.extend(following_accounts)
                    
                    # 记录进度日志
                    if progress_callback:
                        progress_callback(f"账号 {self.source_account} - 第 {scroll_count + 1} 次滚动，当前已获取 {len(all_following_accounts)} 个账号")
                    
                    # 滚动页面
                    current_height = self.driver.execute_script("return document.documentElement.scrollHeight")
                    if current_height == last_height:
                        # 如果高度没有变化，可能已经到底或需要等待加载
                        time.sleep(3)  # 多等待一下
                        new_height = self.driver.execute_script("return document.documentElement.scrollHeight")
                        if new_height == current_height:
                            logging.info("已到达页面底部或无法加载更多内容")
                            break
                    
                    # 执行滚动
                    self.driver.execute_script(f"window.scrollTo(0, {current_height});")
                    time.sleep(2)  # 等待内容加载
                    
                    # 保存滚动截图
                    account_screenshot_dir = os.path.join(self.screenshots_dir, self.source_account.lower())
                    os.makedirs(account_screenshot_dir, exist_ok=True)
                    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                    screenshot_path = os.path.join(
                        account_screenshot_dir,
                        f"{current_time}_scroll_{scroll_count + 1}_{self.source_account.lower()}.png"
                    )
                   
                    self.driver.save_screenshot(screenshot_path)
                    
                    last_height = current_height
                    scroll_count += 1
                
                # 保存所有获取到的账号
                if all_following_accounts:
                    self.save_to_db(all_following_accounts)
                    if progress_callback:
                        progress_callback(f"账号 {self.source_account} - 已成功保存 {len(all_following_accounts)} 个following账号")
                else:
                    if progress_callback:
                        progress_callback(f"账号 {self.source_account} - 未找到following账号")
                
            except Exception as e:
                error_msg = f"账号 {self.source_account} - 爬取失败: {str(e)}"
                if progress_callback:
                    progress_callback(error_msg)
                raise Exception(error_msg)
                
        finally:
            self.close()
