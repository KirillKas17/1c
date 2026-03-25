# YooKassa Payment Gateway Integration
"""
Интеграция с платежным шлюзом ЮKassa для обработки платежей и подписок.
Документация: https://yookassa.ru/developers/api
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from decimal import Decimal

from yookassa import Configuration, Payment
from yookassa.domain.models.receipt import Receipt, ReceiptItem
from yookassa.domain.models.confirmation import ConfirmationType, Confirmation
from yookassa.domain.models.currency import Currency
from yookassa.domain.notification import (
    WebhookNotificationEventType,
    WebhookNotification
)

from src.core.config import settings
from src.api.models.models import User, Subscription, PaymentTransaction
from src.api.services.trial_service import trial_service


class YooKassaService:
    """Сервис для работы с платежной системой ЮKassa."""
    
    def __init__(self):
        self.shop_id = settings.YOOKASSA_SHOP_ID
        self.secret_key = settings.YOOKASSA_SECRET_KEY
        
        if self.shop_id and self.secret_key:
            Configuration.account_id = self.shop_id
            Configuration.secret_key = self.secret_key
            self.enabled = True
        else:
            self.enabled = False
            print("⚠️ YooKassa не настроена. Установите YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY")
    
    def create_payment(
        self,
        user: User,
        amount: Decimal,
        description: str,
        return_url: str,
        save_card: bool = False,
        receipt_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создание платежа.
        
        :param user: Объект пользователя
        :param amount: Сумма платежа в рублях
        :param description: Описание платежа
        :param return_url: URL возврата после оплаты
        :param save_card: Сохранить карту для будущих платежей
        :param receipt_email: Email для отправки чека
        :return: Данные для оплаты (confirmation_url, payment_id)
        """
        if not self.enabled:
            # Демо-режим: возвращаем фейковый платеж
            return {
                "id": f"demo_payment_{uuid.uuid4()}",
                "status": "pending",
                "amount": {"value": str(amount), "currency": "RUB"},
                "description": description,
                "confirmation": {
                    "type": "redirect",
                    "confirmation_url": "https://yookassa.ru/demo/success"
                },
                "created_at": datetime.now().isoformat(),
                "demo_mode": True
            }
        
        try:
            # Формирование чека (54-ФЗ)
            receipt = None
            if receipt_email:
                receipt = Receipt(
                    customer={"email": receipt_email},
                    items=[
                        ReceiptItem(
                            description=description,
                            quantity=1,
                            amount={
                                "value": str(amount),
                                "currency": "RUB"
                            },
                            vat_code=6  # Без НДС (для УСН)
                        )
                    ]
                )
            
            # Параметры подтверждения
            confirmation = Confirmation(
                type=ConfirmationType.REDIRECT,
                return_url=return_url,
                save_payment_method=save_card
            )
            
            # Создание платежа
            payment = Payment.create({
                "amount": {
                    "value": str(amount),
                    "currency": "RUB"
                },
                "currency": "RUB",
                "description": description,
                "metadata": {
                    "user_id": str(user.id),
                    "payment_type": "one_time"
                },
                "confirmation": confirmation.dict(),
                "capture": True,  # Автоматическое проведение
                "receipt": receipt.dict() if receipt else None
            })
            
            # Сохранение транзакции в БД
            transaction = PaymentTransaction(
                user_id=user.id,
                payment_id=payment.id,
                amount=Decimal(str(amount)),
                currency="RUB",
                status=payment.status,
                description=description,
                created_at=datetime.fromisoformat(payment.created_at) if isinstance(payment.created_at, str) else payment.created_at
            )
            
            # Здесь должна быть логика сохранения в БД
            # await db.add(transaction)
            # await db.commit()
            
            return {
                "id": payment.id,
                "status": payment.status,
                "amount": {"value": str(amount), "currency": "RUB"},
                "description": description,
                "confirmation": {
                    "type": "redirect",
                    "confirmation_url": payment.confirmation.confirmation_url
                },
                "created_at": payment.created_at.isoformat() if hasattr(payment.created_at, 'isoformat') else str(payment.created_at),
                "demo_mode": False
            }
            
        except Exception as e:
            raise Exception(f"Ошибка создания платежа: {str(e)}")
    
    def create_subscription_payment(
        self,
        user: User,
        tariff_plan: str,
        amount: Decimal,
        return_url: str,
        save_card: bool = True
    ) -> Dict[str, Any]:
        """
        Создание платежа за подписку.
        
        :param user: Объект пользователя
        :param tariff_plan: Тарифный план (BASIC, PRO, ENTERPRISE)
        :param amount: Сумма платежа
        :param return_url: URL возврата
        :param save_card: Сохранить карту для автопродления
        :return: Данные для оплаты
        """
        description = f"Оплата подписки {tariff_plan} на 1 месяц"
        
        payment_data = self.create_payment(
            user=user,
            amount=amount,
            description=description,
            return_url=return_url,
            save_card=save_card,
            receipt_email=user.email
        )
        
        # Добавляем метаданные о подписке
        payment_data["metadata"]["subscription_plan"] = tariff_plan
        payment_data["metadata"]["payment_type"] = "subscription"
        
        return payment_data
    
    def handle_webhook(self, request_body: str, signature: str) -> Dict[str, Any]:
        """
        Обработка вебхука от ЮKassa.
        
        :param request_body: Тело запроса
        :param signature: Подпись запроса
        :return: Результат обработки
        """
        if not self.enabled:
            return {"status": "ignored", "reason": "demo_mode"}
        
        try:
            # Проверка подписи (в продакшене обязательно!)
            # if not self._verify_signature(request_body, signature):
            #     raise Exception("Invalid signature")
            
            notification = WebhookNotification.parse(request_body)
            event = notification.event
            payment_object = notification.object
            
            if event == WebhookNotificationEventType.PAYMENT_SUCCEEDED:
                return self._handle_payment_succeeded(payment_object)
            elif event == WebhookNotificationEventType.PAYMENT_WAITING_FOR_CAPTURE:
                return self._handle_waiting_for_capture(payment_object)
            elif event == WebhookNotificationEventType.PAYMENT_CANCELED:
                return self._handle_payment_canceled(payment_object)
            else:
                return {"status": "ignored", "event": event}
                
        except Exception as e:
            raise Exception(f"Ошибка обработки вебхука: {str(e)}")
    
    def _handle_payment_succeeded(self, payment_object: Payment) -> Dict[str, Any]:
        """Обработка успешного платежа."""
        user_id = payment_object.metadata.get("user_id")
        payment_type = payment_object.metadata.get("payment_type")
        subscription_plan = payment_object.metadata.get("subscription_plan")
        
        result = {
            "status": "success",
            "payment_id": payment_object.id,
            "amount": payment_object.amount.value,
            "user_id": user_id
        }
        
        if payment_type == "subscription" and subscription_plan:
            # Активация подписки
            result["subscription_activated"] = True
            result["plan"] = subscription_plan
            # Здесь логика активации подписки в БД
            # await subscription_service.activate_subscription(user_id, subscription_plan)
        
        # Обновление статуса транзакции в БД
        # await db.execute(update(PaymentTransaction).where(...).values(status="succeeded"))
        
        return result
    
    def _handle_waiting_for_capture(self, payment_object: Payment) -> Dict[str, Any]:
        """Платеж ожидает подтверждения."""
        return {
            "status": "waiting_for_capture",
            "payment_id": payment_object.id
        }
    
    def _handle_payment_canceled(self, payment_object: Payment) -> Dict[str, Any]:
        """Платеж отменен."""
        return {
            "status": "canceled",
            "payment_id": payment_object.id
        }
    
    def get_payment_info(self, payment_id: str) -> Dict[str, Any]:
        """Получение информации о платеже."""
        if not self.enabled:
            return {
                "id": payment_id,
                "status": "succeeded",
                "demo_mode": True
            }
        
        payment = Payment.find_one(payment_id)
        return {
            "id": payment.id,
            "status": payment.status,
            "amount": {"value": payment.amount.value, "currency": payment.amount.currency},
            "description": payment.description,
            "created_at": payment.created_at.isoformat() if hasattr(payment.created_at, 'isoformat') else str(payment.created_at)
        }
    
    def refund_payment(self, payment_id: str, amount: Optional[Decimal] = None) -> Dict[str, Any]:
        """
        Возврат средств.
        
        :param payment_id: ID платежа
        :param amount: Сумма возврата (если меньше полной суммы)
        :return: Информация о возврате
        """
        if not self.enabled:
            return {
                "id": f"refund_{uuid.uuid4()}",
                "status": "succeeded",
                "demo_mode": True
            }
        
        params = {
            "amount": {
                "value": str(amount),
                "currency": "RUB"
            }
        } if amount else {}
        
        refund = Payment.create_refund(payment_id, **params)
        
        return {
            "id": refund.id,
            "payment_id": refund.payment_id,
            "status": refund.status,
            "amount": {"value": refund.amount.value, "currency": refund.amount.currency}
        }


# Глобальный экземпляр сервиса
yookassa_service = YooKassaService()
