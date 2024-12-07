Twitter Following Crawler
========================

这是一个用于抓取Twitter(X.com)用户关注列表的爬虫工具。

系统要求
--------
- CentOS 7 或更高版本
- Python 3.7+
- SQLite3

安装步骤
--------

1. 系统依赖安装

# 安装 EPEL 仓库
sudo yum install epel-release -y

# 安装开发工具和 Python3
sudo yum groupinstall "Development Tools" -y
sudo yum install python3 python3-devel python3-pip -y

# 安装 Chromium 和 ChromeDriver
sudo yum install chromium chromium-headless chromedriver -y

# 验证 Chromium 和 ChromeDriver 安装
chromium-browser --version
chromedriver --version

2. 项目设置

# 创建项目目录
mkdir twitter_crawler
cd twitter_crawler

# 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate

# 克隆项目（如果是从git仓库）
git clone <repository_url> .

# 安装 Python 依赖
pip install -r requirements.txt

3. 创建必要的目录

# 创建截图保存目录
mkdir screenshots

4. 设置权限

# 设置目录权限
chmod 755 screenshots

使用方法
--------

1. 激活虚拟环境：
source venv/bin/activate

2. 运行应用：
python app.py

故障排除
--------

1. Chromium 相关问题:

- 如果遇到 Chromium 启动失败:
  # 检查版本是否匹配
  chromium-browser --version
  chromedriver --version
  
  # 确保两者版本号相同或接近

- 权限问题:
  # 检查 chromedriver 权限
  ls -l /usr/bin/chromedriver
  # 如需要，添加执行权限
  sudo chmod +x /usr/bin/chromedriver

2. 常见错误:

- DevToolsActivePort 文件不存在:
  这是正常的，程序已配置使用 --no-sandbox 选项处理此问题

- SSL证书错误:
  程序已配置忽略证书错误，无需额外处理

日志和数据
----------
- 程序日志显示在控制台
- 截图保存在 screenshots 目录
- 数据库文件为 twitter_following.db

注意事项
--------

1. 系统时间同步:
# 检查系统时间
date

# 如果需要，同步时间
sudo yum install chrony -y
sudo systemctl start chronyd
sudo systemctl enable chronyd

2. 内存要求:
- 建议至少有 2GB 可用内存
- 如果内存不足，可调整 scroll_count 参数减少加载量

3. 网络要求:
- 确保服务器可以访问 x.com
- 建议使用代理如果遇到访问限制

维护指南
--------

定期执行以下维护:

1. 更新系统包:
sudo yum update -y

2. 更新 Python 依赖:
pip install --upgrade -r requirements.txt

3. 清理截图(可选):
# 删除30天前的截图
find screenshots/ -type f -mtime +30 -delete

支持
----
如果遇到问题:
1. 检查日志输出
2. 确认 Chromium 和 ChromeDriver 版本匹配
3. 验证网络连接和代理设置
4. 确保 cookies 和 authorization 是最新的 