#!/usr/bin/env python3
import sqlite3
import os
from datetime import datetime
import itertools

def get_db_connection():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, 'twitter_following.db')
    return sqlite3.connect(db_path)

def get_source_accounts():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT source_account FROM following ORDER BY source_account")
        source_accounts = [row[0] for row in cursor.fetchall()]
        
        return source_accounts
    
    except sqlite3.Error as e:
        print(f"查询source_account失败: {str(e)}")
        return []
    
    finally:
        if conn:
            conn.close()

def get_following_list(account, days=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if days:
            query = """
            SELECT 
                following_account, 
                display_name, 
                bio, 
                detected_time
            FROM 
                following
            WHERE 
                source_account = ?
                AND datetime(detected_time) >= datetime('now', '-' || ? || ' days')
            ORDER BY 
                detected_time DESC
            """
            cursor.execute(query, (account, days))
        else:
            query = """
            SELECT 
                following_account, 
                display_name, 
                bio, 
                detected_time
            FROM 
                following
            WHERE 
                source_account = ?
            ORDER BY 
                detected_time DESC
            """
            cursor.execute(query, (account,))
            
        followings = cursor.fetchall()
        
        result = [
            {
                'following_account': row[0],
                'display_name': row[1],
                'bio': row[2],
                'detected_time': row[3]
            } for row in followings
        ]
        
        return result
    
    except sqlite3.Error as e:
        print(f"查询Following列表失败: {str(e)}")
        return []
    
    finally:
        if conn:
            conn.close()

def get_common_following(accounts):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        placeholders = ','.join(['?' for _ in accounts])
        query = f"""
        SELECT 
            f.following_account, 
            f.display_name, 
            f.bio, 
            MAX(f.detected_time) as latest_detected_time
        FROM 
            following f
        WHERE 
            f.source_account IN ({placeholders})
        GROUP BY 
            f.following_account, f.display_name, f.bio
        HAVING 
            COUNT(DISTINCT f.source_account) = ?
        ORDER BY 
            latest_detected_time DESC
        """
        
        cursor.execute(query, accounts + [len(accounts)])
        common_followings = cursor.fetchall()
        
        result = [
            {
                'following_account': row[0], 
                'display_name': row[1], 
                'bio': row[2], 
                'detected_time': row[3]
            } for row in common_followings
        ]
        
        return result
    
    except sqlite3.Error as e:
        print(f"查询共同关注失败: {str(e)}")
        return []
    
    finally:
        if conn:
            conn.close()

def generate_comparison_report():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT source_account FROM following ORDER BY source_account")
        source_accounts = [row[0] for row in cursor.fetchall()]
        
        comparison_results = []
        
        for account1, account2 in itertools.combinations(source_accounts, 2):
            query = """
            SELECT 
                f.following_account, 
                f.display_name, 
                f.bio, 
                MAX(f.detected_time) as latest_detected_time
            FROM 
                following f
            WHERE 
                f.source_account IN (?, ?)
            GROUP BY 
                f.following_account, f.display_name, f.bio
            HAVING 
                COUNT(DISTINCT f.source_account) = 2
            ORDER BY 
                latest_detected_time DESC
            """
            
            cursor.execute(query, (account1, account2))
            common_followings = cursor.fetchall()
            
            if common_followings:
                result = {
                    'account1': account1,
                    'account2': account2,
                    'common_followings': [
                        {
                            'following_account': row[0], 
                            'display_name': row[1], 
                            'bio': row[2], 
                            'detected_time': row[3]
                        } for row in common_followings
                    ]
                }
                comparison_results.append(result)
        
        return comparison_results
    
    except sqlite3.Error as e:
        print(f"生成比较报告失败: {str(e)}")
        return []
    
    finally:
        if conn:
            conn.close()

def get_multiple_followed_accounts(days_ago=2):
    """
    获取在指定日期之后被多个source_account关注的following_account
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = """
            WITH following_counts AS (
                SELECT following_account, 
                       COUNT(DISTINCT source_account) as follower_count,
                       GROUP_CONCAT(DISTINCT source_account) as source_accounts
                FROM following
                WHERE datetime(detected_time) >= datetime('now', '-' || ? || ' days')
                GROUP BY following_account
                HAVING COUNT(DISTINCT source_account) > 1
            )
            SELECT following_account, follower_count, source_accounts
            FROM following_counts
            ORDER BY follower_count DESC, following_account
        """
        
        cur.execute(query, (days_ago,))
        results = cur.fetchall()
        
        # 将GROUP_CONCAT的结果转换为列表
        processed_results = []
        for row in results:
            following_account, follower_count, source_accounts_str = row
            source_accounts = source_accounts_str.split(',') if source_accounts_str else []
            processed_results.append((following_account, follower_count, source_accounts))
        
        return processed_results
    except Exception as e:
        print(f"Error in get_multiple_followed_accounts: {str(e)}")
        return []
    finally:
        if conn:
            conn.close()

def insert_task_log(log_data):
    """插入任务日志并返回日志ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO task_logs 
            (task_type, start_time, status, log_content, affected_accounts)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            log_data['task_type'],
            log_data['start_time'],
            log_data['status'],
            log_data['log_content'],
            log_data['affected_accounts']
        ))
        
        log_id = cursor.lastrowid
        conn.commit()
        return log_id
    finally:
        if conn:
            conn.close()

def update_task_log(log_id, update_data, return_current=False):
    """更新任务日志"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 构建更新语句
        update_fields = []
        update_values = []
        for key, value in update_data.items():
            update_fields.append(f"{key} = ?")
            update_values.append(value)
        
        # 添加log_id到更新值列表
        update_values.append(log_id)
        
        # 执行更新
        cursor.execute(f'''
            UPDATE task_logs
            SET {', '.join(update_fields)}
            WHERE id = ?
        ''', update_values)
        
        if return_current:
            # 获取更新后的记录
            cursor.execute('SELECT * FROM task_logs WHERE id = ?', (log_id,))
            columns = [description[0] for description in cursor.description]
            row = cursor.fetchone()
            if row:
                return dict(zip(columns, row))
        
        conn.commit()
        return None
    finally:
        if conn:
            conn.close()

def get_recent_logs(limit=5):
    """获取最近的任务日志"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, task_type, start_time, end_time, status, log_content, affected_accounts
            FROM task_logs
            ORDER BY start_time DESC
            LIMIT ?
        ''', (limit,))
        
        columns = [description[0] for description in cursor.description]
        logs = []
        for row in cursor.fetchall():
            log = dict(zip(columns, row))
            logs.append(log)
        
        return logs
    finally:
        if conn:
            conn.close()

def get_new_following_list(account, days):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT 
            following_account, 
            display_name, 
            bio, 
            detected_time
        FROM 
            following
        WHERE 
            source_account = ?
            AND datetime(detected_time, 'localtime') >= datetime('now', 'localtime', '-' || ? || ' days')
            AND datetime(detected_time, 'localtime') <= datetime('now', 'localtime')
        ORDER BY 
            detected_time DESC
        """
        
        cursor.execute(query, (account, days))
        followings = cursor.fetchall()
        
        result = [
            {
                'following_account': row[0],
                'display_name': row[1],
                'bio': row[2],
                'detected_time': row[3]
            } for row in followings
        ]
        
        return result
    
    except sqlite3.Error as e:
        print(f"查询新增Following列表失败: {str(e)}")
        return []
    
    finally:
        if conn:
            conn.close()

def delete_accounts(accounts):
    """
    从following表中删除指定source_account的所有数据
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 使用参数化查询来防止SQL注入
        placeholders = ','.join(['?' for _ in accounts])
        query = f"""
            DELETE FROM following 
            WHERE source_account IN ({placeholders})
        """
        
        cursor.execute(query, accounts)
        conn.commit()
        
        return {
            'status': 'success',
            'message': f'成功删除 {cursor.rowcount} 条记录'
        }
    
    except sqlite3.Error as e:
        print(f"删除账号数据失败: {str(e)}")
        return {
            'status': 'error',
            'message': f'删除失败: {str(e)}'
        }
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    source_accounts = get_source_accounts()
    print("Source Accounts:")
    for account in source_accounts:
        print(account)
