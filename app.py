from flask import Flask, render_template, request, jsonify, Response, send_file
import sqlite3
import os
import json
from twitter_following_crawler import TwitterFollowingCrawler
import run_crawler
import query_db
import logging
import queue
import threading
from query_db import get_multiple_followed_accounts
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
from task_scheduler import TaskScheduler, get_recent_logs

# 在文件开头添加或修改日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

app = Flask(__name__)

# 创建一个线程安全的日志队列
log_queue = queue.Queue()

def get_db_connection():
    """创建数据库连接"""
    conn = sqlite3.connect('twitter_following.db')
    conn.row_factory = sqlite3.Row
    return conn

def read_default_config():
    try:
        with open('config/cookies.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
            authorization = lines[0].strip() if lines else ''
            cookie = lines[1].strip() if len(lines) > 1 else ''
        return authorization, cookie
    except Exception as e:
        print(f"读取配置文件错误: {e}")
        return '', ''

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/update_crawler')
def update_crawler_page():
    source_accounts = query_db.get_source_accounts()
    default_authorization, default_cookie = read_default_config()
    return render_template('update_crawler.html', 
                           source_accounts=source_accounts, 
                           default_authorization=default_authorization, 
                           default_cookie=default_cookie)

@app.route('/show_following')
def show_following():
    source_accounts = query_db.get_source_accounts()
    return render_template('show_following.html', source_accounts=source_accounts)

@app.route('/comparison_report')
def comparison_report():
    report = query_db.generate_comparison_report()
    return render_template('comparison_report.html', report=report)


@app.route('/get_following_list', methods=['POST'])
def get_following_list():
    data = request.json
    account = data.get('account')
    days = data.get('days')  # 获取天数参数
    
    following_list = query_db.get_following_list(account, days)
    
    return jsonify({
        'status': 'success',
        'following_list': following_list
    })

@app.route('/get_common_following', methods=['POST'])
def get_common_following():
    data = request.json
    accounts = data.get('accounts', [])
    
    if not accounts or len(accounts) < 2:
        return jsonify({
            'status': 'error',
            'message': '请选择至少两个账号'
        })
    
    common_following_list = query_db.get_common_following(accounts)
    
    return jsonify({
        'status': 'success',
        'common_following_list': common_following_list
    })

def custom_log_handler(message):
    """自定义日志处理器，将日志放入队列"""
    # 直接放入消息，不进行JSON编码
    log_queue.put(message)

@app.route('/log_stream')
def log_stream():
    """服务器发送事件(SSE)日志流"""
    def generate():
        while True:
            message = log_queue.get()
            if message is None:  # 结束信号
                yield 'data: null\n\n'
                break
            # 在这里进行一次性JSON编码
            yield f'data: {json.dumps(message)}\n\n'
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/trigger_crawler', methods=['POST'])
def trigger_crawler():
    try:
        data = request.json
        accounts = data.get('accounts', [])
        authorization = data.get('authorization', '')
        cookie = data.get('cookie', '')

        if not accounts:
            return jsonify({
                'status': 'error',
                'message': '请选择至少一个账号'
            })

        # 保存授权信息到配置文件
        try:
            with open('config/cookies.txt', 'w', encoding='utf-8') as f:
                f.write(f"{authorization}\n{cookie}")
        except Exception as e:
            print(f"保存配置文件错误: {e}")

        # 清空之前的日志队列
        while not log_queue.empty():
            try:
                log_queue.get_nowait()
            except queue.Empty:
                break

        # 执行爬虫
        def run_crawler_thread():
            try:
                run_crawler.main(
                    accounts=accounts, 
                    authorization=authorization, 
                    cookie=cookie,
                    log_callback=custom_log_handler
                )
            except Exception as e:
                error_msg = f"爬虫执行失败: {str(e)}"
                custom_log_handler(error_msg)
            finally:
                log_queue.put(None)  # 发送结束信号

        # 启动异步线程执行爬虫
        threading.Thread(target=run_crawler_thread, daemon=True).start()

        return jsonify({
            'status': 'success',
            'message': '爬虫已启动，正在实时输出日志'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/multiple_followed')
def multiple_followed():
    days_options = [
        {'value': 1, 'label': '最近1天'},
        {'value': 2, 'label': '最近2天'},
        {'value': 7, 'label': '最近7天'},
        {'value': 30, 'label': '最近30天'},
        {'value': 60, 'label': '最近60天'}
    ]
    
    days = request.args.get('days', '2')
    try:
        days = int(days)
    except ValueError:
        days = 2
    
    results = get_multiple_followed_accounts(days)
    
    return render_template(
        'multiple_followed.html',
        results=results,
        days_options=days_options,
        selected_days=days
    )

@app.route('/export_multiple_followed')
def export_multiple_followed():
    try:
        days = request.args.get('days', default=7, type=int)
        
        # 使用已存在的函数获取数据
        results = get_multiple_followed_accounts(days)  
        
        if not results:
            return "No data available for export", 404
        
        # 转换数据格式为DataFrame
        data = []
        for result in results:
            following_account = result[0]
            follow_count = result[1]
            source_accounts = ', '.join(result[2])  # 将source accounts列表转换为逗号分隔的字符串
            data.append({
                'Following Account': following_account,
                '被关注次数': follow_count,
                '关注该账号的Source Accounts': source_accounts
            })
        
        df = pd.DataFrame(data)
        
        # 创建一个字节流
        output = BytesIO()
        
        # 将DataFrame写入Excel
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='多重关注分析')
            
            # 获取xlsxwriter工作簿和工作表对象
            workbook = writer.book
            worksheet = writer.sheets['多重关注分析']
            
            # 设置列宽
            worksheet.set_column('A:A', 20)  # Following Account
            worksheet.set_column('B:B', 15)  # 被关注次数
            worksheet.set_column('C:C', 50)  # Source Accounts
        
        # 重置指针到开始位置
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'multiple_followed_analysis_{datetime.now().strftime("%Y%m%d")}.xlsx'
        )
    except Exception as e:
        logging.error(f"导出Excel文件时发生错误: {str(e)}")
        return f"Error exporting data: {str(e)}", 500

@app.route('/schedule_tasks')
def schedule_tasks():
    """定时任务管理页面"""
    scheduler = TaskScheduler.get_instance()
    recent_logs = get_recent_logs(limit=5)
    schedule = scheduler.get_schedule()
    return render_template('schedule_tasks.html',
                         task_enabled=scheduler.is_enabled(),
                         recent_logs=recent_logs,
                         schedule=schedule)

@app.route('/toggle_schedule_task', methods=['POST'])
def toggle_schedule_task():
    """切换定时任务状态"""
    try:
        scheduler = TaskScheduler.get_instance()
        if scheduler.is_enabled():
            scheduler.stop()
        else:
            scheduler.start()
        
        return jsonify({
            'status': 'success',
            'enabled': scheduler.is_enabled(),
            'message': '任务已' + ('启用' if scheduler.is_enabled() else '禁用'),
            'schedule': scheduler.get_schedule()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/update_schedule', methods=['POST'])
def update_schedule():
    """更新定时任务时间"""
    try:
        data = request.json
        hour = int(data.get('hour', 8))
        minute = int(data.get('minute', 0))
        
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("无效的时间值")
        
        scheduler = TaskScheduler.get_instance()
        scheduler.update_schedule(hour, minute)
        
        return jsonify({
            'status': 'success',
            'message': f'定时任务已更新为每天 {hour:02d}:{minute:02d}',
            'schedule': scheduler.get_schedule()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/run_task_now', methods=['POST'])
def run_task_now():
    """立即执行任务"""
    try:
        scheduler = TaskScheduler.get_instance()
        scheduler.run_now()
        return jsonify({
            'status': 'success',
            'message': '任务已开始执行'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

def get_recent_logs(limit=5):
    """获近的任务日志"""
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

def init_scheduler():
    """初始化定时任务调度器"""
    scheduler = TaskScheduler.get_instance()
    if scheduler.is_enabled():
        scheduler.start()

@app.route('/get_new_following_list', methods=['POST'])
def get_new_following_list():
    data = request.json
    accounts = data.get('accounts', [])
    days = data.get('days')
    
    result = {}
    for account in accounts:
        result[account] = query_db.get_new_following_list(account, days)
    
    return jsonify({
        'status': 'success',
        'new_following_lists': result
    })

@app.route('/check_task_status')
def check_task_status():
    """检查最近任务的状态"""
    try:
        recent_log = get_recent_logs(1)[0]
        return jsonify({
            'status': recent_log['status']
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/get_latest_log')
def get_latest_log():
    """获取最新的任务日志"""
    try:
        logs = get_recent_logs(1)
        if logs:
            latest_log = logs[0]
            
            # 如果有对应的日志文件，直接读取
            log_dir = 'logs'
            if os.path.exists(log_dir):
                # 查找最新的日志文件
                log_files = [f for f in os.listdir(log_dir) if f.startswith(f'task_{latest_log["id"]}_')]
                if log_files:
                    latest_file = sorted(log_files)[-1]
                    log_path = os.path.join(log_dir, latest_file)
                    try:
                        with open(log_path, 'r', encoding='utf-8') as f:
                            # 读取文件内容并更新到 latest_log
                            latest_log['log_content'] = f.read()
                            
                            # 同时更新数据库中的日志内容
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute('''
                                UPDATE task_logs 
                                SET log_content = ? 
                                WHERE id = ?
                            ''', (latest_log['log_content'], latest_log['id']))
                            conn.commit()
                            conn.close()
                    except Exception as e:
                        print(f"Error reading log file: {str(e)}")
                        return jsonify({
                            'status': 'error',
                            'message': f"读取日志文件失败: {str(e)}"
                        })
            
            # 计算进度
            progress = 0
            if latest_log['status'] == TaskScheduler.STATUS_RUNNING:
                content = latest_log['log_content']
                if '找到' in content and '个源账号' in content:
                    progress = 10
                if '正在爬取账号' in content:
                    # 从日志内容中提取当前正在处理的账号序号
                    import re
                    match = re.search(r'\[(\d+)/(\d+)\]', content)
                    if match:
                        current, total = map(int, match.groups())
                        progress = 10 + (current / total * 80)  # 给爬取过程分配80%的进度
                if '成功爬取账号' in content:
                    # 计算已完成账号数占总数的比例
                    total_accounts = len(latest_log['affected_accounts'].split(',')) if latest_log['affected_accounts'] else 0
                    completed_accounts = content.count('成功爬取账号')
                    if total_accounts > 0:
                        progress = min(90, 10 + (completed_accounts / total_accounts * 80))
                if '任务完成' in content:
                    progress = 100
                elif '任务失败' in content:
                    progress = 100
            elif latest_log['status'] in [TaskScheduler.STATUS_COMPLETED, TaskScheduler.STATUS_FAILED]:
                progress = 100

            return jsonify({
                'status': 'success',
                'log': latest_log,
                'progress': progress
            })
            
        return jsonify({
            'status': 'error',
            'message': '没有找到日志'
        })
    except Exception as e:
        print(f"Error in get_latest_log: {str(e)}")  # 添加调试日志
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/save_accounts', methods=['POST'])
def save_accounts():
    try:
        data = request.get_json()
        accounts = data.get('accounts', [])
        
        # 这里添加保存账号的逻辑
        # 例如保存到文件或数据库
        
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    init_scheduler()  # 初始化定时任务
    app.run(debug=True)
