# api/index.py
import os
import json
import random
import smtplib
import requests
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, session, render_template
from supabase import create_client, Client
from user_agents import parse
from werkzeug.security import generate_password_hash, check_password_hash

# --- 配置区域 ---
# 在 Vercel 部署时，请在后台 Environment Variables 设置这些值
# 本地测试可以直接把值填在 default='' 引号里，但不要提交给别人看
# api/index.py (修改这两行)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'random_string_for_session')

# SMTP 账号配置：格式为 JSON 字符串
# 例子: '[{"email": "a@163.com", "password": "pass", "smtp": "smtp.163.com"}, ...]'
SMTP_ACCOUNTS_JSON = os.getenv('SMTP_ACCOUNTS', '[]') 

app = Flask(__name__, template_folder='../templates')
app.secret_key = SECRET_KEY

# 初始化 Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 辅助函数 ---

def get_random_smtp():
    """从环境变量加载的账户列表中随机选一个"""
    try:
        accounts = json.loads(SMTP_ACCOUNTS_JSON)
        if not accounts:
            return None
        return random.choice(accounts)
    except:
        return None

def send_email_code(to_email, code):
    """发送验证码逻辑"""
    account = get_random_smtp()
    if not account:
        return False, "未配置SMTP账户"
    
    msg = MIMEText(f"【星际留言板】您的验证码是：{code}，5分钟内有效。", 'plain', 'utf-8')
    msg['Subject'] = '登录验证'
    msg['From'] = account['email']
    msg['To'] = to_email

    try:
        server = smtplib.SMTP_SSL(account['smtp'], 465)
        server.login(account['email'], account['password'])
        server.send_message(msg)
        server.quit()
        return True, "发送成功"
    except Exception as e:
        print(f"Mail Error: {e}")
        return False, str(e)

def get_ip_info(ip):
    """通过 IP 获取地理位置 (使用 ip-api.com 免费接口)"""
    if ip == '127.0.0.1': return "本地 连接"
    try:
        # 这里的 API 有频率限制，生产环境建议加缓存或更换
        url = f"http://ip-api.com/json/{ip}?lang=zh-CN"
        res = requests.get(url, timeout=3).json()
        if res['status'] == 'success':
            return f"{res['country']} {res['regionName']} {res['city']}"
        return "未知 坐标"
    except:
        return "深空 信号"

def get_device_info(user_agent):
    """解析设备型号"""
    ua = parse(user_agent)
    device = ua.device.family
    os_name = ua.os.family
    # 简单优化显示
    if "iPhone" in device:
        return f"{device} ({os_name})"
    if device == "Other":
        return f"{os_name} 设备"
    return f"{device} ({os_name})"

def get_qq_avatar(qq):
    """获取 QQ 头像"""
    if not qq: return None
    return f"https://q1.qlogo.cn/g?b=qq&nk={qq}&s=640"

# --- 路由区域 ---

@app.route('/')
def index():
    """主页：直接渲染模板"""
    return render_template('index.html')

@app.route('/api/send-code', methods=['POST'])
def api_send_code():
    data = request.json
    email = data.get('email')
    if not email: return jsonify({'error': '请输入邮箱'}), 400
    
    # 生成6位验证码
    code = str(random.randint(100000, 999999))
    
    # 存入数据库 (覆盖旧的)
    supabase.table('email_codes').upsert({'email': email, 'code': code}).execute()
    
    success, msg = send_email_code(email, code)
    if success:
        return jsonify({'message': '验证码已发射'})
    else:
        return jsonify({'error': '发送失败，请重试'}), 500

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    email = data.get('email')
    code = data.get('code')
    password = data.get('password')
    qq = data.get('qq') # 可选
    nickname = data.get('nickname', '星际旅行者')

    # 1. 验证验证码
    res = supabase.table('email_codes').select('*').eq('email', email).execute()
    if not res.data or res.data[0]['code'] != code:
        return jsonify({'error': '验证码错误或失效'}), 400
    
    # 2. 检查用户是否已存在
    user_check = supabase.table('app_users').select('id').eq('email', email).execute()
    if user_check.data:
        return jsonify({'error': '该邮箱已注册'}), 400

    # 3. 判定是否为第一个用户 (自动设为 super_admin)
    all_users = supabase.table('app_users').select('id', count='exact').execute()
    role = 'super_admin' if all_users.count == 0 else 'user'

    # 4. 创建用户
    pw_hash = generate_password_hash(password)
    avatar = get_qq_avatar(qq) if qq else None
    
    new_user = {
        'email': email,
        'password_hash': pw_hash,
        'qq_number': qq,
        'nickname': nickname,
        'avatar_url': avatar,
        'role': role
    }
    
    try:
        u_res = supabase.table('app_users').insert(new_user).execute()
        # 注册成功后删除验证码
        supabase.table('email_codes').delete().eq('email', email).execute()
        return jsonify({'message': '注册成功，欢迎登舰'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    res = supabase.table('app_users').select('*').eq('email', email).execute()
    if not res.data:
        return jsonify({'error': '账号不存在'}), 404
    
    user = res.data[0]
    if user.get('is_banned'):
        return jsonify({'error': '账号已被封禁，禁止连接'}), 403

    if check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        session['role'] = user['role']
        session['nickname'] = user['nickname']
        return jsonify({'message': '登录成功', 'user': user})
    else:
        return jsonify({'error': '密码错误'}), 401

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'message': '已断开连接'})

@app.route('/api/messages', methods=['GET'])
def get_messages():
    # 获取消息列表 (倒序)
    res = supabase.table('messages').select('*, app_users(nickname, avatar_url, role, qq_number)').order('created_at', desc=True).limit(50).execute()
    return jsonify(res.data)

@app.route('/api/messages', methods=['POST'])
def post_message():
    data = request.json
    content = data.get('content')
    parent_id = data.get('parent_id') # 回复功能
    
    if not content: return jsonify({'error': '内容为空'}), 400

    # 获取 IP 和 User-Agent
    if request.headers.getlist("X-Forwarded-For"):
        ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        ip = request.remote_addr
        
    ua_string = request.headers.get('User-Agent')
    
    user_id = session.get('user_id')
    is_guest = False
    
    # 游客限制逻辑
    if not user_id:
        is_guest = True
        # 查询该 IP 过去 24 小时的发帖数
        one_day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat()
        count_res = supabase.table('messages').select('id', count='exact').eq('ip_address', ip).gte('created_at', one_day_ago).execute()
        if count_res.count >= 5:
            return jsonify({'error': '游客每日仅限发送 5 条消息，请登录'}), 429

    # 解析信息
    location = get_ip_info(ip)
    device = get_device_info(ua_string)

    payload = {
        'content': content,
        'user_id': user_id,
        'is_guest': is_guest,
        'ip_address': ip,
        'location_info': location,
        'device_model': device,
        'parent_id': parent_id
    }

    try:
        supabase.table('messages').insert(payload).execute()
        return jsonify({'message': '信号已发送'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/messages/<msg_id>', methods=['DELETE'])
def delete_message(msg_id):
    """删除消息 (软删除)"""
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    if not user_id: return jsonify({'error': '未登录'}), 401

    # 获取消息所有者
    msg = supabase.table('messages').select('user_id').eq('id', msg_id).single().execute()
    if not msg.data: return jsonify({'error': '消息不存在'}), 404
    
    # 权限检查: 超管 > 管理 > 自己的消息
    can_delete = False
    if user_role in ['super_admin', 'admin']:
        can_delete = True
    elif str(msg.data['user_id']) == str(user_id):
        can_delete = True # 自己撤回
        
    if can_delete:
        supabase.table('messages').update({'is_deleted': True, 'content': '此条通信已被拦截/撤回'}).eq('id', msg_id).execute()
        return jsonify({'message': '删除成功'})
    else:
        return jsonify({'error': '权限不足'}), 403

@app.route('/api/user/profile', methods=['POST'])
def update_profile():
    """更新资料：绑定QQ/修改密码"""
    user_id = session.get('user_id')
    if not user_id: return jsonify({'error': '未登录'}), 401
    
    data = request.json
    action = data.get('action') # 'bind_qq', 'change_pwd'
    
    if action == 'bind_qq':
        qq = data.get('qq')
        avatar = get_qq_avatar(qq)
        supabase.table('app_users').update({'qq_number': qq, 'avatar_url': avatar}).eq('id', user_id).execute()
        return jsonify({'message': 'QQ 绑定成功'})
        
    if action == 'change_pwd':
        new_pwd = data.get('password')
        pw_hash = generate_password_hash(new_pwd)
        supabase.table('app_users').update({'password_hash': pw_hash}).eq('id', user_id).execute()
        return jsonify({'message': '密码重置成功'})
        
    return jsonify({'error': '未知操作'}), 400

# 必须给 Vercel 暴露 app
# if __name__ == '__main__':
#     app.run(debug=True)
