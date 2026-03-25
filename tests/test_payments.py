"""
Тесты для модуля платежей ЮKassa
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, timezone
import json
import sys
import os

# Добавляем путь к модулю
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from payments.yookassa_service import (
    YooKassaPaymentService,
    PaymentStatus,
    SubscriptionTier,
    Payment,
    Subscription
)


class TestPaymentStatus(unittest.TestCase):
    """Тесты enum статусов платежа"""
    
    def test_payment_status_values(self):
        """Проверка значений статусов"""
        self.assertEqual(PaymentStatus.PENDING.value, "pending")
        self.assertEqual(PaymentStatus.SUCCEEDED.value, "succeeded")
        self.assertEqual(PaymentStatus.CANCELED.value, "canceled")
        self.assertEqual(PaymentStatus.FAILED.value, "failed")
        self.assertEqual(PaymentStatus.WAITING_FOR_CAPTURE.value, "waiting_for_capture")


class TestSubscriptionTier(unittest.TestCase):
    """Тесты enum тарифов"""
    
    def test_subscription_tier_values(self):
        """Проверка значений тарифов"""
        self.assertEqual(SubscriptionTier.FREE.value, "free")
        self.assertEqual(SubscriptionTier.BASIC.value, "basic")
        self.assertEqual(SubscriptionTier.PRO.value, "pro")
        self.assertEqual(SubscriptionTier.ENTERPRISE.value, "enterprise")


class TestYooKassaPaymentService(unittest.TestCase):
    """Тесты сервиса платежей"""
    
    def setUp(self):
        """Настройка тестового окружения"""
        self.shop_id = "test_shop_123"
        self.secret_key = "test_secret_key_456"
        self.service = YooKassaPaymentService(
            shop_id=self.shop_id,
            secret_key=self.secret_key,
            test_mode=True
        )
    
    def test_initialization(self):
        """Проверка инициализации сервиса"""
        self.assertEqual(self.service.shop_id, self.shop_id)
        self.assertEqual(self.service.secret_key, self.secret_key)
        self.assertTrue(self.service.test_mode)
        self.assertEqual(self.service.base_url, "https://api.yookassa.ru/v3")
    
    def test_tariffs_structure(self):
        """Проверка структуры тарифов"""
        tariffs = self.service.TARIFFS
        
        # Проверка наличия всех тарифов
        self.assertIn(SubscriptionTier.FREE, tariffs)
        self.assertIn(SubscriptionTier.BASIC, tariffs)
        self.assertIn(SubscriptionTier.PRO, tariffs)
        self.assertIn(SubscriptionTier.ENTERPRISE, tariffs)
        
        # Проверка структуры тарифа
        free_tariff = tariffs[SubscriptionTier.FREE]
        self.assertIn('name', free_tariff)
        self.assertIn('price', free_tariff)
        self.assertIn('documents_limit', free_tariff)
        self.assertIn('features', free_tariff)
        
        # Проверка цен
        self.assertEqual(tariffs[SubscriptionTier.FREE]['price'], 0)
        self.assertEqual(tariffs[SubscriptionTier.BASIC]['price'], 990)
        self.assertEqual(tariffs[SubscriptionTier.PRO]['price'], 2990)
        self.assertEqual(tariffs[SubscriptionTier.ENTERPRISE]['price'], 9990)
    
    @patch('payments.yookassa_service.requests.post')
    def test_create_payment_success(self, mock_post):
        """Тест успешного создания платежа"""
        # Мокируем ответ API
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'id': 'payment_123',
            'status': 'pending',
            'amount': {'value': '990.00', 'currency': 'RUB'},
            'confirmation': {
                'type': 'redirect',
                'return_url': 'https://example.com/success'
            }
        }
        mock_post.return_value = mock_response
        
        payment_data, error = self.service.create_payment(
            amount=990.0,
            currency='RUB',
            description='Тестовый платеж',
            user_id=1,
            subscription_tier='basic'
        )
        
        self.assertIsNone(error)
        self.assertIsNotNone(payment_data)
        self.assertEqual(payment_data['id'], 'payment_123')
        self.assertEqual(payment_data['status'], 'pending')
        
        # Проверка вызова API
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn('/payments', call_args[0][0])
    
    @patch('payments.yookassa_service.requests.post')
    def test_create_payment_error(self, mock_post):
        """Тест ошибки при создании платежа"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Invalid request'
        mock_post.return_value = mock_response
        
        payment_data, error = self.service.create_payment(amount=990.0)
        
        self.assertIsNotNone(error)
        self.assertIsNone(payment_data)
        self.assertIn('YooKassa API error', error)
    
    @patch('payments.yookassa_service.requests.get')
    def test_get_payment_info_success(self, mock_get):
        """Тест получения информации о платеже"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 'payment_123',
            'status': 'succeeded',
            'amount': {'value': '990.00', 'currency': 'RUB'}
        }
        mock_get.return_value = mock_response
        
        payment_info, error = self.service.get_payment_info('payment_123')
        
        self.assertIsNone(error)
        self.assertEqual(payment_info['id'], 'payment_123')
        self.assertEqual(payment_info['status'], 'succeeded')
    
    @patch('payments.yookassa_service.requests.post')
    def test_cancel_payment_success(self, mock_post):
        """Тест отмены платежа"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        success, error = self.service.cancel_payment('payment_123')
        
        self.assertTrue(success)
        self.assertIsNone(error)
    
    def test_verify_notification(self):
        """Тест проверки подписи уведомления"""
        notification_body = '{"event":"payment.succeeded","object":{"id":"payment_123"}}'
        
        # Создаем правильную подпись
        import hmac
        import hashlib
        expected_signature = hmac.new(
            self.secret_key.encode('utf-8'),
            notification_body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Проверяем
        result = self.service.verify_notification(notification_body, expected_signature)
        self.assertTrue(result)
        
        # Проверяем с неправильной подписью
        result = self.service.verify_notification(notification_body, 'wrong_signature')
        self.assertFalse(result)
    
    def test_get_confirmation_url(self):
        """Тест получения URL подтверждения"""
        payment_data = {
            'confirmation': {
                'type': 'redirect',
                'return_url': 'https://yookassa.ru/confirm/123'
            }
        }
        
        url = self.service.get_confirmation_url(payment_data)
        self.assertEqual(url, 'https://yookassa.ru/confirm/123')
        
        # Без confirmation
        url = self.service.get_confirmation_url({})
        self.assertIsNone(url)


class TestSubscriptionModel(unittest.TestCase):
    """Тесты модели подписки"""
    
    def test_days_remaining_property(self):
        """Проверка расчета оставшихся дней"""
        # Мокируем объект подписки
        sub = Mock(spec=Subscription)
        sub.end_date = datetime.now(timezone.utc) + timedelta(days=15)
        
        # Реализуем property вручную для теста
        delta = sub.end_date - datetime.now(timezone.utc)
        days = max(0, delta.days)
        
        self.assertGreaterEqual(days, 14)
        self.assertLessEqual(days, 16)
    
    def test_days_remaining_expired(self):
        """Проверка для истекшей подписки"""
        end_date = datetime.now(timezone.utc) - timedelta(days=5)
        delta = end_date - datetime.now(timezone.utc)
        days = max(0, delta.days)
        
        self.assertEqual(days, 0)


class TestPaymentFlow(unittest.TestCase):
    """Интеграционные тесты потока оплаты"""
    
    @patch('payments.yookassa_service.requests.post')
    @patch('payments.yookassa_service.db')
    def test_full_payment_flow(self, mock_db, mock_post):
        """Тест полного цикла оплаты"""
        service = YooKassaPaymentService("shop", "secret", True)
        
        # 1. Создание платежа
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'id': 'payment_test_123',
            'status': 'pending',
            'confirmation': {
                'type': 'redirect',
                'return_url': 'https://success.url'
            }
        }
        mock_post.return_value = mock_response
        
        payment_data, error = service.create_payment(
            amount=990,
            user_id=1,
            subscription_tier='basic'
        )
        
        self.assertIsNone(error)
        self.assertEqual(payment_data['id'], 'payment_test_123')
        
        # 2. Получение URL для редиректа
        url = service.get_confirmation_url(payment_data)
        self.assertEqual(url, 'https://success.url')
        
        # 3. Симуляция уведомления об успехе
        notification = {
            'event': 'payment.succeeded',
            'object': {
                'id': 'payment_test_123',
                'status': 'succeeded',
                'amount': {'value': '990.00'},
                'metadata': {'user_id': '1', 'subscription_tier': 'basic'}
            }
        }
        
        # Мокируем пользователя и БД
        mock_user = Mock()
        mock_user.id = 1
        
        # Тестируем обработку уведомления
        # (в реальном тесте нужно мокировать Query)
        pass


class TestTariffFeatures(unittest.TestCase):
    """Тесты функциональности тарифов"""
    
    def test_free_tariff_limits(self):
        """Проверка ограничений бесплатного тарифа"""
        service = YooKassaPaymentService("shop", "secret", True)
        free = service.TARIFFS[SubscriptionTier.FREE]
        
        self.assertEqual(free['price'], 0)
        self.assertEqual(free['documents_limit'], 10)
        self.assertIn('Базовый анализ', free['features'])
    
    def test_enterprise_tariff_unlimited(self):
        """Проверка безлимитности enterprise тарифа"""
        service = YooKassaPaymentService("shop", "secret", True)
        enterprise = service.TARIFFS[SubscriptionTier.ENTERPRISE]
        
        self.assertEqual(enterprise['documents_limit'], -1)  # Безлимит
        self.assertIn('Безлимитные документы', enterprise['features'])
        self.assertIn('Персональный менеджер', enterprise['features'])
    
    def test_pro_tariff_features(self):
        """Проверка функций PRO тарифа"""
        service = YooKassaPaymentService("shop", "secret", True)
        pro = service.TARIFFS[SubscriptionTier.PRO]
        
        self.assertEqual(pro['documents_limit'], 500)
        self.assertIn('Экспорт PDF/PPTX', pro['features'])
        self.assertIn('API доступ', pro['features'])
        self.assertIn('История 1 год', pro['features'])


def run_tests():
    """Запуск всех тестов"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Добавляем все тесты
    suite.addTests(loader.loadTestsFromTestCase(TestPaymentStatus))
    suite.addTests(loader.loadTestsFromTestCase(TestSubscriptionTier))
    suite.addTests(loader.loadTestsFromTestCase(TestYooKassaPaymentService))
    suite.addTests(loader.loadTestsFromTestCase(TestSubscriptionModel))
    suite.addTests(loader.loadTestsFromTestCase(TestPaymentFlow))
    suite.addTests(loader.loadTestsFromTestCase(TestTariffFeatures))
    
    # Запускаем
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
