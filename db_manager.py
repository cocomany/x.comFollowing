from sqlalchemy import create_engine, event
from sqlalchemy.pool import SingletonThreadPool
import sqlite3
import os

class DatabaseManager:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = DatabaseManager()
        return cls._instance
    
    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, 'twitter_following.db')
        
        # 创建数据库引擎，使用SingletonThreadPool
        self.engine = create_engine(
            f'sqlite:///{db_path}',
            poolclass=SingletonThreadPool,
            pool_size=1,  # 只使用一个连接
            connect_args={
                'timeout': 60,
                'check_same_thread': False
            }
        )
        
        # 初始化数据库设置
        with self.engine.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=60000")
            conn.execute("PRAGMA synchronous=NORMAL")

    def get_connection(self):
        return self.engine.connect()

db_manager = DatabaseManager.get_instance()

def get_db_connection():
    """获取数据库连接"""
    return db_manager.get_connection() 