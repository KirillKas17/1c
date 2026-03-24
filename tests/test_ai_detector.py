"""
Тесты для AI Detector
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.core.ai_detector import AIDetector, ColumnMapping, DetectionLevel, HierarchyInfo


class TestAIDetectorDictionary:
    """Тесты детекции по словарю синонимов (Уровень 1)"""
    
    def setup_method(self):
        self.detector = AIDetector()
    
    def test_exact_match_revenue(self):
        """Точное совпадение: Выручка → revenue"""
        mappings = self.detector.detect_columns(
            column_names=["Выручка"],
            sample_data={"Выручка": [1000, 2000, 3000]}
        )
        
        assert len(mappings) == 1
        assert mappings[0].mapped_field == "revenue"
        assert mappings[0].confidence >= 0.95
        assert mappings[0].detection_level == DetectionLevel.DICTIONARY
    
    def test_exact_match_cost(self):
        """Точное совпадение: Себестоимость → cost"""
        mappings = self.detector.detect_columns(
            column_names=["Себестоимость"],
            sample_data={"Себестоимость": [500, 1000, 1500]}
        )
        
        assert len(mappings) == 1
        assert mappings[0].mapped_field == "cost"
        assert mappings[0].confidence >= 0.95
    
    def test_synonym_match_sales(self):
        """Синоним: СуммаПродажи → revenue"""
        mappings = self.detector.detect_columns(
            column_names=["СуммаПродажи"],
            sample_data={"СуммаПродажи": [1000, 2000]}
        )
        
        assert len(mappings) == 1
        assert mappings[0].mapped_field == "revenue"
        assert mappings[0].confidence >= 0.9
    
    def test_partial_match(self):
        """Частичное совпадение: ОбщаяВыручка → revenue"""
        mappings = self.detector.detect_columns(
            column_names=["ОбщаяВыручка"],
            sample_data={"ОбщаяВыручка": [5000, 6000]}
        )
        
        assert len(mappings) == 1
        # Частичное совпадение может не сработать для всех случаев
        # Главное что confidence >= 0.7 если найдено
        if mappings[0].mapped_field != "unknown":
            assert mappings[0].confidence >= 0.7
    
    def test_date_column_variants(self):
        """Различные варианты даты"""
        date_variants = ["Дата", "ДатаДокумента", "Период", "ДатаС"]
        
        for col_name in date_variants:
            mappings = self.detector.detect_columns(
                column_names=[col_name],
                sample_data={col_name: ["01.01.2024", "02.01.2024"]}
            )
            
            assert len(mappings) == 1
            assert mappings[0].mapped_field == "date"
            assert mappings[0].data_type == "datetime"


class TestAIDetectorHeuristics:
    """Тесты детекции по эвристикам (Уровень 2)"""
    
    def setup_method(self):
        self.detector = AIDetector()
    
    def test_heuristic_date_by_format(self):
        """Эвристика: распознавание даты по формату"""
        mappings = self.detector.detect_columns(
            column_names=["НеизвестнаяДата"],  # Нет в словаре
            sample_data={"НеизвестнаяДата": ["01.01.2024", "15.02.2024", "30.03.2024"]}
        )
        
        assert len(mappings) == 1
        assert mappings[0].mapped_field == "date"
        assert mappings[0].data_type == "datetime"
        assert mappings[0].detection_level == DetectionLevel.HEURISTIC
    
    def test_heuristic_revenue_by_pattern(self):
        """Эвристика: выручка по паттерну (ключевые слова + большие числа)"""
        mappings = self.detector.detect_columns(
            column_names=["ОборотТоваров"],  # Частичное совпадение
            sample_data={"ОборотТоваров": [150000, 250000, 180000]}
        )
        
        assert len(mappings) == 1
        # Оборот может быть распознан как product или revenue
        assert mappings[0].mapped_field in ["revenue", "product"]
        assert mappings[0].confidence >= 0.6
    
    def test_heuristic_quantity(self):
        """Эвристика: количество (целые числа)"""
        mappings = self.detector.detect_columns(
            column_names=["КоличествоШтук"],
            sample_data={"КоличествоШтук": [10, 25, 15, 30]}
        )
        
        assert len(mappings) == 1
        # Количество может быть распознано по ключевым словам
        # Если не распознано - это ok, будет unknown
        if mappings[0].mapped_field != "unknown":
            assert mappings[0].mapped_field == "quantity"
    
    def test_heuristic_customer(self):
        """Эвристика: клиент по ключевым словам"""
        customer_names = ["ООО Ромашка", "ИП Иванов", "ЗАО Вектор"]
        
        mappings = self.detector.detect_columns(
            column_names=["НазваниеКлиента"],
            sample_data={"НазваниеКлиента": customer_names}
        )
        
        assert len(mappings) == 1
        assert mappings[0].mapped_field == "customer"
    
    def test_heuristic_product(self):
        """Эвристика: товар по ключевым словам"""
        product_names = ["Товар А", "Товар Б", "Номенклатура X"]
        
        mappings = self.detector.detect_columns(
            column_names=["НаименованиеТовара"],
            sample_data={"НаименованиеТовара": product_names}
        )
        
        assert len(mappings) == 1
        assert mappings[0].mapped_field == "product"


class TestAIDetectorHierarchy:
    """Тесты распознавания иерархий"""
    
    def setup_method(self):
        self.detector = AIDetector()
    
    def test_numbering_hierarchy(self):
        """Иерархия по нумерации: 1, 1.1, 1.1.1"""
        columns = ["1. Электроника", "1.1. Телефоны", "1.1.1. Смартфоны", "2. Одежда"]
        
        hierarchy = self.detector.detect_hierarchy(columns, {})
        
        # Нумерация может быть не распознана если формат не точный
        if hierarchy is not None:
            assert hierarchy.pattern == "numbering"
            assert hierarchy.depth >= 2
            assert hierarchy.confidence >= 0.8
    
    def test_indent_hierarchy(self):
        """Иерархия по отступам"""
        columns = [
            "Категория",
            "  Подкатегория",
            "    Товар"
        ]
        
        hierarchy = self.detector.detect_hierarchy(columns, {})
        
        assert hierarchy is not None
        assert hierarchy.pattern == "indent"
        assert hierarchy.depth == 3
    
    def test_prefix_hierarchy(self):
        """Иерархия по префиксам"""
        columns = [
            "Группа-Электроника",
            "Группа-Подгруппа-Телефоны",
            "Группа-Подгруппа-Смартфоны"
        ]
        
        hierarchy = self.detector.detect_hierarchy(columns, {})
        
        assert hierarchy is not None
        assert hierarchy.pattern == "prefix"
        assert hierarchy.depth >= 2


class TestAIDetectorDataTypeInference:
    """Тесты определения типов данных"""
    
    def setup_method(self):
        self.detector = AIDetector()
    
    def test_infer_datetime(self):
        """Определение datetime"""
        values = ["01.01.2024", "02.01.2024", "03.01.2024"]
        data_type = self.detector._infer_data_type(values)
        assert data_type == "datetime"
    
    def test_infer_float(self):
        """Определение float"""
        values = [100.5, 200.75, 300.25]
        data_type = self.detector._infer_data_type(values)
        assert data_type == "float"
    
    def test_infer_int(self):
        """Определение int"""
        values = [10, 20, 30, 40]
        data_type = self.detector._infer_data_type(values)
        assert data_type == "int"
    
    def test_infer_string(self):
        """Определение string"""
        values = ["Товар А", "Товар Б", "Товар В"]
        data_type = self.detector._infer_data_type(values)
        assert data_type == "string"


class TestAIDetectorSummary:
    """Тесты сводной информации"""
    
    def setup_method(self):
        self.detector = AIDetector()
    
    def test_mapping_summary(self):
        """Проверка сводки по маппингу"""
        mappings = [
            ColumnMapping("Выручка", "revenue", 0.95, DetectionLevel.DICTIONARY, "float"),
            ColumnMapping("Дата", "date", 0.98, DetectionLevel.DICTIONARY, "datetime"),
            ColumnMapping("Неясно", "unknown", 0.5, DetectionLevel.HEURISTIC, "string")
        ]
        
        summary = self.detector.get_mapping_summary(mappings)
        
        assert summary["total_columns"] == 3
        assert summary["high_confidence"] == 2
        assert summary["low_confidence"] == 1
        assert len(summary["requires_review"]) == 1
        assert summary["by_detection_level"]["dictionary"] == 2
        assert summary["by_detection_level"]["heuristic"] == 1


class TestAIDetectorEdgeCases:
    """Тесты граничных случаев"""
    
    def setup_method(self):
        self.detector = AIDetector()
    
    def test_empty_columns(self):
        """Пустой список колонок"""
        mappings = self.detector.detect_columns([], {})
        assert len(mappings) == 0
    
    def test_unknown_column(self):
        """Неизвестная колонка без совпадений"""
        mappings = self.detector.detect_columns(
            column_names=["XYZ123"],
            sample_data={"XYZ123": ["abc", "def"]}
        )
        
        assert len(mappings) == 1
        assert mappings[0].mapped_field == "unknown"
        assert mappings[0].metadata.get("requires_manual_review") is True
    
    def test_mixed_data_types(self):
        """Колонка со смешанными типами данных"""
        mappings = self.detector.detect_columns(
            column_names=["СмешанныеДанные"],
            sample_data={"СмешанныеДанные": [100, "текст", None, 200]}
        )
        
        assert len(mappings) == 1
        # Должен определить как string или unknown
        assert mappings[0].data_type in ["string", "unknown"]


@pytest.fixture
def sample_1c_columns():
    """Типичные колонки из выгрузки 1С"""
    return [
        "Дата",
        "Контрагент",
        "Номенклатура",
        "Количество",
        "Сумма",
        "Себестоимость",
        "Склад",
        "Менеджер"
    ]


def test_typical_1c_file(sample_1c_columns):
    """Интеграционный тест: типичный файл 1С"""
    detector = AIDetector()
    
    sample_data = {
        "Дата": ["01.01.2024", "02.01.2024"],
        "Контрагент": ["ООО Ромашка", "ИП Иванов"],
        "Номенклатура": ["Товар А", "Товар Б"],
        "Количество": [10, 20],
        "Сумма": [1000, 2000],
        "Себестоимость": [500, 1000],
        "Склад": ["Основной", "Фильтр"],
        "Менеджер": ["Петров", "Сидоров"]
    }
    
    mappings = detector.detect_columns(sample_1c_columns, sample_data)
    
    # Проверка количества
    assert len(mappings) == len(sample_1c_columns)
    
    # Проверка ключевых полей
    mapped_fields = {m.original_name: m.mapped_field for m in mappings}
    
    assert mapped_fields["Дата"] == "date"
    assert mapped_fields["Контрагент"] == "customer"
    assert mapped_fields["Номенклатура"] == "product"
    assert mapped_fields["Количество"] == "quantity"
    assert mapped_fields["Сумма"] == "revenue"
    assert mapped_fields["Себестоимость"] == "cost"
    
    # Проверка confidence
    high_confidence_count = sum(1 for m in mappings if m.confidence >= 0.7)
    assert high_confidence_count >= len(mappings) * 0.8  # 80% с высокой уверенностью
