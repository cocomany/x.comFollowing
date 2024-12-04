import sys
import os
import json
import io
import logging
from twitter_following_crawler import TwitterFollowingCrawler

def read_cookies():
    try:
        with open('config/cookies.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
            # 使用更健壮的方法提取authorization和cookie
            authorization = ''
            cookie = ''
            
            for line in lines:
                line = line.strip()
                if line.startswith('authorization:'):
                    authorization = line.split(':', 1)[1].strip()
                elif line.startswith('cookie:'):
                    cookie = line.split(':', 1)[1].strip()
            
            # 如果没有找到值，抛出异常
            if not authorization or not cookie:
                raise ValueError("未找到有效的authorization或cookie")
            
            return authorization, cookie
    
    except FileNotFoundError:
        print("错误：未找到cookies.txt文件")
        return '', ''
    except Exception as e:
        print(f"读取cookies时发生错误：{e}")
        return '', ''

def main(accounts=None, authorization=None, cookie=None, log_callback=None):
    try:
        # 如果没有传入accounts，从数据库获取
        if accounts is None:
            import query_db
            accounts = query_db.get_source_accounts()
        
        # 确保accounts是列表
        if isinstance(accounts, str):
            accounts = [accounts]
        elif not isinstance(accounts, list):
            error_msg = f"错误：accounts必须是字符串或列表，当前类型为 {type(accounts)}"
            if log_callback:
                log_callback(error_msg)
            return "账号类型错误"
        
        # 如果没有传入authorization和cookie，从文件读取
        if not authorization or not cookie:
            authorization, cookie = read_cookies()
        
        # 再次检查authorization和cookie是否为空
        if not authorization or not cookie:
            error_msg = "错误：未能获取有效的authorization或cookie"
            if log_callback:
                log_callback(error_msg)
            return "未获取到授权信息"
        
        # 记录详细的账号信息
        log_msg = f"开始为以下账号爬取Following: {', '.join(accounts)}"
        if log_callback:
            log_callback(log_msg)
        
        results = []
        for account in accounts:
            log_msg = f"开始爬取账号: {account}"
            if log_callback:
                log_callback(log_msg)
            
            try:
                crawler = TwitterFollowingCrawler(
                    source_account=account,
                    authorization=authorization,
                    cookie=cookie
                )
                crawler.run()
                result = f"账号 {account} 爬取成功"
                results.append(result)
                if log_callback:
                    log_callback(result)
            except Exception as account_error:
                result = f"账号 {account} 爬取失败: {str(account_error)}"
                results.append(result)
                if log_callback:
                    log_callback(result)
        
        return "\n".join(results)
    
    except Exception as e:
        error_msg = f"爬虫执行过程中发生错误：{e}"
        if log_callback:
            log_callback(error_msg)
        return error_msg

def run_crawler(accounts=None, authorization=None, cookie=None):
    """
    对main()函数的包装，以满足模块调用需求
    """
    return main(accounts, authorization, cookie)

if __name__ == "__main__":
    main()
