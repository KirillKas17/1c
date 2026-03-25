"""
Email Service для отправки уведомлений пользователям.
Поддержка SMTP, SendGrid, Mailgun.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.core.config import settings


class EmailService:
    """Сервис для отправки email уведомлений."""
    
    def __init__(self):
        self.smtp_host = getattr(settings, 'SMTP_HOST', 'smtp.yandex.ru')
        self.smtp_port = getattr(settings, 'SMTP_PORT', 587)
        self.smtp_user = getattr(settings, 'SMTP_USER', '')
        self.smtp_password = getattr(settings, 'SMTP_PASSWORD', '')
        self.smtp_use_tls = getattr(settings, 'SMTP_USE_TLS', True)
        
        self.email_from = getattr(settings, 'EMAIL_FROM', 'noreply@1c-dashboard.ru')
        self.email_from_name = getattr(settings, 'EMAIL_FROM_NAME', '1C Dashboard Service')
        
        self.enabled = bool(self.smtp_user and self.smtp_password)
        
        if not self.enabled:
            print("⚠️ Email сервис не настроен. Установите SMTP_USER и SMTP_PASSWORD")
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Отправка email сообщения.
        
        :param to_email: Email получателя
        :param subject: Тема письма
        :param html_content: HTML содержимое
        :param text_content: Текстовое содержимое (опционально)
        :return: True если успешно
        """
        if not self.enabled:
            print(f"📧 [DEMO] Email: {to_email} | {subject}")
            return True
        
        try:
            # Создание сообщения
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.email_from_name} <{self.email_from}>"
            msg['To'] = to_email
            
            # Добавление текстовой версии
            if text_content:
                part1 = MIMEText(text_content, 'plain', 'utf-8')
                msg.attach(part1)
            
            # Добавление HTML версии
            part2 = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(part2)
            
            # Отправка через SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.email_from, to_email, msg.as_string())
            
            print(f"✅ Email отправлен: {to_email} | {subject}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка отправки email: {str(e)}")
            return False
    
    def send_welcome_email(self, user_email: str, user_name: str, trial_days: int = 14) -> bool:
        """Отправка приветственного письма после регистрации."""
        subject = "Добро пожаловать в 1C Dashboard Service! 🎉"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #2563eb;">Добро пожаловать!</h1>
                
                <p>Здравствуйте, {user_name}!</p>
                
                <p>Спасибо за регистрацию в <strong>1C Dashboard Service</strong> — вашем интеллектуальном помощнике для анализа данных 1С.</p>
                
                <div style="background: #f0f9ff; border-left: 4px solid #2563eb; padding: 15px; margin: 20px 0;">
                    <h2 style="margin-top: 0; color: #2563eb;">🎁 Ваш триальный период активирован!</h2>
                    <p style="font-size: 18px; margin: 10px 0;">
                        <strong>{trial_days} дней</strong> полного доступа ко всем функциям
                    </p>
                    <ul style="line-height: 2;">
                        <li>✅ До 10 отчетов</li>
                        <li>✅ До 3 шаблонов</li>
                        <li>✅ AI-анализ документов</li>
                        <li>✅ Экспорт в PDF и PowerPoint</li>
                    </ul>
                </div>
                
                <h3>Что дальше?</h3>
                <ol>
                    <li>Загрузите ваш первый файл Excel/CSV</li>
                    <li>AI автоматически определит структуру данных</li>
                    <li>Получите готовый аналитический отчет</li>
                </ol>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="https://1c-dashboard.ru/dashboard" 
                       style="background: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Перейти в личный кабинет
                    </a>
                </div>
                
                <p style="color: #666; font-size: 14px; margin-top: 30px;">
                    Если у вас возникнут вопросы, наша команда поддержки всегда готова помочь.<br>
                    Просто ответьте на это письмо.
                </p>
                
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="color: #999; font-size: 12px;">
                    С уважением,<br>
                    Команда 1C Dashboard Service<br>
                    <a href="https://1c-dashboard.ru" style="color: #2563eb;">1c-dashboard.ru</a>
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        Здравствуйте, {user_name}!
        
        Добро пожаловать в 1C Dashboard Service!
        
        Ваш триальный период активирован: {trial_days} дней полного доступа.
        
        Что включено в триал:
        - До 10 отчетов
        - До 3 шаблонов
        - AI-анализ документов
        - Экспорт в PDF и PowerPoint
        
        Перейдите в личный кабинет: https://1c-dashboard.ru/dashboard
        
        С уважением,
        Команда 1C Dashboard Service
        """
        
        return self.send_email(user_email, subject, html_content, text_content)
    
    def send_trial_ending_soon(self, user_email: str, user_name: str, days_left: int, reports_used: int, reports_limit: int) -> bool:
        """Уведомление о скором окончании триала."""
        subject = f"⏰ Ваш триальный период заканчивается через {days_left} дн."
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #f59e0b;">Ваш триал скоро заканчивается</h1>
                
                <p>Здравствуйте, {user_name}!</p>
                
                <p>Напоминаем, что ваш триальный период в <strong>1C Dashboard Service</strong> заканчивается через <strong>{days_left} дн.</strong></p>
                
                <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Ваша статистика:</h3>
                    <p style="font-size: 16px;">
                        Использовано отчетов: <strong>{reports_used} из {reports_limit}</strong>
                    </p>
                </div>
                
                <h3>Не упустите возможность продолжить работу!</h3>
                <p>Выберите подходящий тарифный план:</p>
                
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr style="background: #f0f9ff;">
                        <th style="padding: 10px; border: 1px solid #ddd;">Тариф</th>
                        <th style="padding: 10px; border: 1px solid #ddd;">Цена</th>
                        <th style="padding: 10px; border: 1px solid #ddd;">Отчетов/мес</th>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>BASIC</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">990₽</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">50</td>
                    </tr>
                    <tr style="background: #f0f9ff;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>PRO</strong> ⭐</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">2990₽</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">200</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>ENTERPRISE</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">9990₽</td>
                        <td style="padding: 10px; border: 1px solid #ddd;">Безлимит</td>
                    </tr>
                </table>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="https://1c-dashboard.ru/billing" 
                       style="background: #f59e0b; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Выбрать тариф
                    </a>
                </div>
                
                <p style="color: #666; font-size: 14px;">
                    После окончания триала вы потеряете доступ к созданию новых отчетов.<br>
                    Оформите подписку сейчас и продолжите работу без перерывов!
                </p>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(user_email, subject, html_content)
    
    def send_payment_success(self, user_email: str, tariff_plan: str, amount: float) -> bool:
        """Уведомление об успешной оплате."""
        subject = f"✅ Оплата подписки {tariff_plan} прошла успешно"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #10b981;">Оплата прошла успешно! 🎉</h1>
                
                <p>Спасибо за оплату!</p>
                
                <div style="background: #ecfdf5; border-left: 4px solid #10b981; padding: 15px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Детали платежа:</h3>
                    <p><strong>Тариф:</strong> {tariff_plan}</p>
                    <p><strong>Сумма:</strong> {amount}₽</p>
                    <p><strong>Дата:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
                    <p><strong>Статус:</strong> Активна</p>
                </div>
                
                <p>Ваша подписка активирована. Теперь у вас есть полный доступ ко всем функциям сервиса.</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="https://1c-dashboard.ru/dashboard" 
                       style="background: #10b981; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Перейти в личный кабинет
                    </a>
                </div>
                
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="color: #999; font-size: 12px;">
                    Чек был отправлен на вашу почту отдельно.<br>
                    С уважением, Команда 1C Dashboard Service
                </p>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(user_email, subject, html_content)
    
    def send_password_reset(self, user_email: str, reset_token: str) -> bool:
        """Отправка ссылки для сброса пароля."""
        subject = "Сброс пароля для 1C Dashboard Service"
        reset_link = f"https://1c-dashboard.ru/reset-password?token={reset_token}"
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #2563eb;">Сброс пароля</h1>
                
                <p>Вы запросили сброс пароля для вашего аккаунта.</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" 
                       style="background: #2563eb; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Сбросить пароль
                    </a>
                </div>
                
                <p style="color: #666; font-size: 14px;">
                    Ссылка действительна в течение 1 часа.<br>
                    Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо.
                </p>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(user_email, subject, html_content)


# Глобальный экземпляр сервиса
email_service = EmailService()
