// 等待DOM加载完成
document.addEventListener('DOMContentLoaded', function() {
    // 获取下载按钮
    const downloadBtn = document.getElementById('downloadBtn');
    
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function() {
            console.log('Download button clicked'); // 添加调试日志
            console.log('Download URL:', window.downloadUrl); // 添加调试日志
            
            fetch(window.downloadUrl, {
                method: 'GET',
                credentials: 'same-origin'  // 包含cookies
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.blob();
            })
            .then(blob => {
                // 创建下载链接
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = `multiple_followed_analysis_${new Date().toISOString().split('T')[0]}.xlsx`;
                
                // 触发下载
                document.body.appendChild(a);
                a.click();
                
                // 清理
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            })
            .catch(error => {
                console.error('下载失败:', error);
                alert('下载失败，请重试');
            });
        });
    } else {
        console.warn('Download button not found'); // 添加调试日志
    }
}); 