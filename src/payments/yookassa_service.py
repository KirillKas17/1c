"""
YooKassa Payment Integration Module
Обработка платежей через ЮKassa API
"""

import uuid
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from decimal import Decimal
import requests
from flask import request, abort, jsonify, current_app
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship, declarative_base
import enum

# Базовый класс для моделей SQLAlchemy
Base = declarative_base()

# Глобальная переменная для db (инициализируется при старте приложения)
db = None


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    WAITING_FOR_CAPTURE = "waiting_for_capture"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"
    FAILED = "failed"


class SubscriptionTier(enum.Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Payment(Base):
    """Модель платежа"""
    __tablename__ = 'payments'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    yookassa_payment_id = Column(String(50), unique=True, nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default='RUB')
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    description = Column(Text)
    payment_metadata = Column('metadata', Text)  # JSON строка с дополнительными данными
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    expires_at = Column(DateTime)
    is_test = Column(Boolean, default=False)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': self.amount,
            'currency': self.currency,
            'status': self.status.value,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_test': self.is_test
        }


class Subscription(Base):
    """Модель подписки пользователя"""
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    tier = Column(Enum(SubscriptionTier), default=SubscriptionTier.FREE)
    start_date = Column(DateTime, default=datetime.now(timezone.utc))
    end_date = Column(DateTime)
    is_active = Column(Boolean, default=False)
    auto_renew = Column(Boolean, default=False)
    yookassa_subscription_id = Column(String(50), unique=True, nullable=True)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'tier': self.tier.value,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_active': self.is_active,
            'auto_renew': self.auto_renew
        }
    
    @property
    def days_remaining(self) -> int:
        if not self.end_date:
            return 0
        delta = self.end_date - datetime.now(timezone.utc)
        return max(0, delta.days)


class YooKassaPaymentService:
    """Сервис для работы с платежной системой ЮKassa"""
    
    # Тарифы
    TARIFFS = {
        SubscriptionTier.FREE: {
            'name': 'Бесплатный',
            'price': 0,
            'documents_limit': 10,
            'features': ['Базовый анализ', '10 документов/мес', 'Email поддержка']
        },
        SubscriptionTier.BASIC: {
            'name': 'Базовый',
            'price': 990,
            'documents_limit': 100,
            'features': ['Расширенный анализ', '100 документов/мес', 'Экспорт PDF', 'Приоритетная поддержка']
        },
        SubscriptionTier.PRO: {
            'name': 'Профессиональный',
            'price': 2990,
            'documents_limit': 500,
            'features': ['Полный анализ', '500 документов/мес', 'Экспорт PDF/PPTX', 'API доступ', 'История 1 год']
        },
        SubscriptionTier.ENTERPRISE: {
            'name': 'Корпоративный',
            'price': 9990,
            'documents_limit': -1,  # Безлимит
            'features': ['Безлимитные документы', 'Персональный менеджер', 'SLA 99.9%', 'Кастомизация', 'On-premise опция']
        }
    }
    
    def __init__(self, shop_id: str, secret_key: str, test_mode: bool = True):
        """
        Инициализация сервиса
        
        :param shop_id: ID магазина в ЮKassa
        :param secret_key: Секретный ключ
        :param test_mode: Режим тестирования
        """
        self.shop_id = shop_id
        self.secret_key = secret_key
        self.test_mode = test_mode
        self.base_url = "https://api.yookassa.ru/v3" if not test_mode else "https://api.yookassa.ru/v3"
        
        # Заголовки для авторизации
        self.auth = (shop_id, secret_key)
        self.headers = {
            'Content-Type': 'application/json',
            'Idempotence-Key': str(uuid.uuid4())
        }
    
    def create_payment(self, 
                      amount: float, 
                      currency: str = 'RUB',
                      description: str = 'Оплата подписки',
                      user_id: int = None,
                      subscription_tier: str = None,
                      return_url: str = None) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Создание платежа
        
        :return: (payment_data, error_message)
        """
        idempotence_key = str(uuid.uuid4())
        
        # Используем переданный return_url или дефолтный
        default_return_url = return_url or "http://localhost/payment/success"
        
        payment_data = {
            "amount": {
                "value": str(amount),
                "currency": currency
            },
            "capture": True,  # Автоматическое подтверждение
            "confirmation": {
                "type": "redirect",
                "return_url": default_return_url
            },
            "description": description,
            "metadata": {
                "user_id": str(user_id),
                "subscription_tier": subscription_tier
            }
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/payments",
                auth=self.auth,
                headers={**self.headers, 'Idempotence-Key': idempotence_key},
                json=payment_data,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                return response.json(), None
            else:
                error_msg = f"YooKassa API error: {response.status_code} - {response.text}"
                return None, error_msg
                
        except requests.exceptions.RequestException as e:
            return None, f"Request failed: {str(e)}"
    
    def get_payment_info(self, payment_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Получение информации о платеже"""
        try:
            response = requests.get(
                f"{self.base_url}/payments/{payment_id}",
                auth=self.auth,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json(), None
            else:
                return None, f"Error getting payment info: {response.status_code}"
                
        except requests.exceptions.RequestException as e:
            return None, f"Request failed: {str(e)}"
    
    def cancel_payment(self, payment_id: str) -> Tuple[bool, Optional[str]]:
        """Отмена платежа"""
        try:
            response = requests.post(
                f"{self.base_url}/payments/{payment_id}/cancel",
                auth=self.auth,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                return True, None
            else:
                return False, f"Error canceling payment: {response.status_code}"
                
        except requests.exceptions.RequestException as e:
            return False, f"Request failed: {str(e)}"
    
    def verify_notification(self, notification_body: str, signature: str) -> bool:
        """
        Проверка подписи уведомления от ЮKassa
        
        :param notification_body: Тело уведомления
        :param signature: Подпись из заголовка
        :return: True если подпись верна
        """
        expected_signature = hmac.new(
            self.secret_key.encode('utf-8'),
            notification_body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    def handle_notification(self, notification_data: Dict) -> Optional[Payment]:
        """
        Обработка уведомления от ЮKassa
        
        :param notification_data: Данные уведомления
        :return: Обновленный объект Payment или None
        """
        event_type = notification_data.get('event')
        payment_object = notification_data.get('object', {})
        
        yookassa_payment_id = payment_object.get('id')
        status = payment_object.get('status')
        amount_value = float(payment_object.get('amount', {}).get('value', 0))
        metadata = payment_object.get('metadata', {})
        
        # Находим платеж в БД
        payment = Payment.query.filter_by(yookassa_payment_id=yookassa_payment_id).first()
        
        if not payment:
            # Создаем новый платеж если не найден
            user_id = metadata.get('user_id')
            if user_id:
                payment = Payment(
                    user_id=int(user_id),
                    yookassa_payment_id=yookassa_payment_id,
                    amount=amount_value,
                    status=PaymentStatus(status) if status in [s.value for s in PaymentStatus] else PaymentStatus.PENDING,
                    metadata=json.dumps(metadata)
                )
                db.session.add(payment)
        else:
            # Обновляем существующий
            if status in [s.value for s in PaymentStatus]:
                payment.status = PaymentStatus(status)
            payment.amount = amount_value
            payment.payment_metadata = json.dumps(metadata)
        
        # Если платеж успешен - активируем подписку
        if payment.status == PaymentStatus.SUCCEEDED:
            subscription_tier = metadata.get('subscription_tier')
            if subscription_tier and payment.user:
                self._activate_subscription(payment.user, subscription_tier)
        
        db.session.commit()
        return payment
    
    def _activate_subscription(self, user, tier_name: str):
        """Активация подписки для пользователя"""
        tier = SubscriptionTier(tier_name)
        
        subscription = Subscription.query.filter_by(user_id=user.id).first()
        
        if not subscription:
            subscription = Subscription(user_id=user.id)
            db.session.add(subscription)
        
        subscription.tier = tier
        subscription.is_active = True
        subscription.start_date = datetime.now(timezone.utc)
        
        # Устанавливаем дату окончания в зависимости от тарифа
        if tier != SubscriptionTier.FREE:
            subscription.end_date = datetime.now(timezone.utc) + timedelta(days=30)
            subscription.auto_renew = True
        
        # Обновляем лимиты пользователя
        tariff_info = self.TARIFFS[tier]
        user.documents_limit = tariff_info['documents_limit']
        user.tier = tier
    
    def get_confirmation_url(self, payment_data: Dict) -> Optional[str]:
        """Получение URL для подтверждения платежа"""
        confirmation = payment_data.get('confirmation', {})
        if confirmation.get('type') == 'redirect':
            return confirmation.get('return_url')
        return None


# Blueprint для Flask
from flask import Blueprint, redirect, url_for, render_template, session

payments_bp = Blueprint('payments', __name__, url_prefix='/payments')

def init_payments(app, db_instance):
    """Инициализация модуля платежей"""
    global db
    db = db_instance
    
    # Создание таблиц
    with app.app_context():
        db.create_all()
    
    # Регистрация blueprint
    app.register_blueprint(payments_bp)
    
    # Инициализация сервиса
    shop_id = app.config.get('YOOKASSA_SHOP_ID', 'test_shop_id')
    secret_key = app.config.get('YOOKASSA_SECRET_KEY', 'test_secret_key')
    test_mode = app.config.get('YOOKASSA_TEST_MODE', True)
    
    app.yookassa_service = YooKassaPaymentService(shop_id, secret_key, test_mode)


@payments_bp.route('/create/<tier>')
def create_payment(tier: str):
    """Создание платежа для подписки"""
    from src.auth.jwt_auth import token_required
    from functools import wraps
    
    # Проверка аутентификации (упрощенно)
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['user_id']
    
    if tier not in [t.value for t in SubscriptionTier]:
        return jsonify({'error': 'Invalid tier'}), 400
    
    service = current_app.yookassa_service
    tariff = service.TARIFFS[SubscriptionTier(tier)]
    
    if tariff['price'] == 0:
        # Бесплатный тариф - просто активируем
        user = User.query.get(user_id)
        service._activate_subscription(user, tier)
        return redirect(url_for('dashboard'))
    
    # Создаем платеж
    payment_data, error = service.create_payment(
        amount=tariff['price'],
        description=f"Подписка '{tariff['name']}' на 30 дней",
        user_id=user_id,
        subscription_tier=tier,
        return_url=url_for('payments.success', _external=True)
    )
    
    if error:
        return jsonify({'error': error}), 500
    
    # Сохраняем платеж в БД
    payment = Payment(
        user_id=user_id,
        yookassa_payment_id=payment_data['id'],
        amount=tariff['price'],
        description=f"Подписка '{tariff['name']}'",
        payment_metadata=json.dumps({'subscription_tier': tier}),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)  # Платеж действителен 30 минут
    )
    db.session.add(payment)
    db.session.commit()
    
    # Перенаправляем на страницу оплаты ЮKassa
    confirmation_url = service.get_confirmation_url(payment_data)
    if confirmation_url:
        return redirect(confirmation_url)
    
    return jsonify({'error': 'Failed to get confirmation URL'}), 500


@payments_bp.route('/success')
def success():
    """Страница успешной оплаты"""
    payment_id = request.args.get('payment_id')
    
    if payment_id:
        service = current_app.yookassa_service
        payment_info, error = service.get_payment_info(payment_id)
        
        if payment_info and payment_info.get('status') == 'succeeded':
            return render_template('payment_success.html', payment=payment_info)
    
    return render_template('payment_success.html', payment=None)


@payments_bp.route('/webhook', methods=['POST'])
def webhook():
    """Webhook для уведомлений от ЮKassa"""
    signature = request.headers.get('X-Yookassa-Signature')
    
    if not signature:
        abort(400, description='Missing signature')
    
    service = current_app.yookassa_service
    
    # Проверяем подпись (в продакшене обязательно!)
    # if not service.verify_notification(request.data.decode('utf-8'), signature):
    #     abort(403, description='Invalid signature')
    
    try:
        notification_data = request.json
        payment = service.handle_notification(notification_data)
        
        if payment:
            return jsonify({'status': 'ok', 'payment_id': payment.id}), 200
        else:
            return jsonify({'status': 'ignored'}), 200
            
    except Exception as e:
        current_app.logger.error(f"Webhook error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@payments_bp.route('/tariffs')
def get_tariffs():
    """Получение списка тарифов"""
    service = current_app.yookassa_service
    return jsonify({
        'tariffs': [
            {
                'tier': tier.value,
                **info
            }
            for tier, info in service.TARIFFS.items()
        ]
    })


@payments_bp.route('/my-subscription')
def get_my_subscription():
    """Получение информации о текущей подписке пользователя"""
    # Заглушка для демонстрации - в реальном приложении использовать JWT
    from flask import session
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    subscription = Subscription.query.filter_by(user_id=user_id).first()
    
    if not subscription:
        return jsonify({
            'tier': 'free',
            'is_active': False,
            'documents_limit': 10
        }), 200
    
    return jsonify(subscription.to_dict()), 200


@payments_bp.route('/history')
def get_payment_history():
    """История платежей пользователя"""
    from flask import session
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    payments = Payment.query.filter_by(user_id=user_id)\
                           .order_by(Payment.created_at.desc())\
                           .limit(50)\
                           .all()
    
    return jsonify({
        'payments': [p.to_dict() for p in payments]
    }), 200
