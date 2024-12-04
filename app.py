from flask import Flask, render_template, request, jsonify, Response
import sqlite3
import os
import json
from twitter_following_crawler import TwitterFollowingCrawler
import run_crawler
import query_db
import logging
import queue
import threading

app = Flask(__name__)

# 创建一个线程安全的日志队列
log_queue = queue.Queue()

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

if __name__ == '__main__':
    app.run(debug=True)
