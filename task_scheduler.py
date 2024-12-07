from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import json
from twitter_following_crawler import TwitterFollowingCrawler
from query_db import get_source_accounts, insert_task_log, update_task_log
from utils.logger import TaskLogger

class TaskScheduler:
    _instance = None
    
    # 添加任务状态常量
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TaskScheduler()
        return cls._instance
    
    def __init__(self):
        if TaskScheduler._instance is not None:
            raise Exception("This class is a singleton!")
        
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self._enabled = False
        self.current_job = None
        self._hour = 8
        self._minute = 0
        
    def is_enabled(self):
        return self._enabled
    
    def start(self):
        if not self._enabled:
            self._enabled = True
            self._schedule_job()
    
    def stop(self):
        if self._enabled:
            self._enabled = False
            if self.current_job:
                self.current_job.remove()
                self.current_job = None
    
    def _schedule_job(self):
        if self.current_job:
            self.current_job.remove()
        
        self.current_job = self.scheduler.add_job(
            self._run_crawler_task,
            CronTrigger(hour=self._hour, minute=self._minute),
            id='crawler_task'
        )
    
    def update_schedule(self, hour, minute):
        self._hour = hour
        self._minute = minute
        if self._enabled:
            self._schedule_job()
    
    def get_schedule(self):
        next_run = None
        if self.current_job:
            next_run = self.current_job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')
        return {
            'hour': self._hour,
            'minute': self._minute,
            'next_run': next_run
        }
    
    def run_now(self):
        """立即执行一次爬取任务"""
        self.scheduler.add_job(self._run_crawler_task, 'date')
    
    def _run_crawler_task(self):
        """执行爬取任务的具体实现"""
        log_id = None
        current_log = None
        task_logger = None
        
        try:
            # 创建任务日志，使用状态常量
            log_id = insert_task_log({
                'task_type': 'scheduled_crawl',
                'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': self.STATUS_RUNNING,  # 使用状态常量
                'log_content': '开始执行定时爬取任务...\n',
                'affected_accounts': ''
            })
            
            # 创建任务日志记录器
            task_logger = TaskLogger(log_id)
            task_logger.info('开始执行定时爬取任务...')
            
            # 获取所有源账号
            source_accounts = get_source_accounts()
            if not source_accounts:
                raise Exception("没有找到源账号")
            
            # 记录受影响的账号
            affected_accounts = []
            
            # 更新日志
            message = f'找到{len(source_accounts)}个源账号，开始爬取...'
            task_logger.info(message)
            current_log = update_task_log(log_id, {
                'log_content': task_logger.get_log_content(),
                'affected_accounts': ','.join(source_accounts)
            }, return_current=True)
            
            # 从配置文件读取认证信息
            with open('config/cookies.txt', 'r', encoding='utf-8') as f:
                lines = f.readlines()
                authorization = lines[0].strip() if lines else ''
                cookie = lines[1].strip() if len(lines) > 1 else ''
            
            if not authorization or not cookie:
                raise Exception("未找到有效的认证信息")
            
            # 遍历每个账号进行爬取
            for i, account in enumerate(source_accounts, 1):
                crawler = None
                try:
                    # 更新日志，标记当前正在爬取的账号
                    message = f"[{i}/{len(source_accounts)}] 正在爬取账号 {account}..."
                    task_logger.info(message)
                    current_log = update_task_log(log_id, {
                        'log_content': task_logger.get_log_content(),
                        'affected_accounts': ','.join(source_accounts)
                    }, return_current=True)
                    
                    # 创建爬虫实例并执行爬取
                    crawler = TwitterFollowingCrawler(account, authorization, cookie)
                    
                    # 添加进度回调
                    def progress_callback(message):
                        nonlocal current_log
                        task_logger.info(message)
                        current_log = update_task_log(log_id, {
                            'log_content': task_logger.get_log_content()
                        }, return_current=True)
                    
                    # 执行爬取
                    crawler.run(progress_callback=progress_callback)
                    
                    # 爬取成功，添加到受影响账号列表
                    affected_accounts.append(account)
                    
                    # 更新日志
                    task_logger.info(f"成功爬取账号 {account}")
                    current_log = update_task_log(log_id, {
                        'log_content': task_logger.get_log_content(),
                        'affected_accounts': ','.join(affected_accounts)
                    }, return_current=True)
                    
                except Exception as e:
                    # 记录单个账号爬取失败
                    task_logger.error(f"爬取账号 {account} 失败: {str(e)}")
                    current_log = update_task_log(log_id, {
                        'log_content': task_logger.get_log_content()
                    }, return_current=True)
                finally:
                    if crawler:
                        crawler.close()
            
            # 完成任务，更新状态
            task_logger.info('任务完成')
            update_task_log(log_id, {
                'status': self.STATUS_COMPLETED,  # 使用状态常量
                'end_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'log_content': task_logger.get_log_content(),
                'affected_accounts': ','.join(affected_accounts)
            })
            
        except Exception as e:
            # 任务失败，更新状态
            if task_logger:
                task_logger.error(f'任务失败: {str(e)}')
            if log_id:
                update_task_log(log_id, {
                    'status': self.STATUS_FAILED,  # 使用状态常量
                    'end_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'log_content': task_logger.get_log_content() if task_logger else f'任务失败: {str(e)}\n'
                })
            raise

def get_recent_logs(limit=5):
    """获取最近的任务日志"""
    db_path = os.path.join(os.path.dirname(__file__), 'twitter_following.db')
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT task_type, start_time, end_time, status, log_content, affected_accounts
            FROM task_logs
            ORDER BY start_time DESC
            LIMIT ?
        ''', (limit,))
        
        logs = cursor.fetchall()
        return [{
            'task_type': log[0],
            'start_time': log[1],
            'end_time': log[2],
            'status': log[3],
            'log_content': log[4],
            'affected_accounts': log[5]
        } for log in logs]
        
    except Exception as e:
        logging.error(f"获取任务日志失败: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()
