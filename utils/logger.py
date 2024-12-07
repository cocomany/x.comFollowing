import os
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

class TaskLogger:
    def __init__(self, task_id):
        self.task_id = task_id
        self.log_dir = 'logs'
        self.log_file = self._get_log_file()
        self.logger = self._setup_logger()
        
    def _get_log_file(self):
        """获取日志文件路径"""
        # 确保logs目录存在
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        
        # 使用任务ID和时间创建日志文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return os.path.join(self.log_dir, f'task_{self.task_id}_{timestamp}.log')
    
    def _setup_logger(self):
        """设置日志记录器"""
        logger = logging.getLogger(f'task_{self.task_id}')
        logger.setLevel(logging.INFO)
        
        # 创建文件处理器
        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.INFO)
        
        # 设置日志格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
        file_handler.setFormatter(formatter)
        
        # 添加处理器
        logger.addHandler(file_handler)
        
        return logger
    
    def info(self, message):
        """记录信息日志"""
        self.logger.info(message)
        
    def error(self, message):
        """记录错误日志"""
        self.logger.error(message)
    
    def get_log_content(self):
        """获取当前日志文件内容"""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"读取日志文件失败: {str(e)}" 