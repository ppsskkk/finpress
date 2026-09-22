"""把生成的 html 稿件以邮件形式推送给自己：正文=排版好的HTML，附件=html原文件。"""
import glob
import os
import smtplib
from email.header import Header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.qq.com")   # 163邮箱改为 smtp.163.com
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
MAIL_USER = os.environ["MAIL_USER"]                      # 发件邮箱
MAIL_PASS = os.environ["MAIL_PASS"]                      # SMTP 授权码（非登录密码）
MAIL_TO = os.environ.get("MAIL_TO") or MAIL_USER         # 收件邮箱，默认发给自己

files = sorted(glob.glob("article_*.html"))
if not files:
    raise SystemExit("未找到 article_*.html，邮件推送跳过")
fp = files[0]
html = open(fp, encoding="utf-8").read()

msg = MIMEMultipart("alternative")
msg["Subject"] = Header(f"【简报已生成】{fp}", "utf-8")
msg["From"] = MAIL_USER
msg["To"] = MAIL_TO
msg.attach(MIMEText(html, "html", "utf-8"))

with open(fp, "rb") as f:
    att = MIMEApplication(f.read(), _subtype="html")
att.add_header("Content-Disposition", "attachment", filename=fp)
msg.attach(att)

with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as s:
    s.login(MAIL_USER, MAIL_PASS)
    s.sendmail(MAIL_USER, [MAIL_TO], msg.as_string())

print(f"已发送至 {MAIL_TO}")
