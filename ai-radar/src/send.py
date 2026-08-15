"""
Gmail SMTP 发送层。

规格来源：PROJECT_SPEC_V2.md §0（Gmail SMTP + 应用专用密码）

设计：只负责"给定 subject/body，发出去"，不含任何业务逻辑（配额判断、
静默日判断都在 render.py）。这样邮件*内容*的正确性可以单独用纯函数测试
（render.py 的 render_email），不需要真的连 SMTP 服务器；这里只测试
消息对象本身构造得对不对（build_message），真正的发信动作
（send_email）只在真实运行 / 手动验证时才会被调用。
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("send")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def build_message(sender: str, recipient: str, subject: str, body_text: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    return msg


def send_email(
    gmail_user: str,
    gmail_app_password: str,
    subject: str,
    body_text: str,
    recipient: str | None = None,
) -> None:
    """recipient 默认等于 gmail_user 自己（发给自己）——§0 决定的方案是
    同一个 Gmail 账号既做发件人也做收件人，不需要单独的收件人凭据。"""
    recipient = recipient or gmail_user
    msg = build_message(gmail_user, recipient, subject, body_text)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(gmail_user, gmail_app_password)
        server.sendmail(gmail_user, [recipient], msg.as_string())
    logger.info("邮件已发送: %r -> %s", subject, recipient)
