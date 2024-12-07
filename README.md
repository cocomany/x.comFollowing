# X.com Following Crawler & Analyzer

这是一个用于抓取和分析X.com(Twitter)用户关注列表的Web应用程序。它可以帮助你追踪特定账号的关注列表，并进行数据分析。

## 功能特点

- 抓取指定X.com账号的关注列表
- 分析多个账号的共同关注
- 生成关注者数据报告
- 支持导出数据为Excel格式
- 实时日志显示爬虫运行状态
- 简洁的Web界面

## 系统要求

- Python 3.8+
- Chrome浏览器（用于Selenium爬虫）
- Windows/Linux/MacOS

### 必需的系统组件

1. **Chrome浏览器**
   - 安装最新版本的Google Chrome浏览器
   - ChromeDriver会通过webdriver_manager自动安装，无需手动下载

2. **Python包依赖**
   - Selenium 4.18.1（用于网页爬虫）
   - BeautifulSoup4 4.12.3（用于解析HTML）
   - Flask 3.0.0（Web服务器）
   - Flask-CORS 4.0.0（跨域支持）
   - pandas（用于Excel导出功能）
   - xlsxwriter（用于Excel文件生成）

3. **系统权限要求**
   - 需要文件系统写入权限（用于保存数据库和截图）
   - 需要网络访问权限
   - Chrome浏览器需要适当的执行权限

## 安装步骤

1. 克隆项目到本地：
```bash
git clone [项目地址]
cd x.comFollowing
```

2. 安装所有依赖：
```bash
pip install -r requirements.txt
```

3. 确保系统环境：
   - 检查Chrome浏览器是否正确安装
   - 确保Python环境变量已正确配置
   - 验证pip是否可用

4. 配置Cookie信息：
   - 在`config`目录下创建`cookies.txt`文件
   - 第一行填写Authorization值
   - 第二行填写Cookie值
   
   获取方法：
   1. 登录X.com
   2. 打开开发者工具(F12)
   3. 在Network标签页中找到任意请求
   4. 在请求头中复制Authorization和Cookie值

5. 创建必要的目录：
```bash
mkdir -p screenshots
mkdir -p config
```

## CentOS环境配置指南

### 1. 安装Python环境

1. 安装Python 3.8及相关工具：
```bash
# 安装EPEL仓库
sudo yum install -y epel-release

# 安装开发工具组
sudo yum groupinstall -y "Development Tools"

# 安装Python 3.8的依赖
sudo yum install -y openssl-devel bzip2-devel libffi-devel xz-devel

# 下载并安装Python 3.8
wget https://www.python.org/ftp/python/3.8.12/Python-3.8.12.tgz
tar xzf Python-3.8.12.tgz
cd Python-3.8.12
./configure --enable-optimizations
sudo make altinstall

# 验证Python安装
python3.8 --version
```

2. 配置Python环境变量：
```bash
# 编辑环境变量文件
sudo vi /etc/profile.d/python.sh

# 添加以下内容
export PATH="/usr/local/bin:$PATH"
export PYTHONPATH="/usr/local/lib/python3.8/site-packages:$PYTHONPATH"

# 使环境变量生效
source /etc/profile.d/python.sh
```

### 2. 安装Chrome浏览器

1. 添加Chrome仓库：
```bash
sudo vi /etc/yum.repos.d/google-chrome.repo
```

添加以下内容：
```
[google-chrome]
name=google-chrome
baseurl=http://dl.google.com/linux/chrome/rpm/stable/$basearch
enabled=1
gpgcheck=1
gpgkey=https://dl-ssl.google.com/linux/linux_signing_key.pub
```

2. 安装Chrome：
```bash
sudo yum install -y google-chrome-stable
```

3. 验证Chrome安装：
```bash
google-chrome --version
```

### 3. 安装其他必需的系统依赖

```bash
# 安装字体
sudo yum install -y liberation-fonts

# 安装必要的系统库
sudo yum install -y libX11 libXcomposite libXcursor libXdamage \
                    libXext libXi libXtst cups-libs libXrandr libXss \
                    libXScrnSaver pango at-spi2-atk gtk3 libdrm \
                    libgbm alsa-lib pulseaudio-libs

# 如果是最小化安装的CentOS，还需要安装以下包
sudo yum install -y xorg-x11-server-Xvfb
```

### 4. 验证环境配置

1. 验证Python配置：
```bash
# 检查Python版本
python3.8 --version

# 检查pip是否可用
python3.8 -m pip --version

# 检查Python环境变量
echo $PYTHONPATH
```

2. 验证Chrome配置：
```bash
# 检查Chrome版本
google-chrome --version

# 测试Chrome无头模式
google-chrome --headless --dump-dom https://www.google.com

# 如果出现错误，检查Chrome是否能以无头模式运行
google-chrome --headless --no-sandbox --disable-dev-shm-usage \
             --dump-dom https://www.google.com
```

### 5. 常见问题解决

1. 如果遇到Chrome启动失败：
```bash
# 添加必要的权限
sudo chmod 1777 /dev/shm
sudo sysctl -w kernel.unprivileged_userns_clone=1

# 如果使用非root用户运行，需要添加以下配置
sudo usermod -a -G chrome,video $USER
```

2. 如果遇到共享内存问题：
```bash
# 编辑系统限制
sudo vi /etc/security/limits.conf

# 添加以下行
* soft memlock unlimited
* hard memlock unlimited
```

3. SELinux相关问题：
```bash
# 如果遇到SELinux阻止Chrome运行，可以临时关闭SELinux
sudo setenforce 0

# 或者添加适当的SELinux规则
sudo setsebool -P httpd_can_network_connect 1
```

## 数据库初始化

首次运行需要初始化数据库：
```bash
python reset_db.py
```

## 运行应用

启动Web服务器：
```bash
python run.py
```

启动后访问：`http://localhost:5000`

## 使用说明

1. **添加待追踪账号**
   - 在首页的"配置爬虫"标签页中添加要追踪的X.com账号
   - 点击"开始爬取"按钮开始收集数据
   - 可以实时查看爬虫运行日志

2. **查看关注列表**
   - 在"查看关注"标签页中可以查看已爬取账号的关注列表
   - 支持按时间筛选查看不同时期的关注数据

3. **分析共同关注**
   - 在"共同关注"标签页中选择多个账号
   - 系统会自动分析并显示这些账号的共同关注者
   - 可以导出分析结果为Excel文件

4. **数据导出**
   - 支持导出多种格式的数据报告
   - 导出的Excel文件包含详细的关注者信息

## 注意事项

1. 请确保`config/cookies.txt`中的认证信息是最新的
2. 爬虫运行时请保持网络连接稳定
3. 建议定期备份`twitter_following.db`数据库文件
4. 如遇到验证码或登录问题，请更新Cookie信息

## 故障排除

1. 如果爬虫无法正常工作：
   - 检查网络连接
   - 更新Cookie信息
   - 检查Chrome浏览器版本是否兼容

2. 如果数据库访问出错：
   - 确保有数据库的写入权限
   - 可以尝试重新初始化数据库

## 技术栈

- 后端：Flask
- 数据库：SQLite
- 爬虫：Selenium + BeautifulSoup4
- 前端：HTML + JavaScript

## 许可证

[MIT]
