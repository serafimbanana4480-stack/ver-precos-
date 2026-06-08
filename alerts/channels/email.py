"""
Email channel for alerts.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from pydantic import BaseModel


class EmailChannel(BaseModel):
    """Email notification channel."""
    
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    from_email: str
    to_emails: List[str]
    use_tls: bool = True
    
    def send(self, subject: str, body: str, html: bool = False) -> bool:
        """Send email notification."""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            msg['Subject'] = subject
            
            if html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            return True
        except Exception:
            return False
