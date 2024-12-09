import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import COMMASPACE
from email import encoders
import logging


class MailSender:
    """通过SMTP协议发送邮件(python通过SMTP协议用qq邮箱群发带附件的邮件)"""

    def __init__(self, mail_host, mail_host_port, mail_user, mail_pass):
        self.mail_host = mail_host
        self.mail_host_port = mail_host_port
        self.mail_user = mail_user
        self.mail_pass = mail_pass
        self.mail = None

    def send_mail_with_attachment(self, receivers, subject, text, attach_file_name):
        # 创建邮件对象
        self.mail = MIMEMultipart()
        self.mail['From'] = self.mail_user
        self.mail['To'] = COMMASPACE.join(receivers)
        self.mail['Subject'] = subject

        # 添加邮件正文
        self.mail.attach(MIMEText(text))

        # 添加截图附件
        with open(attach_file_name, 'rb') as f:
            mime = MIMEBase('image', 'png', filename=attach_file_name)
            mime.add_header('Content-Disposition', 'attachment', filename=attach_file_name)
            mime.add_header('X-Attachment-Id', '0')
            mime.set_payload(f.read())
            encoders.encode_base64(mime)
            self.mail.attach(mime)

        # 发送邮件
        try:
            # smtp_obj = smtplib.SMTP()
            # smtp_obj.connect(self.mail_host, self.mail_host_port)
            smtp_obj = smtplib.SMTP_SSL(self.mail_host, self.mail_host_port)
            smtp_obj.login(self.mail_user, self.mail_pass)
            smtp_obj.sendmail(self.mail_user, receivers, self.mail.as_string())
            smtp_obj.quit()
            # logging.info("send mail success")
            print("send mail success")
        except smtplib.SMTPException as e:
            # logging.error(f"send mail failed:{e}")
            print(f"send mail failed:{e}")
        finally:
            pass


if __name__ == "__main__":
    mail_sender = MailSender(
        mail_host="smtp.qq.com",
        mail_host_port=465,
        mail_user="1983270580@qq.com",
        mail_pass="mklgfcgprteudebd"
    )

    mail_sender.send_mail_with_attachment(
        receivers=['wangfengchen@bankcomm.com'],
        subject='票据辅助助手邮件发送功能测试',
        text='您好，本邮件为功能测试，收到可忽略',
        attach_file_name='./qrcode.jpg'
    )
