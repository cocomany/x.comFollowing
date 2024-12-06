from app import app
from flask import request, render_template
from query_db import get_multiple_followed_accounts

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

@app.route('/multiple_followed', methods=['GET'])
def multiple_followed():
    days_options = [
        {'value': 1, 'label': '最近1天'},
        {'value': 2, 'label': '最近2天'},
        {'value': 7, 'label': '最近7天'},
        {'value': 30, 'label': '最近30天'},
        {'value': 60, 'label': '最近60天'}
    ]
    
    # 获取查询天数参数，默认为2天
    days = request.args.get('days', '2')
    try:
        days = int(days)
    except ValueError:
        days = 2
    
    # 获取数据
    results = get_multiple_followed_accounts(days)
    
    return render_template(
        'multiple_followed.html',
        results=results,
        days_options=days_options,
        selected_days=days
    )
