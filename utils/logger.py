import logging
from logging.handlers import RotatingFileHandler
import os

class TaskLogger:
    def __init__(self, log_path):
        self.log_path = log_path
        self.logger = self._setup_logger()
        
    def _setup_logger(self):
        # 确保日志目录存在
        log_dir = os.path.dirname(self.log_path)
        os.makedirs(log_dir, exist_ok=True)
        
        logger = logging.getLogger(f'task_logger_{os.path.basename(self.log_path)}')
        logger.setLevel(logging.INFO)
        
        # 清除之前的处理器
        if logger.handlers:
            logger.handlers.clear()
        
        # 创建文件处理器
        file_handler = RotatingFileHandler(
            self.log_path,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        
        # 设置格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s',
                                   datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        return logger
    
    def info(self, message):
        self.logger.info(message)
        
    def error(self, message):
        self.logger.error(message)
        
    def get_log_content(self):
        if os.path.exists(self.log_path):
            with open(self.log_path, 'r', encoding='utf-8') as f:
                return f.read()
        return "" 