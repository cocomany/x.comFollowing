// 确保脚本只执行一次
(function() {
    console.log('脚本开始执行');

    let isEventBound = false;

    function bindShowFollowingEvent() {
        // 防止重复绑定
        if (isEventBound) return;
        isEventBound = true;

        // 获取所有DOM元素
        const selectAllCheckbox = document.getElementById('select-all-accounts');
        const accountCheckboxes = document.querySelectorAll('.account-checkbox');
        const showFollowingBtn = document.getElementById('show-following-btn');
        const followingList = document.getElementById('following-list');
        const triggerCrawlerBtn = document.getElementById('trigger-crawler-btn');
        const statusMessage = document.getElementById('status-message');
        const crawlerLog = document.getElementById('crawler-log');
        const progressBar = document.getElementById('progress');

        // 添加全选功能
        if (selectAllCheckbox) {
            // 监听全选复选框的变化
            selectAllCheckbox.addEventListener('change', function() {
                accountCheckboxes.forEach(checkbox => {
                    checkbox.checked = selectAllCheckbox.checked;
                });
            });

            // 监听单个复选框的变化
            accountCheckboxes.forEach(checkbox => {
                checkbox.addEventListener('change', function() {
                    const allChecked = Array.from(accountCheckboxes).every(cb => cb.checked);
                    selectAllCheckbox.checked = allChecked;
                });
            });
        }

        // 触发爬虫事件处理
        if (triggerCrawlerBtn) {
            triggerCrawlerBtn.addEventListener('click', function() {
                // 修改获取选中账号的方式，使用最新的DOM元素
                const selectedAccounts = Array.from(document.querySelectorAll('.account-checkbox'))
                    .filter(checkbox => checkbox.checked)
                    .map(checkbox => checkbox.value);

                // 获取授权和 Cookie 信息
                const authorization = document.getElementById('authorization-input').value;
                const cookie = document.getElementById('cookie-input').value;

                if (selectedAccounts.length === 0) {
                    statusMessage.textContent = '请至少选择一个账号';
                    statusMessage.style.color = 'red';
                    return;
                }

                // 重置状态
                statusMessage.textContent = '开始爬取...不要关闭或刷新页面，等两三分钟';
                statusMessage.style.color = 'blue';
                crawlerLog.value = '';
                progressBar.style.width = '0%';

                // 发送爬虫请求
                fetch('/trigger_crawler', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        accounts: selectedAccounts,
                        authorization: authorization,
                        cookie: cookie
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        // 开始监听SSE事件
                        const eventSource = new EventSource('/log_stream');
                        
                        eventSource.onmessage = function(event) {
                            const logMessage = event.data;
                            if (logMessage === 'null') {
                                // 爬虫完成，关闭SSE连接
                                eventSource.close();
                                statusMessage.textContent = '爬取完成';
                                statusMessage.style.color = 'green';
                                progressBar.style.width = '100%';
                            } else {
                                // 解析JSON消息
                                const message = JSON.parse(logMessage);
                                // 更新日志显示
                                crawlerLog.value += message + '\n';
                                crawlerLog.scrollTop = crawlerLog.scrollHeight;
                                
                                // 根据日志内容更新状态
                                if (message.includes('验证成功')) {
                                    progressBar.style.width = '30%';
                                } else if (message.includes('开始滚动页面')) {
                                    progressBar.style.width = '50%';
                                } else if (message.includes('找到账号')) {
                                    progressBar.style.width = '70%';
                                }
                            }
                        };
                        
                        eventSource.onerror = function(error) {
                            console.error('SSE错误:', error);
                            eventSource.close();
                            statusMessage.textContent = '爬取过程中断';
                            statusMessage.style.color = 'red';
                        };
                        
                    } else {
                        statusMessage.textContent = '爬取失败：' + (data.message || '未知错误');
                        statusMessage.style.color = 'red';
                        crawlerLog.value = data.log || '';
                    }
                })
                .catch(error => {
                    console.error('爬虫触发错误:', error);
                    statusMessage.textContent = '爬取发生错误：' + error.message;
                    statusMessage.style.color = 'red';
                });
            });
        }

        if (showFollowingBtn && followingList) {
            showFollowingBtn.addEventListener('click', function() {
                const selectedAccounts = Array.from(accountCheckboxes)
                    .filter(checkbox => checkbox.checked)
                    .map(checkbox => checkbox.value);

                console.log('选中的账号:', selectedAccounts);

                if (selectedAccounts.length === 0) {
                    followingList.innerHTML = '<p>请至少选择一个账号</p>';
                    return;
                }

                if (selectedAccounts.length === 1) {
                    updateFollowingList(selectedAccounts[0]);
                } else {
                    updateCommonFollowingList(selectedAccounts);
                }
                
                updateNewFollowingLists(selectedAccounts);
            });
        } else {
            console.error('未找到显示Following按钮或Following列表');
        }

        // 添加新账号功能
        const addAccountBtn = document.getElementById('add-account-btn');
        const newAccountInput = document.getElementById('new-account-input');
        const accountList = document.getElementById('account-list');

        if (addAccountBtn && newAccountInput && accountList) {
            addAccountBtn.addEventListener('click', function() {
                const accountsStr = newAccountInput.value.trim();
                
                if (!accountsStr) {
                    alert('请输入账号名');
                    return;
                }

                // 将输入按逗号分隔，处理每个账号
                const newAccounts = accountsStr.split(',')
                    .map(account => account.trim().toLowerCase())
                    .filter(account => account); // 过滤掉空字符串

                if (newAccounts.length === 0) {
                    alert('请输入有效账号');
                    return;
                }

                // 检查是否已存在
                const existingAccounts = Array.from(accountList.querySelectorAll('.account-item span'))
                    .map(span => span.textContent.trim().toLowerCase());

                // 过滤掉已存在的账号
                const accountsToAdd = newAccounts.filter(account => !existingAccounts.includes(account));

                if (accountsToAdd.length === 0) {
                    alert('所有账号都已存在');
                    return;
                }

                // 添加新账号到列表
                accountsToAdd.forEach(account => {
                    const newAccountDiv = document.createElement('div');
                    newAccountDiv.className = 'account-item';
                    newAccountDiv.dataset.account = account;
                    
                    // 确保新的复选框有正确的class和value属性
                    newAccountDiv.innerHTML = `
                        <input type="checkbox" class="account-checkbox" value="${account}">
                        <span>${account}</span>
                    `;

                    // 添加到列表中
                    accountList.appendChild(newAccountDiv);

                    // 为新添加的复选框添加事件监听
                    const newCheckbox = newAccountDiv.querySelector('.account-checkbox');
                    newCheckbox.addEventListener('change', function() {
                        // 更新全选状态
                        const allCheckboxes = document.querySelectorAll('.account-checkbox');
                        const selectAllCheckbox = document.getElementById('select-all-accounts');
                        const allChecked = Array.from(allCheckboxes).every(cb => cb.checked);
                        selectAllCheckbox.checked = allChecked;
                    });
                });

                // 清空输入框
                newAccountInput.value = '';

                // 保存新账号到服务器（如果需要的话）
                fetch('/save_accounts', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        accounts: accountsToAdd
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status !== 'success') {
                        console.error('保存账号失败:', data.message);
                    }
                })
                .catch(error => {
                    console.error('保存账号错误:', error);
                });
            });

            // 添加回车键支持
            newAccountInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    addAccountBtn.click();
                }
            });
        }

        const timeFilter = document.getElementById('time-filter');
        if (timeFilter) {
            timeFilter.addEventListener('change', function() {
                const selectedAccounts = Array.from(accountCheckboxes)
                    .filter(checkbox => checkbox.checked)
                    .map(checkbox => checkbox.value);

                if (selectedAccounts.length === 1) {
                    updateFollowingList(selectedAccounts[0]);
                } else if (selectedAccounts.length > 1) {
                    updateCommonFollowingList(selectedAccounts);
                }
            });
        }
    }

    // 更新Following列表的函数
    function updateFollowingList(account) {
        console.log('获取单个账号Following:', account);
        const timeFilter = document.getElementById('time-filter').value;
        
        fetch('/get_following_list', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                account: account,
                days: parseInt(timeFilter)
            })
        })
        .then(response => {
            console.log('响应状态:', response.status, response.ok);
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            console.log('Following列表数据:', data);
            const followingList = document.getElementById('following-list');
            if (data.status === 'success') {
                followingList.innerHTML = '';

                const table = document.createElement('table');
                table.innerHTML = `
                    <thead>
                        <tr>
                            <th>账号</th>
                            <th>显示名称</th>
                            <th>简介</th>
                            <th>检测时间</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                `;
                const tbody = table.querySelector('tbody');

                data.following_list.forEach(following => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${following.following_account}</td>
                        <td>${following.display_name || '无'}</td>
                        <td>${following.bio || '无'}</td>
                        <td>${following.detected_time}</td>
                    `;
                    tbody.appendChild(row);
                });

                followingList.appendChild(table);
            } else {
                console.error('获取Following列表失败:', data.message);
                followingList.innerHTML = `<p>获取Following列表失败: ${data.message}</p>`;
            }
        })
        .catch(error => {
            console.error('获取Following列表错误:', error);
            const followingList = document.getElementById('following-list');
            followingList.innerHTML = `<p>获取Following列表时发生错误: ${error.message}</p>`;
        });
    }

    // 更新Common Following列表的函数
    function updateCommonFollowingList(accounts) {
        console.log('获取共同Following:', accounts);
        fetch('/get_common_following', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                accounts: accounts
            })
        })
        .then(response => {
            console.log('响应状态:', response.status, response.ok);
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            console.log('共同Following数据:', data);
            const followingList = document.getElementById('following-list');
            if (data.status === 'success') {
                followingList.innerHTML = '';

                const table = document.createElement('table');
                table.innerHTML = `
                    <thead>
                        <tr>
                            <th>账号</th>
                            <th>显示名称</th>
                            <th>简介</th>
                            <th>检测时间</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                `;
                const tbody = table.querySelector('tbody');

                data.common_following_list.forEach(following => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${following.following_account}</td>
                        <td>${following.display_name || '无'}</td>
                        <td>${following.bio || '无'}</td>
                        <td>${following.detected_time}</td>
                    `;
                    tbody.appendChild(row);
                });

                followingList.appendChild(table);
            } else {
                console.error('获取共同关注列表失败:', data.message);
                followingList.innerHTML = `<p>获取共同关注列表失败: ${data.message}</p>`;
            }
        })
        .catch(error => {
            console.error('获取共同关注列表错误:', error);
            const followingList = document.getElementById('following-list');
            followingList.innerHTML = `<p>获取共同关注列表时发生错误: ${error.message}</p>`;
        });
    }

    function updateNewFollowingLists(accounts) {
        const timeFilter = document.getElementById('time-filter').value;
        
        fetch('/get_new_following_list', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                accounts: accounts,
                days: parseInt(timeFilter)
            })
        })
        .then(response => response.json())
        .then(data => {
            const newFollowingList = document.getElementById('new-following-list');
            if (data.status === 'success') {
                newFollowingList.innerHTML = '';
                
                Object.entries(data.new_following_lists).forEach(([account, followings]) => {
                    const accountSection = document.createElement('div');
                    accountSection.className = 'account-section';
                    
                    const accountHeader = document.createElement('h3');
                    accountHeader.textContent = `${account} 的新增Following`;
                    accountSection.appendChild(accountHeader);
                    
                    if (followings.length === 0) {
                        const noData = document.createElement('p');
                        noData.textContent = '该时间范围内无新增Following';
                        accountSection.appendChild(noData);
                    } else {
                        const table = document.createElement('table');
                        table.innerHTML = `
                            <thead>
                                <tr>
                                    <th>账号</th>
                                    <th>显示名称</th>
                                    <th>简介</th>
                                    <th>检测时间</th>
                                </tr>
                            </thead>
                            <tbody></tbody>
                        `;
                        
                        const tbody = table.querySelector('tbody');
                        followings.forEach(following => {
                            const row = document.createElement('tr');
                            row.innerHTML = `
                                <td>${following.following_account}</td>
                                <td>${following.display_name || '无'}</td>
                                <td>${following.bio || '无'}</td>
                                <td>${following.detected_time}</td>
                            `;
                            tbody.appendChild(row);
                        });
                        
                        accountSection.appendChild(table);
                    }
                    
                    newFollowingList.appendChild(accountSection);
                });
            }
        })
        .catch(error => {
            console.error('获取新增Following列表错误:', error);
            const newFollowingList = document.getElementById('new-following-list');
            newFollowingList.innerHTML = `<p>获取新增Following列表时发生错误: ${error.message}</p>`;
        });
    }

    function runNow() {
        if (!confirm('确定要立即执行一次任务吗？')) {
            return;
        }
        
        fetch('/run_task_now', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // 清空并显示日志区域
                const logTextarea = document.getElementById('crawler-log');
                logTextarea.value = '';
                document.getElementById('current-task-status').style.display = 'block';
                document.getElementById('status-message').textContent = '正在启动任务...';
                document.getElementById('progress').style.width = '0%';
                
                // 开始定期检查任务状态
                checkTaskStatus();
            } else {
                alert('执行失败: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('执行失败，请查看控制台获取详细信息');
        });
    }

    function checkTaskStatus() {
        const statusDiv = document.getElementById('current-task-status');
        const statusMessage = document.getElementById('status-message');
        const progressBar = document.getElementById('progress');
        const logTextarea = document.getElementById('crawler-log');
        let lastLogContent = '';
        let lastStatus = '';

        // 显示状态区域
        statusDiv.style.display = 'block';
        
        // 每1秒检查一次任务状态
        const intervalId = setInterval(() => {
            fetch('/get_latest_log')
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        const log = data.log;
                        
                        // 更新进度条
                        progressBar.style.width = `${data.progress}%`;
                        
                        // 更新状态消息
                        let statusText = '正在运行';
                        let statusClass = 'status-running';
                        
                        if (log.status === 'completed') {
                            statusText = '已完成';
                            statusClass = 'status-completed';
                        } else if (log.status === 'failed') {
                            statusText = '失败';
                            statusClass = 'status-failed';
                        }
                        
                        // 如果状态发生变化，添加视觉提示
                        if (lastStatus !== log.status) {
                            statusMessage.className = statusClass;
                            if (log.status === 'completed' || log.status === 'failed') {
                                // 播放提示音（可选）
                                const audio = new Audio('/static/notification.mp3');
                                audio.play().catch(() => {});
                                
                                // 显示通知
                                if (Notification.permission === "granted") {
                                    new Notification("任务状态更新", {
                                        body: `任务${statusText}`,
                                        icon: "/static/favicon.ico"
                                    });
                                }
                            }
                            lastStatus = log.status;
                        }
                        
                        statusMessage.textContent = `状态: ${statusText} (${Math.round(data.progress)}%)`;
                        
                        // 更新日志内容
                        if (log.log_content && log.log_content !== lastLogContent) {
                            logTextarea.value = log.log_content;
                            logTextarea.scrollTop = logTextarea.scrollHeight;
                            lastLogContent = log.log_content;
                        }
                        
                        // 如果任务已完成或失败，停止检查
                        if (log.status !== 'running') {
                            clearInterval(intervalId);
                            // 等待5秒后刷新页面
                            setTimeout(() => {
                                location.reload();
                            }, 5000);
                        }
                    } else {
                        console.error('获取日志失败:', data.message);
                    }
                })
                .catch(error => {
                    console.error('检查任务状态失败:', error);
                    clearInterval(intervalId);
                });
        }, 1000);
        
        // 设置最长检查时间为10分钟
        setTimeout(() => {
            clearInterval(intervalId);
            location.reload();
        }, 600000);
    }

    // 在页面加载时请求通知权限
    document.addEventListener('DOMContentLoaded', function() {
        if (Notification.permission !== "granted" && Notification.permission !== "denied") {
            Notification.requestPermission();
        }
    });

    // 尝试绑定事件
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindShowFollowingEvent);
    } else {
        bindShowFollowingEvent();
    }
})();
