# Star Log | 星际留言板 🚀

一个基于 **Python (Flask)** + **Supabase** 的无服务架构（Serverless）留言板系统，专为 **Vercel** 部署设计。
拥有赛博朋克/科幻风格 UI，支持多邮箱轮询验证、QQ 绑定、IP 归属地显示及设备型号识别。

## ✨ 特性 (Features)

* **📡 无服务架构**: 后端逻辑单一 Python 文件 (`api/index.py`)，完美适配 Vercel Serverless Function。
* **🎨 科幻 UI**: 霓虹配色、全息玻璃质感、CSS 动画、响应式设计。
* **🛡️ 安全验证**:
    * 支持多 SMTP 邮箱（网易/QQ）**随机轮询**发送验证码，避免单账号发送受限。
    * 注册即绑定邮箱，防止恶意灌水。
* **👤 用户系统**:
    * **QQ 绑定**: 自动获取 QQ 头像和昵称。
    * **角色管理**: 超级管理员 (Super Admin)、管理员 (Admin)、普通用户。
    * **蓝勾认证**: 管理员发言带有专属认证图标。
* **🌍 痕迹追踪**:
    * 自动解析 **IP 归属地** (如: 中国 福建)。
    * 自动识别 **设备型号** (如: iPhone 16 / Windows)。
    * 游客限制: 未登录 IP 每日限发 5 条消息。
* **💬 交互功能**:
    * 评论回复 (带引用)。
    * 消息撤回/删除 (软删除)。
    * 长消息折叠。

## 📂 文件结构

```text
scifi-board/
├── api/
│   └── index.py       # 核心后端逻辑 (Flask)
├── templates/
│   └── index.html     # 前端单文件 (HTML+CSS+JS)
├── requirements.txt   # Python 依赖
├── vercel.json        # Vercel 路由配置
├── README.md          # 项目说明
└── .env               # 本地环境变量 (不上传)
