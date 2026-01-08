#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发送邮件附件
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path

# 邮件配置
MAIL_SERVER = 'smtp.qq.com'
MAIL_PORT = 587
MAIL_USE_TLS = True
MAIL_USERNAME = 'jimmyki@qq.com'
MAIL_PASSWORD = 'kurzssokwrixeahb'  # QQ邮箱授权码
MAIL_SENDER = 'Enterprise Wiki <jimmyki@qq.com>'

# 附件路径
pdf_path = Path("/Users/jimmyki/Documents/Code/news/docs/用户手册.pdf")

print(f"正在准备发送邮件...")
print(f"  - 附件: {pdf_path}")
print(f"  - 文件大小: {pdf_path.stat().st_size / 1024:.1f} KB")

# 创建邮件
msg = MIMEMultipart()
msg['From'] = MAIL_SENDER
msg['To'] = 'jimmyki@qq.com'
msg['Subject'] = '[新闻态势分析系统] 用户手册'

# 添加正文
body = """
您好！

附件是新闻态势分析系统的完整用户手册。

包含以下内容：
- 系统概述
- 登录页面说明
- 所有功能模块的详细说明
- 操作步骤和使用提示

祝使用愉快！

---
此邮件由系统自动发送，请勿回复。
"""

msg.attach(MIMEText(body, 'plain', 'utf-8'))

# 添加PDF附件
print(f"正在添加附件...")
with open(pdf_path, 'rb') as f:
    part = MIMEApplication(f.read(), Name=pdf_path.name)
part['Content-Disposition'] = f'attachment; filename="{pdf_path.name}"'
msg.attach(part)

# 发送邮件
print(f"正在连接到邮件服务器 {MAIL_SERVER}:{MAIL_PORT}...")

try:
    with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
        server.set_debuglevel(1)  # 显示调试信息
        print("正在启用TLS加密...")
        server.starttls()  # 启用TLS
        print("正在登录...")
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        print("正在发送邮件...")
        server.send_message(msg)
        print("\n✓ 邮件发送成功！")

except Exception as e:
    print(f"\n✗ 邮件发送失败: {e}")
    import traceback
    traceback.print_exc()
