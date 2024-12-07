from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import json
import os
from twitter_following_crawler import TwitterFollowingCrawler
from query_db import get_source_accounts
from utils.logger import TaskLogger

class TaskScheduler:
    _instance = None
    CONFIG_FILE = 'config/schedule.json'
    
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
        self.current_job = None
        
        # 从配置文件加载调度设置
        self._load_config()
        
    def _load_config(self):
        """从配置文件加载调度设置"""
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, 'r') as f:
                config = json.load(f)
                self._enabled = config.get('enabled', False)
                self._hour = config.get('hour', 8)
                self._minute = config.get('minute', 0)
        else:
            self._enabled = False
            self._hour = 8
            self._minute = 0
            self._save_config()
        
        if self._enabled:
            self._schedule_job()
    
    def _save_config(self):
        """保存调度设置到配置文件"""
        os.makedirs('config', exist_ok=True)
        config = {
            'enabled': self._enabled,
            'hour': self._hour,
            'minute': self._minute
        }
        with open(self.CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    
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
        
        try:
            self.current_job = self.scheduler.add_job(
                self._run_crawler_task,
                CronTrigger(hour=self._hour, minute=self._minute),
                id='crawler_task'
            )
            # 保存配置
            self._save_config()
        except Exception as e:
            print(f"调度任务设置失败: {str(e)}")
            self.current_job = None
    
    def update_schedule(self, hour, minute):
        self._hour = hour
        self._minute = minute
        # 保存更新后的配置
        self._save_config()
        if self._enabled:
            self._schedule_job()
    
    def get_schedule(self):
        next_run = None
        try:
            if self.current_job and self.current_job.next_run_time:
                next_run = self.current_job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')
                print(f"下次执行时间: {next_run}")
            else:
                print("没有找到下次执行时间")
                if not self.current_job:
                    print("current_job 为 None")
                elif not self.current_job.next_run_time:
                    print("next_run_time 为 None")
        except Exception as e:
            print(f"获取调度信息时出错: {str(e)}")
        
        schedule_info = {
            'hour': self._hour,
            'minute': self._minute,
            'next_run': next_run,
            'enabled': self._enabled
        }
        print(f"返回调度信息: {schedule_info}")
        return schedule_info
    
    def run_now(self):
        """立即执行一次爬取任务"""
        # 使用绝对路径
        base_dir = os.path.abspath(os.path.dirname(__file__))
        logs_dir = os.path.join(base_dir, 'logs')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f'task_{timestamp}.log'
        log_path = os.path.join(logs_dir, log_filename)
        
        os.makedirs(logs_dir, exist_ok=True)
        
        # 直接执行爬虫任务，不通过调度器
        try:
            self._run_crawler_task()
        except Exception as e:
            print(f"立即执行任务失败: {str(e)}")
            raise
    
    def _run_crawler_task(self):
        """执行爬取任务的具体实现"""
        # 使用绝对路径
        base_dir = os.path.abspath(os.path.dirname(__file__))
        logs_dir = os.path.join(base_dir, 'logs')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f'task_{timestamp}.log'
        log_path = os.path.join(logs_dir, log_filename)
        
        os.makedirs(logs_dir, exist_ok=True)
        
        task_logger = TaskLogger(log_path)
        
        try:
            task_logger.info('开始执行定时爬取任务...')
            
            # 获取所有源账号
            source_accounts = get_source_accounts()
            if not source_accounts:
                raise Exception("没有找到源账号")
            
            task_logger.info(f'找到{len(source_accounts)}个源账号，开始爬取...')
            
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
                    task_logger.info(f"[{i}/{len(source_accounts)}] 正在爬取账号 {account}...")
                    
                    crawler = TwitterFollowingCrawler(account, authorization, cookie)
                    # 将爬虫的日志也传递给任务日志记录器
                    crawler.run(progress_callback=task_logger.info)
                    
                    task_logger.info(f"成功爬取账号 {account}")
                    
                except Exception as e:
                    # 记录详细的错误信息和堆栈跟踪
                    import traceback
                    error_msg = f"爬取账号 {account} 失败: {str(e)}\n{traceback.format_exc()}"
                    task_logger.error(error_msg)
                finally:
                    if crawler:
                        crawler.close()
            
            task_logger.info('任务完成')
            
        except Exception as e:
            # 记录详细的错误信息和堆栈跟踪
            import traceback
            error_msg = f'任务失败: {str(e)}\n{traceback.format_exc()}'
            task_logger.error(error_msg)
            raise

def get_recent_logs(limit=5):
    """获取最近的日志文件列表"""
    logs_dir = 'logs'
    if not os.path.exists(logs_dir):
        return []
    
    log_files = []
    for filename in os.listdir(logs_dir):
        if filename.endswith('.log'):
            file_path = os.path.join(logs_dir, filename)
            log_files.append({
                'filename': filename,
                'path': file_path,
                'time': datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
                'size': os.path.getsize(file_path)
            })
    
    # 按创建时间倒序排序
    log_files.sort(key=lambda x: x['time'], reverse=True)
    return log_files[:limit]
