from flask import Flask, render_template, request, jsonify, Response, send_file, send_from_directory, redirect, url_for, session
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
from functools import wraps
from config.auth_config import ACCESS_PASSWORD

# 在文件开头添加或修改日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

app = Flask(__name__)
app.secret_key = os.urandom(24)  # 设置用于会话的密钥

# 登录验证装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['password'] == ACCESS_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        error = '密码错误'
    return render_template('login.html', error=error)

@app.route('/')
@login_required
def index():
    return render_template('index.html')

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

@app.route('/update_crawler')
@login_required
def update_crawler_page():
    source_accounts = query_db.get_source_accounts()
    default_authorization, default_cookie = read_default_config()
    return render_template('update_crawler.html', 
                           source_accounts=source_accounts, 
                           default_authorization=default_authorization, 
                           default_cookie=default_cookie)

@app.route('/show_following')
@login_required
def show_following():
    source_accounts = query_db.get_source_accounts()
    return render_template('show_following.html', source_accounts=source_accounts)

@app.route('/comparison_report')
@login_required
def comparison_report():
    report = query_db.generate_comparison_report()
    return render_template('comparison_report.html', report=report)


@app.route('/get_following_list', methods=['POST'])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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

def init_scheduler():
    """初始化定时任务调度器"""
    scheduler = TaskScheduler.get_instance()
    if scheduler.is_enabled():
        scheduler.start()

@app.route('/get_new_following_list', methods=['POST'])
@login_required
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

@app.route('/get_latest_log')
@login_required
def get_latest_log():
    """获取最新的任务日志"""
    try:
        logs = get_recent_logs(1)
        if logs:
            latest_log = logs[0]
            try:
                with open(latest_log['path'], 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # 计算进度
                progress = 0
                if '找到' in content and '个源账号' in content:
                    progress = 10
                if '正在爬取账号' in content:
                    import re
                    match = re.search(r'\[(\d+)/(\d+)\]', content)
                    if match:
                        current, total = map(int, match.groups())
                        progress = 10 + (current / total * 80)
                if '任务完成' in content:
                    progress = 100
                elif '任务失败' in content:
                    progress = 100

                return jsonify({
                    'status': 'success',
                    'log': {
                        'filename': latest_log['filename'],
                        'time': latest_log['time'],
                        'log_content': content
                    },
                    'progress': progress
                })
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': f"读取日志文件失败: {str(e)}"
                })
        
        return jsonify({
            'status': 'error',
            'message': '没有找到日志'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/save_accounts', methods=['POST'])
@login_required
def save_accounts():
    try:
        data = request.get_json()
        accounts = data.get('accounts', [])
        
        # 这里添加保存账号的逻辑
        # 例如保存到文数据库
        
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/download_log/<filename>')
@login_required
def download_log(filename):
    """下载日志文件"""
    return send_from_directory('logs', filename, as_attachment=True)

@app.route('/check_task_status')
@login_required
def check_task_status():
    """检查是否有任务正在运行"""
    try:
        logs = get_recent_logs(1)
        if not logs:
            return jsonify({'running': False})
            
        latest_log = logs[0]
        # 检查最新日志文件的修改时间是否在最近5分钟内
        log_time = datetime.strptime(latest_log['time'], '%Y-%m-%d %H:%M:%S')
        now = datetime.now()
        
        # 检查文件最后修改时间
        last_modified = datetime.fromtimestamp(os.path.getmtime(latest_log['path']))
        time_since_modified = now - last_modified
        
        with open(latest_log['path'], 'r', encoding='utf-8') as f:
            content = f.read()
            if '任务完成' in content or '任务失败' in content:
                return jsonify({'running': False})
            
            # 如果日志最后修改时间超过5分钟，标记为可能停止响应
            if time_since_modified > timedelta(minutes=5):
                return jsonify({
                    'running': True,
                    'stalled': True,
                    'last_modified': last_modified.strftime('%Y-%m-%d %H:%M:%S')
                })
                
            return jsonify({
                'running': True,
                'stalled': False
            })
            
    except Exception as e:
        return jsonify({'running': False, 'error': str(e)})

@app.route('/reset_task_status', methods=['POST'])
@login_required
def reset_task_status():
    """强制重置任务状态"""
    try:
        logs = get_recent_logs(1)
        if logs:
            latest_log = logs[0]
            # 在日志末尾添加强制终止标记
            with open(latest_log['path'], 'a', encoding='utf-8') as f:
                f.write('\n[强制重置] 任务状态已被手动重置\n任务完成\n')
        
        return jsonify({
            'status': 'success',
            'message': '任务状态已重置'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/get_task_progress')
@login_required
def get_task_progress():
    """获取当前任务的进度"""
    try:
        logs = get_recent_logs(1)
        if not logs:
            return jsonify({
                'status': 'error',
                'message': '没有找到日志'
            })
            
        latest_log = logs[0]
        with open(latest_log['path'], 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 计算进度
        progress = 0
        status_text = '准备中...'
        completed = False
        
        if '找到' in content and '个源账号' in content:
            progress = 10
            status_text = '已获取源账号列表'
            
        if '正在爬取账号' in content:
            import re
            match = re.search(r'\[(\d+)/(\d+)\]', content)
            if match:
                current, total = map(int, match.groups())
                progress = 10 + (current / total * 80)
                status_text = f'正在爬取 {current}/{total}'
                
        if '任务完成' in content:
            progress = 100
            status_text = '任务已完成'
            completed = True
        elif '任务失败' in content:
            status_text = '任务失败'
            completed = True
            
        return jsonify({
            'status': 'success',
            'progress': progress,
            'log': content,
            'status_text': status_text,
            'completed': completed
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/view_log/<filename>')
@login_required
def view_log(filename):
    """查看日志文件内容"""
    try:
        log_path = os.path.join('logs', filename)
        if not os.path.exists(log_path):
            return jsonify({
                'status': 'error',
                'message': '日志文件不存在'
            })
            
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        return jsonify({
            'status': 'success',
            'content': content
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/get_recent_logs')
@login_required
def get_recent_logs_api():
    """API接口：获取最近的日志文件列表"""
    try:
        logs = get_recent_logs(limit=5)
        return jsonify({
            'status': 'success',
            'logs': logs
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/delete_accounts', methods=['POST'])
@login_required
def delete_accounts():
    """删除选中账号的所有数据"""
    try:
        data = request.json
        accounts = data.get('accounts', [])
        
        if not accounts:
            return jsonify({
                'status': 'error',
                'message': '请选择要删除的账号'
            })
        
        # 调用query_db中的删除函数
        result = query_db.delete_accounts(accounts)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

if __name__ == '__main__':
    init_scheduler()  # 初始化定时任务
    app.run(debug=True)

