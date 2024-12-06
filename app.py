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
    
    following_list = query_db.get_following_list(account)
    
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
        logging.info("开始导出Excel文件...")
        days = request.args.get('days', '2')
        days_int = int(days)
        
        # 直接使用 multiple_followed 函数中的逻辑获取数据
        results = get_multiple_followed_accounts(days_int)
        
        if not results:
            logging.warning("没有找到可导出的数据")
            return "No data available for export", 404
        
        logging.info(f"找到 {len(results)} 条记录，开始创建Excel文件...")
        
        # 创建DataFrame，将source accounts列表转换为逗号分隔的字符串
        df = pd.DataFrame(
            [(row[0], row[1], ', '.join(row[2])) for row in results],
            columns=['Following Account', '被关注次数', '关注该账号的Source Accounts']
        )
        
        # 创建Excel文件
        output = BytesIO()
        logging.info("正在写入Excel文件...")
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='多重关注分析', index=False)
            
            # 获取工作表对象
            worksheet = writer.sheets['多重关注分析']
            
            # 调整列宽
            worksheet.set_column('A:A', 20)  # Following Account
            worksheet.set_column('B:B', 15)  # 被关注次数
            worksheet.set_column('C:C', 40)  # Source Accounts
        
        output.seek(0)
        
        # 生成文件名
        filename = f'multiple_followed_analysis_{datetime.now().strftime("%Y%m%d")}.xlsx'
        logging.info(f"Excel文件创建完成: {filename}")
        
        response = send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
        # 添加响应头，禁用缓存
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        logging.info("文件导出成功")
        return response
        
    except Exception as e:
        logging.error(f"导出Excel文件时发生错误: {str(e)}")
        return f"Error exporting data: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
