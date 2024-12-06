function downloadExcel() {
    // 直接在当前窗口下载，不使用新窗口
    fetch(downloadUrl, {
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
} 