// 确保脚本只执行一次
(function() {
    console.log('脚本开始执行');

    let isEventBound = false;

    function bindShowFollowingEvent() {
        // 防止重复绑定
        if (isEventBound) return;
        isEventBound = true;

        // 添加全选功能
        const selectAllCheckbox = document.getElementById('select-all-accounts');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', function() {
                const accountCheckboxes = document.querySelectorAll('.account-checkbox');
                accountCheckboxes.forEach(checkbox => {
                    checkbox.checked = selectAllCheckbox.checked;
                });
            });

            // 监听单个复选框的变化
            const accountCheckboxes = document.querySelectorAll('.account-checkbox');
            accountCheckboxes.forEach(checkbox => {
                checkbox.addEventListener('change', function() {
                    const allChecked = Array.from(accountCheckboxes).every(cb => cb.checked);
                    selectAllCheckbox.checked = allChecked;
                });
            });
        }

        const showFollowingBtn = document.getElementById('show-following-btn');
        const followingList = document.getElementById('following-list');
        const accountCheckboxes = document.querySelectorAll('.account-checkbox');
        const triggerCrawlerBtn = document.getElementById('trigger-crawler-btn');
        const statusMessage = document.getElementById('status-message');
        const crawlerLog = document.getElementById('crawler-log');
        const progressBar = document.getElementById('progress');

        // 触发爬虫事件处理
        if (triggerCrawlerBtn) {
            triggerCrawlerBtn.addEventListener('click', function() {
                // 修改这里：每次点击时重新获取所有复选框
                const accountCheckboxes = document.querySelectorAll('.account-checkbox');
                
                // 获取选中的账号
                const selectedAccounts = Array.from(accountCheckboxes)
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

                // 检查是���已存在
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
                    newAccountDiv.innerHTML = `
                        <input type="checkbox" class="account-checkbox" value="${account}">
                        <span>${account}</span>
                    `;

                    // 添加到列表中
                    accountList.appendChild(newAccountDiv);

                    // 为新添加的复选框添加事件监听
                    const newCheckbox = newAccountDiv.querySelector('.account-checkbox');
                    newCheckbox.addEventListener('change', function() {
                        const allCheckboxes = document.querySelectorAll('.account-checkbox');
                        const selectAllCheckbox = document.getElementById('select-all-accounts');
                        const allChecked = Array.from(allCheckboxes).every(cb => cb.checked);
                        selectAllCheckbox.checked = allChecked;
                    });
                });

                // 清空输入框
                newAccountInput.value = '';
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

    // 尝试绑定事件
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindShowFollowingEvent);
    } else {
        bindShowFollowingEvent();
    }
})();
