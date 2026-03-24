"""
AI Detector для распознавания структуры файлов 1С

Трёхуровневая система детекции:
1. Словарь синонимов - сопоставление названий колонок с известными полями 1С
2. Эвристики - анализ формата данных, паттернов, иерархий
3. LLM (Ollama) - семантический анализ неясных случаев
"""

import re
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json

from config.field_mappings import FIELD_MAPPINGS, DATE_FORMATS


class DetectionLevel(Enum):
    """Уровень детекции"""
    DICTIONARY = "dictionary"  # Уровень 1: словарь синонимов
    HEURISTIC = "heuristic"    # Уровень 2: эвристики
    LLM = "llm"               # Уровень 3: LLM


@dataclass
class ColumnMapping:
    """Результат маппинга колонки"""
    original_name: str
    mapped_field: str
    confidence: float  # 0.0 - 1.0
    detection_level: DetectionLevel
    data_type: str
    aggregation: Optional[str] = None
    unit: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "original_name": self.original_name,
            "mapped_field": self.mapped_field,
            "confidence": self.confidence,
            "detection_level": self.detection_level.value,
            "data_type": self.data_type,
            "aggregation": self.aggregation,
            "unit": self.unit,
            "metadata": self.metadata
        }


@dataclass
class HierarchyInfo:
    """Информация об иерархии"""
    levels: List[str]
    depth: int
    pattern: str  # "indent", "numbering", "prefix"
    confidence: float


class AIDetector:
    """
    AI-детектор структуры файлов 1С
    
    Использует трёхуровневую систему для максимального качества распознавания
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.ollama_url = ollama_url
        self.model = model
        self._llm_cache: Dict[str, str] = {}  # Кэш LLM-ответов
        
    def detect_columns(self, column_names: List[str], sample_data: Dict[str, List]) -> List[ColumnMapping]:
        """
        Распознать колонки файла
        
        Args:
            column_names: Список названий колонок
            sample_data: Пример данных для анализа форматов
            
        Returns:
            Список маппингов колонок
        """
        mappings = []
        
        for col_name in column_names:
            # Уровень 1: Словарь синонимов
            mapping = self._detect_by_dictionary(col_name)
            
            if mapping and mapping.confidence >= 0.9:
                mappings.append(mapping)
                continue
            
            # Уровень 2: Эвристики
            if not mapping or mapping.confidence < 0.7:
                heuristic_mapping = self._detect_by_heuristics(col_name, sample_data.get(col_name, []))
                
                if heuristic_mapping and heuristic_mapping.confidence > (mapping.confidence if mapping else 0):
                    mapping = heuristic_mapping
            
            # Уровень 3: LLM для неясных случаев
            if not mapping or mapping.confidence < 0.6:
                llm_mapping = self._detect_by_llm(col_name, sample_data.get(col_name, []))
                
                if llm_mapping and llm_mapping.confidence > (mapping.confidence if mapping else 0):
                    mapping = llm_mapping
            
            # Если ничего не найдено - создаём неизвестный маппинг
            if not mapping:
                mapping = ColumnMapping(
                    original_name=col_name,
                    mapped_field="unknown",
                    confidence=0.5,
                    detection_level=DetectionLevel.HEURISTIC,
                    data_type=self._infer_data_type(sample_data.get(col_name, [])),
                    metadata={"requires_manual_review": True}
                )
            
            mappings.append(mapping)
        
        return mappings
    
    def _detect_by_dictionary(self, col_name: str) -> Optional[ColumnMapping]:
        """
        Уровень 1: Детекция по словарю синонимов
        
        Сопоставляет название колонки с известными полями из FIELD_MAPPINGS
        """
        col_name_normalized = self._normalize_column_name(col_name)
        
        best_match = None
        best_confidence = 0.0
        
        for field_id, field_config in FIELD_MAPPINGS.items():
            synonyms = field_config.get("synonyms", [])
            
            for synonym in synonyms:
                synonym_normalized = self._normalize_column_name(synonym)
                
                # Точное совпадение
                if col_name_normalized == synonym_normalized:
                    return ColumnMapping(
                        original_name=col_name,
                        mapped_field=field_id,
                        confidence=0.98,
                        detection_level=DetectionLevel.DICTIONARY,
                        data_type=field_config.get("data_type", "string"),
                        aggregation=field_config.get("aggregation"),
                        unit=field_config.get("unit"),
                        metadata={"matched_synonym": synonym}
                    )
                
                # Частичное совпадение (содержит синоним)
                if synonym_normalized in col_name_normalized or col_name_normalized in synonym_normalized:
                    confidence = 0.85 * (len(synonym_normalized) / len(col_name_normalized))
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = ColumnMapping(
                            original_name=col_name,
                            mapped_field=field_id,
                            confidence=confidence,
                            detection_level=DetectionLevel.DICTIONARY,
                            data_type=field_config.get("data_type", "string"),
                            aggregation=field_config.get("aggregation"),
                            unit=field_config.get("unit"),
                            metadata={"matched_synonym": synonym, "match_type": "partial"}
                        )
        
        return best_match if best_confidence >= 0.7 else None
    
    def _detect_by_heuristics(self, col_name: str, sample_values: List) -> Optional[ColumnMapping]:
        """
        Уровень 2: Детекция по эвристикам
        
        Анализирует:
        - Формат данных (дата, число, строка)
        - Паттерны названий (регистр, специальные символы)
        - Иерархии по отступам/нумерации
        """
        col_name_normalized = self._normalize_column_name(col_name)
        
        # Эвристика: Дата
        if self._is_date_column(sample_values):
            return ColumnMapping(
                original_name=col_name,
                mapped_field="date",
                confidence=0.85,
                detection_level=DetectionLevel.HEURISTIC,
                data_type="datetime",
                metadata={"detected_format": self._detect_date_format(sample_values)}
            )
        
        # Эвристика: Выручка/Сумма (число с большими значениями)
        if self._is_revenue_column(col_name_normalized, sample_values):
            return ColumnMapping(
                original_name=col_name,
                mapped_field="revenue",
                confidence=0.75,
                detection_level=DetectionLevel.HEURISTIC,
                data_type="float",
                aggregation="sum",
                unit="RUB",
                metadata={"heuristic": "revenue_pattern"}
            )
        
        # Эвристика: Количество (целые числа)
        if self._is_quantity_column(col_name_normalized, sample_values):
            return ColumnMapping(
                original_name=col_name,
                mapped_field="quantity",
                confidence=0.75,
                detection_level=DetectionLevel.HEURISTIC,
                data_type="int",
                aggregation="sum",
                metadata={"heuristic": "quantity_pattern"}
            )
        
        # Эвристика: Клиент/Контрагент
        if self._is_customer_column(col_name_normalized):
            return ColumnMapping(
                original_name=col_name,
                mapped_field="customer",
                confidence=0.70,
                detection_level=DetectionLevel.HEURISTIC,
                data_type="string",
                metadata={"heuristic": "customer_pattern"}
            )
        
        # Эвристика: Товар/Номенклатура
        if self._is_product_column(col_name_normalized):
            return ColumnMapping(
                original_name=col_name,
                mapped_field="product",
                confidence=0.70,
                detection_level=DetectionLevel.HEURISTIC,
                data_type="string",
                metadata={"heuristic": "product_pattern"}
            )
        
        return None
    
    def _detect_by_llm(self, col_name: str, sample_values: List) -> Optional[ColumnMapping]:
        """
        Уровень 3: Детекция через LLM (Ollama)
        
        Используется для неясных случаев, когда словарь и эвристики не дали результата
        """
        try:
            # Проверяем кэш
            cache_key = self._get_llm_cache_key(col_name, sample_values)
            if cache_key in self._llm_cache:
                cached_result = json.loads(self._llm_cache[cache_key])
                return ColumnMapping(**cached_result) if cached_result else None
            
            # Формируем промпт
            prompt = self._build_llm_prompt(col_name, sample_values)
            
            # Вызываем Ollama (локально)
            llm_response = self._call_ollama(prompt)
            
            # Парсим ответ
            mapping = self._parse_llm_response(llm_response, col_name, sample_values)
            
            # Сохраняем в кэш
            if mapping:
                self._llm_cache[cache_key] = json.dumps(mapping.to_dict())
            
            return mapping
            
        except Exception as e:
            print(f"LLM detection failed: {e}")
            return None
    
    def detect_hierarchy(self, column_names: List[str], sample_data: Dict[str, List]) -> Optional[HierarchyInfo]:
        """
        Распознать иерархию в данных
        
        Определяет паттерны:
        - Отступы в названиях
        - Нумерация (1, 1.1, 1.1.1)
        - Префиксы (Группа-, Подгруппа-)
        """
        # Паттерн: нумерация
        numbering_pattern = self._detect_numbering_hierarchy(column_names)
        if numbering_pattern:
            return numbering_pattern
        
        # Паттерн: отступы (пробелы в начале)
        indent_pattern = self._detect_indent_hierarchy(column_names)
        if indent_pattern:
            return indent_pattern
        
        # Паттерн: префиксы
        prefix_pattern = self._detect_prefix_hierarchy(column_names)
        if prefix_pattern:
            return prefix_pattern
        
        return None
    
    def _normalize_column_name(self, name: str) -> str:
        """Нормализовать название колонки"""
        # Удалить спецсимволы, привести к нижнему регистру
        normalized = re.sub(r'[^\w\sа-яА-ЯёЁ]', '', name)
        normalized = normalized.lower().strip()
        # Заменить множественные пробелы на один
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    def _infer_data_type(self, values: List) -> str:
        """Определить тип данных по значениям"""
        if not values:
            return "string"
        
        # Проверка на дату
        if self._is_date_column(values):
            return "datetime"
        
        # Проверка на число
        numeric_count = 0
        for val in values[:10]:  # Проверяем первые 10 значений
            if val is None or val == "":
                continue
            try:
                float(str(val).replace(',', '.').replace(' ', ''))
                numeric_count += 1
            except ValueError:
                pass
        
        if numeric_count > len([v for v in values[:10] if v and str(v).strip()]) * 0.8:
            # Проверка на целое число
            if all(float(str(v).replace(',', '.').replace(' ', '')).is_integer() 
                   for v in values[:10] if v and str(v).strip()):
                return "int"
            return "float"
        
        return "string"
    
    def _is_date_column(self, values: List) -> bool:
        """Проверить, является ли колонка датой"""
        if not values:
            return False
        
        date_count = 0
        for val in values[:10]:
            if val is None or val == "":
                continue
            
            val_str = str(val).strip()
            
            for fmt in DATE_FORMATS:
                try:
                    from datetime import datetime
                    datetime.strptime(val_str, fmt)
                    date_count += 1
                    break
                except ValueError:
                    continue
        
        return date_count > len([v for v in values[:10] if v and str(v).strip()]) * 0.7
    
    def _detect_date_format(self, values: List) -> Optional[str]:
        """Определить формат даты"""
        for val in values[:5]:
            if val is None or val == "":
                continue
            
            val_str = str(val).strip()
            
            for fmt in DATE_FORMATS:
                try:
                    from datetime import datetime
                    datetime.strptime(val_str, fmt)
                    return fmt
                except ValueError:
                    continue
        
        return None
    
    def _is_revenue_column(self, col_name: str, values: List) -> bool:
        """Проверить, является ли колонка выручкой"""
        revenue_keywords = ["сумм", "выручк", "оборот", "продаж", "доход"]
        
        if any(keyword in col_name for keyword in revenue_keywords):
            # Проверка на большие числовые значения
            numeric_values = []
            for val in values[:10]:
                if val and str(val).strip():
                    try:
                        num = float(str(val).replace(',', '.').replace(' ', ''))
                        if num > 1000:  # Выручка обычно большая
                            numeric_values.append(num)
                    except ValueError:
                        pass
            
            if len(numeric_values) > 3:
                return True
        
        return False
    
    def _is_quantity_column(self, col_name: str, values: List) -> bool:
        """Проверить, является ли колонка количеством"""
        quantity_keywords = ["кол", "колич", "штук", "вес", "объем"]
        
        if any(keyword in col_name for keyword in quantity_keywords):
            # Проверка на целые положительные числа
            int_count = 0
            for val in values[:10]:
                if val and str(val).strip():
                    try:
                        num = float(str(val).replace(',', '.').replace(' ', ''))
                        if num > 0 and num.is_integer() and num < 100000:
                            int_count += 1
                    except ValueError:
                        pass
            
            if int_count > 5:
                return True
        
        return False
    
    def _is_customer_column(self, col_name: str) -> bool:
        """Проверить, является ли колонка клиентом"""
        customer_keywords = ["клиент", "контрагент", "покупатель", "заказчик", "организация", "компания"]
        return any(keyword in col_name for keyword in customer_keywords)
    
    def _is_product_column(self, col_name: str) -> bool:
        """Проверить, является ли колонка товаром"""
        product_keywords = ["товар", "продукт", "номенклатур", "артикул", "наименован", "категор"]
        return any(keyword in col_name for keyword in product_keywords)
    
    def _detect_numbering_hierarchy(self, column_names: List[str]) -> Optional[HierarchyInfo]:
        """Обнаружить иерархию по нумерации"""
        numbering_pattern = re.compile(r'^(\d+)(\.(\d+))*$')
        
        levels = []
        for name in column_names:
            match = numbering_pattern.match(name.strip())
            if match:
                depth = name.count('.') + 1
                levels.append((name, depth))
        
        if len(levels) >= 2:
            max_depth = max(level[1] for level in levels)
            return HierarchyInfo(
                levels=[level[0] for level in sorted(levels, key=lambda x: x[1])],
                depth=max_depth,
                pattern="numbering",
                confidence=0.85
            )
        
        return None
    
    def _detect_indent_hierarchy(self, column_names: List[str]) -> Optional[HierarchyInfo]:
        """Обнаружить иерархию по отступам"""
        indented = []
        for name in column_names:
            leading_spaces = len(name) - len(name.lstrip(' '))
            if leading_spaces > 0:
                depth = leading_spaces // 2  # 2 пробела = 1 уровень
                indented.append((name.strip(), depth + 1))
        
        if len(indented) >= 2:
            max_depth = max(level[1] for level in indented)
            return HierarchyInfo(
                levels=[level[0] for level in sorted(indented, key=lambda x: x[1])],
                depth=max_depth,
                pattern="indent",
                confidence=0.80
            )
        
        return None
    
    def _detect_prefix_hierarchy(self, column_names: List[str]) -> Optional[HierarchyInfo]:
        """Обнаружить иерархию по префиксам"""
        prefix_levels = {}
        
        for name in column_names:
            if '-' in name:
                parts = name.split('-')
                if len(parts) >= 2:
                    prefix = parts[0].strip()
                    level = len(parts) - 1
                    if level not in prefix_levels:
                        prefix_levels[level] = []
                    prefix_levels[level].append(name.strip())
        
        if len(prefix_levels) >= 2:
            all_levels = []
            for level in sorted(prefix_levels.keys()):
                all_levels.extend(prefix_levels[level])
            
            return HierarchyInfo(
                levels=all_levels,
                depth=max(prefix_levels.keys()) + 1,
                pattern="prefix",
                confidence=0.75
            )
        
        return None
    
    def _build_llm_prompt(self, col_name: str, sample_values: List) -> str:
        """Построить промпт для LLM"""
        sample_str = ", ".join(str(v) for v in sample_values[:5] if v is not None)
        
        prompt = f"""
Ты - эксперт по анализу данных из 1С. Определи, что означает колонка с названием "{col_name}".

Примеры значений: {sample_str}

Возможные типы полей в 1С:
- revenue (Выручка, СуммаПродажи, Оборот)
- cost (Себестоимость, Затраты)
- quantity (Количество, Вес, Объём)
- customer (Клиент, Контрагент, Покупатель)
- product (Товар, Номенклатура, Артикул)
- date (Дата, Период)
- category (Категория, Группа, Вид)
- manager (Менеджер, Ответственный)
- region (Регион, Город, Область)
- warehouse (Склад, МестоХранения)

Верни ответ в формате JSON:
{{
  "mapped_field": "тип_поля",
  "confidence": 0.0-1.0,
  "data_type": "string|int|float|datetime",
  "reasoning": "краткое обоснование"
}}

Если не уверен, верни confidence < 0.5.
"""
        return prompt
    
    def _call_ollama(self, prompt: str) -> str:
        """Вызвать Ollama API"""
        import requests
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "max_tokens": 200
                    }
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json().get("response", "")
        except requests.exceptions.RequestException:
            # Ollama недоступен - возвращаем пустой ответ
            return ""
    
    def _parse_llm_response(self, response: str, col_name: str, sample_values: List) -> Optional[ColumnMapping]:
        """Распарсить ответ LLM"""
        import json
        
        # Извлекаем JSON из ответа
        json_match = re.search(r'\{[^}]*\}', response, re.DOTALL)
        if not json_match:
            return None
        
        try:
            data = json.loads(json_match.group())
            
            mapped_field = data.get("mapped_field", "unknown")
            confidence = float(data.get("confidence", 0.5))
            data_type = data.get("data_type", "string")
            
            # Валидация
            if mapped_field not in FIELD_MAPPINGS and mapped_field != "unknown":
                mapped_field = "unknown"
            
            return ColumnMapping(
                original_name=col_name,
                mapped_field=mapped_field,
                confidence=min(confidence, 0.7),  # LLM не даём выше 0.7
                detection_level=DetectionLevel.LLM,
                data_type=data_type,
                metadata={
                    "llm_reasoning": data.get("reasoning", ""),
                    "model": self.model
                }
            )
        except (json.JSONDecodeError, ValueError):
            return None
    
    def _get_llm_cache_key(self, col_name: str, sample_values: List) -> str:
        """Создать ключ для кэша LLM"""
        sample_str = ",".join(str(v) for v in sorted(sample_values[:5]) if v is not None)
        cache_input = f"{col_name}|{sample_str}"
        return hashlib.md5(cache_input.encode()).hexdigest()
    
    def get_mapping_summary(self, mappings: List[ColumnMapping]) -> Dict:
        """Получить сводку по маппингу для UI"""
        summary = {
            "total_columns": len(mappings),
            "high_confidence": 0,
            "medium_confidence": 0,
            "low_confidence": 0,
            "requires_review": [],
            "by_detection_level": {
                "dictionary": 0,
                "heuristic": 0,
                "llm": 0
            }
        }
        
        for mapping in mappings:
            if mapping.confidence >= 0.8:
                summary["high_confidence"] += 1
            elif mapping.confidence >= 0.6:
                summary["medium_confidence"] += 1
            else:
                summary["low_confidence"] += 1
                summary["requires_review"].append(mapping.to_dict())
            
            summary["by_detection_level"][mapping.detection_level.value] += 1
        
        return summary
