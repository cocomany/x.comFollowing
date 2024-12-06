// 确保脚本只执行一次
(function() {
    console.log('脚本开始执行');

    let isEventBound = false;

    function bindShowFollowingEvent() {
        // 检查当前页面是否是 Following 页面
        const showFollowingBtn = document.getElementById('show-following-btn');
        const followingList = document.getElementById('following-list');
        
        // 防止重复绑定
        if (isEventBound) return;
        isEventBound = true;

        // 添加图片浮窗功能 - 这个功能应该在所有页面都可用
        const helpIcons = document.querySelectorAll('.help-icon');
        helpIcons.forEach(icon => {
            if (!icon.querySelector('.image-tooltip')) {
                const tooltip = document.createElement('div');
                tooltip.className = 'image-tooltip';
                const img = document.createElement('img');
                img.src = icon.dataset.tooltipImage;
                img.alt = '帮助说明';
                tooltip.appendChild(img);
                icon.appendChild(tooltip);
            }

            icon.addEventListener('mouseenter', function() {
                const tooltip = this.querySelector('.image-tooltip');
                if (tooltip) {
                    tooltip.style.display = 'block';
                    const rect = tooltip.getBoundingClientRect();
                    if (rect.top < 0) {
                        tooltip.style.bottom = 'auto';
                        tooltip.style.top = '100%';
                    }
                }
            });

            icon.addEventListener('mouseleave', function() {
                const tooltip = this.querySelector('.image-tooltip');
                if (tooltip) {
                    tooltip.style.display = 'none';
                }
            });
        });

        // Following页面特有的功能
        if (showFollowingBtn && followingList) {
            // Following页面的相关代码
            showFollowingBtn.addEventListener('click', function() {
                // 获取选中的账号
                const accountCheckboxes = document.querySelectorAll('.account-checkbox');
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
            });
        }

        // 爬虫页面的功能
        const triggerCrawlerBtn = document.getElementById('trigger-crawler-btn');
        if (triggerCrawlerBtn) {
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

            const statusMessage = document.getElementById('status-message');
            const crawlerLog = document.getElementById('crawler-log');
            const progressBar = document.getElementById('progress');

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
    }

    // 更新Following列表的函数
    function updateFollowingList(account) {
        console.log('获取单个账号Following:', account);
        fetch('/get_following_list', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                account: account
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

    // 尝试绑定事件
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindShowFollowingEvent);
    } else {
        bindShowFollowingEvent();
    }

    // 导出Excel的函数（放在全局作用域）
    window.downloadExcel = function() {
        fetch(downloadUrl, {
            method: 'GET',
            credentials: 'same-origin'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.blob();
        })
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `multiple_followed_analysis_${new Date().toISOString().split('T')[0]}.xlsx`;
            
            document.body.appendChild(a);
            a.click();
            
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        })
        .catch(error => {
            console.error('下载失败:', error);
            alert('下载失败，请重试');
        });
    };
})();
