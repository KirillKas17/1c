"""
Тесты для модуля hierarchy_parser.py
Проверка обработки иерархических структур, типов контрагентов и извлечения ИНН.
"""

import unittest
import sys
import os
import importlib.util

# Добавляем путь к модулю
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Прямой импорт без загрузки всего core_parser (избегаем paddleocr)
spec = importlib.util.spec_from_file_location(
    "hierarchy_parser", 
    "/workspace/core_parser/semantic_parser/hierarchy_parser.py"
)
if spec and spec.loader:
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    HierarchyParser = module.HierarchyParser
    HierarchicalEntity = module.HierarchicalEntity
    CounterpartyType = module.CounterpartyType
else:
    raise ImportError("Cannot load hierarchy_parser")


class TestHierarchyParser(unittest.TestCase):
    
    def setUp(self):
        """Инициализация парсера перед каждым тестом"""
        self.parser = HierarchyParser()
    
    # ==================== Тесты иерархии ====================
    
    def test_simple_hierarchy(self):
        """Тест простой иерархии с явными маркерами"""
        text = "Отдел продаж - Москва - Менеджер Петров - Клиент ООО Ромашка"
        entities = self.parser.parse_hierarchical_string(text)
        
        self.assertEqual(len(entities), 4)
        self.assertEqual(entities[0].level, 'department')
        self.assertEqual(entities[1].level, 'city')
        self.assertEqual(entities[2].level, 'manager')
        self.assertEqual(entities[3].level, 'client')
    
    def test_hierarchy_with_different_separator(self):
        """Тест иерархии с разделителем '>'"""
        text = "Департамент > СПб > Менеджер Сидоров > ИП Васильев"
        entities = self.parser.parse_hierarchical_string(text)
        
        self.assertEqual(len(entities), 4)
        self.assertEqual(entities[0].value, 'Департамент')
        self.assertEqual(entities[1].value, 'СПб')
    
    def test_single_element(self):
        """Тест одиночного элемента без иерархии"""
        text = "ООО Ромашка"
        entities = self.parser.parse_hierarchical_string(text)
        
        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0].level, 'client')
    
    # ==================== Тесты типов контрагентов ====================
    
    def test_legal_entity_detection(self):
        """Тест определения юридического лица"""
        text = "Клиент ООО Ромашка"
        entities = self.parser.parse_hierarchical_string(text)
        
        client = entities[-1]
        self.assertEqual(client.counterparty_type, CounterpartyType.LEGAL_ENTITY)
    
    def test_ip_detection(self):
        """Тест определения ИП"""
        text = "Департамент > Менеджер Сидоров > ИП Васильев"
        entities = self.parser.parse_hierarchical_string(text)
        
        client = entities[-1]
        self.assertEqual(client.counterparty_type, CounterpartyType.INDIVIDUAL_ENTREPRENEUR)
    
    def test_self_employed_detection(self):
        """Тест определения самозанятого"""
        text = "Управление - Куратор Попов - Самозанятый Козлов"
        entities = self.parser.parse_hierarchical_string(text)
        
        client = entities[-1]
        self.assertEqual(client.counterparty_type, CounterpartyType.SELF_EMPLOYED)
    
    def test_individual_detection_fio(self):
        """Тест определения физлица по ФИО"""
        text = "Клиент Иванов Иван Иванович"
        entities = self.parser.parse_hierarchical_string(text)
        
        client = entities[-1]
        # Физлица определяются по формату ФИО
        self.assertIn(client.counterparty_type, [CounterpartyType.INDIVIDUAL, CounterpartyType.UNKNOWN])
    
    def test_unknown_counterparty(self):
        """Тест неизвестного типа контрагента"""
        text = "Клиент Смирнов А.А."
        entities = self.parser.parse_hierarchical_string(text)
        
        client = entities[-1]
        # Может быть individual или unknown в зависимости от формата
        self.assertIn(client.counterparty_type, [CounterpartyType.INDIVIDUAL, CounterpartyType.UNKNOWN])
    
    # ==================== Тесты ИНН ====================
    
    def test_inn_extraction_10_digits(self):
        """Тест извлечения ИНН из 10 цифр (юрлица)"""
        text = "ООО Вектор ИНН 7701234567"
        entities = self.parser.parse_hierarchical_string(text)
        
        client = entities[-1]
        self.assertEqual(client.inn, '7701234567')
    
    def test_inn_extraction_12_digits(self):
        """Тест извлечения ИНН из 12 цифр (ИП)"""
        text = "ИП Петров ИНН 500123456789"
        entities = self.parser.parse_hierarchical_string(text)
        
        client = entities[-1]
        self.assertEqual(client.inn, '500123456789')
    
    def test_inn_in_hierarchy(self):
        """Тест извлечения ИНН в иерархии"""
        text = "Филиал Москва - Менеджер Николаев - ООО Вектор ИНН 7701234567"
        entities = self.parser.parse_hierarchical_string(text)
        
        client = entities[-1]
        self.assertEqual(client.inn, '7701234567')
        self.assertEqual(client.counterparty_type, CounterpartyType.LEGAL_ENTITY)
    
    def test_no_inn(self):
        """Тест отсутствия ИНН"""
        text = "ООО Ромашка"
        entities = self.parser.parse_hierarchical_string(text)
        
        client = entities[-1]
        self.assertIsNone(client.inn)
    
    # ==================== Тесты городов ====================
    
    def test_moscow_detection(self):
        """Тест определения Москвы"""
        text = "Отдел - Москва - Менеджер"
        entities = self.parser.parse_hierarchical_string(text)
        
        city = entities[1]
        self.assertEqual(city.level, 'city')
        self.assertEqual(city.value, 'Москва')
    
    def test_spb_detection(self):
        """Тест определения СПб"""
        text = "Департамент > СПб > Клиент"
        entities = self.parser.parse_hierarchical_string(text)
        
        city = entities[1]
        self.assertEqual(city.level, 'city')
        self.assertEqual(city.value, 'СПб')
    
    def test_city_by_name(self):
        """Тест определения города по названию"""
        text = "Филиал - Казань - Клиент"
        entities = self.parser.parse_hierarchical_string(text)
        
        city = entities[1]
        self.assertEqual(city.level, 'city')
    
    # ==================== Тесты confidence ====================
    
    def test_confidence_with_explicit_marker(self):
        """Тест высокой уверенности при явном маркере"""
        text = "Менеджер Петров"
        entities = self.parser.parse_hierarchical_string(text)
        
        manager = entities[0]
        self.assertGreater(manager.confidence, 0.7)
    
    def test_confidence_with_inn(self):
        """Тест повышения уверенности при наличии ИНН"""
        text = "ООО Вектор ИНН 7701234567"
        entities = self.parser.parse_hierarchical_string(text)
        
        client = entities[0]
        self.assertGreater(client.confidence, 0.6)
    
    # ==================== Тесты helper методов ====================
    
    def test_is_manager(self):
        """Тест метода is_manager"""
        self.assertTrue(self.parser.is_manager("Менеджер Иванов"))
        self.assertTrue(self.parser.is_manager("Специалист Петров"))
        self.assertFalse(self.parser.is_manager("ООО Ромашка"))
    
    def test_is_client(self):
        """Тест метода is_client"""
        self.assertTrue(self.parser.is_client("Клиент Сидоров"))
        self.assertTrue(self.parser.is_client("Заказчик ООО Вектор"))
        self.assertFalse(self.parser.is_client("Менеджер Попов"))
    
    def test_distinguish_manager_from_client_explicit(self):
        """Тест различения менеджера и клиента с явными маркерами"""
        manager_text = "Менеджер Иванов"
        client_text = "Клиент Петров"
        
        manager, client = self.parser.distinguish_manager_from_client(manager_text, client_text)
        
        self.assertEqual(manager, "Менеджер Иванов")
        self.assertEqual(client, "Клиент Петров")
    
    def test_get_hierarchy_as_dict(self):
        """Тест преобразования иерархии в словарь"""
        text = "Отдел - Москва - Менеджер - Клиент"
        entities = self.parser.parse_hierarchical_string(text)
        result = self.parser.get_hierarchy_as_dict(entities)
        
        self.assertIn('department', result)
        self.assertIn('city', result)
        self.assertIn('manager', result)
        self.assertIn('client', result)
        self.assertIn('full_path', result)
        self.assertEqual(result['levels_count'], 4)


class TestCounterpartyTypePatterns(unittest.TestCase):
    """Тесты паттернов определения типов контрагентов"""
    
    def setUp(self):
        self.parser = HierarchyParser()
    
    def test_legal_entity_patterns(self):
        """Тест паттернов юрлиц"""
        test_cases = [
            ("ООО Ромашка", CounterpartyType.LEGAL_ENTITY),
            ("АО Газпром", CounterpartyType.LEGAL_ENTITY),
            ("ПАО Сбербанк", CounterpartyType.LEGAL_ENTITY),
            ("ЗАО Вектор", CounterpartyType.LEGAL_ENTITY),
            ("ОАО РЖД", CounterpartyType.LEGAL_ENTITY),
        ]
        
        for text, expected_type in test_cases:
            with self.subTest(text=text):
                result = self.parser._determine_counterparty_type(text)
                self.assertEqual(result, expected_type)
    
    def test_ip_patterns(self):
        """Тест паттернов ИП"""
        test_cases = [
            ("ИП Иванов", CounterpartyType.INDIVIDUAL_ENTREPRENEUR),
            ("индивидуальный предприниматель Петров", CounterpartyType.INDIVIDUAL_ENTREPRENEUR),
        ]
        
        for text, expected_type in test_cases:
            with self.subTest(text=text):
                result = self.parser._determine_counterparty_type(text)
                self.assertEqual(result, expected_type)
    
    def test_self_employed_patterns(self):
        """Тест паттернов самозанятых"""
        test_cases = [
            ("самозанятый Козлов", CounterpartyType.SELF_EMPLOYED),
            ("плательщик нпд Сидоров", CounterpartyType.SELF_EMPLOYED),
        ]
        
        for text, expected_type in test_cases:
            with self.subTest(text=text):
                result = self.parser._determine_counterparty_type(text)
                self.assertEqual(result, expected_type)


if __name__ == '__main__':
    unittest.main(verbosity=2)
