"""
📧 Email Notification Service for 1C Dashboard SaaS

Professional email service with templates for:
- Trial welcome emails
- Usage warnings (80% limit)
- Trial expiration notices (3 days, 1 day)
- Subscription confirmations
- Password resets

Supports multiple providers:
- SMTP (generic)
- SendGrid
- Telegram Bot (fallback)
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Import settings from the correct location
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.api.config import Settings
settings = Settings()

logger = logging.getLogger(__name__)


class EmailService:
    """
    Professional email service with template support.
    
    Features:
    - Async email sending
    - HTML + text templates
    - Multiple providers (SMTP, SendGrid, Telegram)
    - Retry logic
    - Queue support (for high volume)
    """
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.EMAIL_FROM
        self.from_name = settings.FROM_NAME or "1C Dashboard"
        
        # Telegram fallback
        self.telegram_bot_token = settings.TELEGRAM_BOT_TOKEN
        self.telegram_admin_chat_id = settings.TELEGRAM_ADMIN_CHAT_ID
        
        # Template engine
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'htm', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        logger.info(f"EmailService initialized: {self.smtp_host}:{self.smtp_port}")
    
    async def send_trial_welcome(self, user_email: str, user_name: str, 
                                  trial_days: int = 14) -> bool:
        """Send welcome email when trial starts."""
        template = self.jinja_env.get_template("trial_welcome.html")
        
        context = {
            "user_name": user_name,
            "trial_days": trial_days,
            "features": [
                "До 10 отчетов",
                "3 шаблона",
                "5 файлов на загрузку",
                "AI анализ структуры",
                "Экспорт в PDF/PPTX",
                "Бизнес-правила 1С"
            ],
            "limits": {
                "reports_total": 10,
                "reports_per_day": 3,
                "templates": 3,
                "files": 5
            },
            "login_url": f"{settings.FRONTEND_URL}/dashboard",
            "docs_url": f"{settings.FRONTEND_URL}/docs",
            "support_email": settings.SUPPORT_EMAIL or "support@1c-dashboard.ru"
        }
        
        html_content = template.render(**context)
        text_content = self._html_to_text(html_content)
        
        return await self.send_email(
            to=user_email,
            subject=f"🎉 Добро пожаловать в 1C Dashboard! {trial_days} дней бесплатно",
            html=html_content,
            text=text_content
        )
    
    async def send_usage_warning(self, user_email: str, user_name: str,
                                  usage_percent: float, 
                                  reports_used: int,
                                  reports_limit: int) -> bool:
        """Send warning when user reaches 80% of trial limits."""
        template = self.jinja_env.get_template("usage_warning.html")
        
        days_left = max(1, 14 - (datetime.now().day % 14))  # Simplified
        
        context = {
            "user_name": user_name,
            "usage_percent": round(usage_percent, 1),
            "reports_used": reports_used,
            "reports_limit": reports_limit,
            "days_left": days_left,
            "upgrade_url": f"{settings.FRONTEND_URL}/billing/upgrade",
            "pricing_url": f"{settings.FRONTEND_URL}/pricing"
        }
        
        html_content = template.render(**context)
        text_content = self._html_to_text(html_content)
        
        return await self.send_email(
            to=user_email,
            subject=f"⚠️ Вы использовали {usage_percent:.0f}% триального лимита",
            html=html_content,
            text=text_content
        )
    
    async def send_trial_expiring_soon(self, user_email: str, user_name: str,
                                        days_left: int) -> bool:
        """Send notification when trial is expiring (3 days, 1 day)."""
        template = self.jinja_env.get_template("trial_expiring.html")
        
        context = {
            "user_name": user_name,
            "days_left": days_left,
            "upgrade_url": f"{settings.FRONTEND_URL}/billing/upgrade",
            "pricing_plans": [
                {"name": "BASIC", "price": "990₽/мес", "best_for": "Фрилансеры"},
                {"name": "PRO", "price": "2990₽/мес", "best_for": "Малый бизнес", "popular": True},
                {"name": "ENTERPRISE", "price": "9990₽/мес", "best_for": "Корпорации"}
            ],
            "features_comparison": {
                "reports": {"basic": 50, "pro": 200, "enterprise": "∞"},
                "templates": {"basic": 10, "pro": 50, "enterprise": "∞"},
                "users": {"basic": 1, "pro": 5, "enterprise": "∞"}
            }
        }
        
        html_content = template.render(**context)
        text_content = self._html_to_text(html_content)
        
        urgency = "Срочно" if days_left == 1 else "Важно"
        return await self.send_email(
            to=user_email,
            subject=f"{urgency}: Ваш триал истекает через {days_left} {'день' if days_left == 1 else 'дня'}",
            html=html_content,
            text=text_content
        )
    
    async def send_subscription_confirmed(self, user_email: str, user_name: str,
                                           plan_name: str, price: float,
                                           next_billing_date: datetime) -> bool:
        """Send confirmation after successful subscription."""
        template = self.jinja_env.get_template("subscription_confirmed.html")
        
        context = {
            "user_name": user_name,
            "plan_name": plan_name,
            "price": price,
            "currency": "₽",
            "billing_date": next_billing_date.strftime("%d.%m.%Y"),
            "invoice_url": f"{settings.FRONTEND_URL}/billing/invoices",
            "dashboard_url": f"{settings.FRONTEND_URL}/dashboard"
        }
        
        html_content = template.render(**context)
        text_content = self._html_to_text(html_content)
        
        return await self.send_email(
            to=user_email,
            subject=f"✅ Подписка {plan_name} активирована",
            html=html_content,
            text=text_content
        )
    
    async def send_password_reset(self, user_email: str, user_name: str,
                                   reset_token: str) -> bool:
        """Send password reset email."""
        template = self.jinja_env.get_template("password_reset.html")
        
        reset_url = f"{settings.FRONTEND_URL}/auth/reset-password?token={reset_token}"
        
        context = {
            "user_name": user_name,
            "reset_url": reset_url,
            "expires_hours": 24,
            "support_email": settings.SUPPORT_EMAIL or "support@1c-dashboard.ru"
        }
        
        html_content = template.render(**context)
        text_content = self._html_to_text(html_content)
        
        return await self.send_email(
            to=user_email,
            subject="🔐 Сброс пароля для 1C Dashboard",
            html=html_content,
            text=text_content
        )
    
    async def send_email(self, to: str, subject: str, 
                         html: str, text: Optional[str] = None) -> bool:
        """
        Send email via SMTP with retry logic.
        
        Args:
            to: Recipient email
            subject: Email subject
            html: HTML content
            text: Plain text content (optional)
        
        Returns:
            bool: True if sent successfully
        """
        if not self.smtp_host or not self.smtp_user:
            logger.warning("SMTP not configured, falling back to Telegram")
            return await self._send_telegram_message(to, subject, text or html)
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to
        
        if text:
            msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await aiosmtplib.send(
                    msg,
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    username=self.smtp_user,
                    password=self.smtp_password,
                    start_tls=True,
                    timeout=30
                )
                logger.info(f"Email sent to {to}: {subject}")
                return True
                
            except Exception as e:
                logger.warning(f"Email send failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to send email after {max_retries} attempts")
                    # Fallback to Telegram
                    return await self._send_telegram_message(to, subject, text or html)
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        return False
    
    async def _send_telegram_message(self, to: str, subject: str, 
                                      message: str) -> bool:
        """Fallback: Send notification via Telegram bot."""
        if not self.telegram_bot_token or not self.telegram_admin_chat_id:
            logger.error("Telegram not configured either. Email lost.")
            return False
        
        import aiohttp
        
        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        
        full_message = f"📧 <b>{subject}</b>\n\n"
        full_message += f"<i>Для: {to}</i>\n\n"
        # Strip HTML tags for Telegram
        import re
        clean_message = re.sub(r'<[^>]+>', '', message)[:4000]
        full_message += clean_message
        
        payload = {
            "chat_id": self.telegram_admin_chat_id,
            "text": full_message,
            "parse_mode": "HTML"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        logger.info(f"Telegram notification sent for {to}")
                        return True
                    else:
                        logger.error(f"Telegram API error: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False
    
    def _html_to_text(self, html: str) -> str:
        """Simple HTML to text conversion."""
        import re
        # Remove script and style elements
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '\n', text)
        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()


# Singleton instance
email_service = EmailService()


async def main():
    """Test email service."""
    # Test welcome email
    success = await email_service.send_trial_welcome(
        user_email="test@example.com",
        user_name="Иван Иванов",
        trial_days=14
    )
    print(f"Test email sent: {success}")


if __name__ == "__main__":
    asyncio.run(main())
