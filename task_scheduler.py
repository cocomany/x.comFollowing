from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import json
from twitter_following_crawler import TwitterFollowingCrawler
from query_db import get_source_accounts, insert_task_log, update_task_log

class TaskScheduler:
    _instance = None
    
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
        # 创建任务日志
        log_id = insert_task_log({
            'task_type': 'scheduled_crawl',
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'running',
            'log_content': '开始执行定时爬取任务...\n',
            'affected_accounts': ''
        })
        
        try:
            # 获取所有源账号
            source_accounts = get_source_accounts()
            if not source_accounts:
                raise Exception("没有找到源账号")
            
            # 记录受影响的账号
            affected_accounts = source_accounts
            
            # 更新日志
            update_task_log(log_id, {
                'log_content': f'找到{len(source_accounts)}个源账号，开始爬取...\n',
                'affected_accounts': ','.join(affected_accounts)
            })
            
            # 从配置文件读取认证信息
            with open('config/cookies.txt', 'r', encoding='utf-8') as f:
                lines = f.readlines()
                authorization = lines[0].strip() if lines else ''
                cookie = lines[1].strip() if len(lines) > 1 else ''
            
            if not authorization or not cookie:
                raise Exception("未找到有效的认证信息")
            
            # 遍历每个账号进行爬取
            for account in source_accounts:
                try:
                    # 创建爬虫实例并执行爬取
                    crawler = TwitterFollowingCrawler(account, authorization, cookie)
                    crawler.run()
                    
                    # 更新日志
                    current_log = update_task_log(log_id, return_current=True)
                    new_log = current_log['log_content'] + f"成功爬取账号 {account}\n"
                    update_task_log(log_id, {'log_content': new_log})
                    
                except Exception as e:
                    # 记录单个账号爬取失败
                    current_log = update_task_log(log_id, return_current=True)
                    new_log = current_log['log_content'] + f"爬取账号 {account} 失败: {str(e)}\n"
                    update_task_log(log_id, {'log_content': new_log})
                finally:
                    # 确保爬虫实例被正确关闭
                    if 'crawler' in locals():
                        crawler.close()
            
            # 完成任务，更新状态
            update_task_log(log_id, {
                'status': 'completed',
                'end_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'log_content': current_log['log_content'] + '任务完成\n'
            })
            
        except Exception as e:
            # 任务失败，更新状态
            update_task_log(log_id, {
                'status': 'failed',
                'end_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'log_content': f'任务失败: {str(e)}\n'
            })

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
