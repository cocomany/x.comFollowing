import sqlite3
import os

def reset_database():
    db_path = 'twitter_following.db'
    
    try:
        # 创建或打开数据库连接
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 删除已存在的表
        cursor.execute('DROP TABLE IF EXISTS following')
        
        # 创建following表
        cursor.execute('''
        CREATE TABLE following (
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
        
        conn.commit()
        print("数据库已重置，表结构已创建")
        
    except sqlite3.Error as e:
        print(f"创建数据库失败: {str(e)}")
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # 执行重置
    reset_database()
