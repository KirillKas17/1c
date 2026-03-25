"""
Модуль для обработки иерархических структур в Excel файлах.
Поддерживает парсинг вложенных данных типа:
"Отдел продаж - Москва - Менеджер Иванов И.И. - Клиент Смирнов А.А."

Также определяет типы контрагентов (Юрлицо, Физлицо, ИП, Самозанятый)
и корректно разделяет менеджеров от клиентов.
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CounterpartyType(Enum):
    """Типы контрагентов"""
    LEGAL_ENTITY = "legal_entity"      # Юридическое лицо (ООО, АО, ПАО и т.д.)
    INDIVIDUAL_ENTREPRENEUR = "ip"     # Индивидуальный предприниматель (ИП)
    SELF_EMPLOYED = "self_employed"    # Самозанятый
    INDIVIDUAL = "individual"          # Физическое лицо (не ИП)
    UNKNOWN = "unknown"                # Не определен


@dataclass
class HierarchicalEntity:
    """Представляет иерархически извлеченную сущность"""
    level: str                    # Уровень иерархии (department, city, manager, client)
    value: str                    # Значение
    confidence: float             # Уверенность извлечения
    counterparty_type: Optional[CounterpartyType] = None  # Тип контрагента (если применимо)
    inn: Optional[str] = None     # ИНН (если найден)
    parent: Optional['HierarchicalEntity'] = None  # Родительский элемент
    children: List['HierarchicalEntity'] = None  # Дочерние элементы
    
    def __post_init__(self):
        if self.children is None:
            self.children = []


class HierarchyParser:
    """
    Парсер для обработки иерархических структур в данных.
    
    Поддерживает форматы:
    - "Отдел продаж - Москва - Менеджер Иванов - Клиент Смирнов"
    - "Департамент > Регион > Менеджер > Контрагент"
    - "Строка с разделителями: / | \\ | ;"
    """
    
    # Разделители иерархии (по убыванию приоритета)
    SEPARATORS = [
        r'\s+-\s+',           # " - " (тире с пробелами)
        r'\s+>\s+',           # " > "
        r'\s+/\s+',           # " / "
        r'\s+\|\s+',          # " | "
        r'\s+;\s+',           # " ; "
        r'\t+',               # Табуляция
        r'\n+',               # Новая строка
    ]
    
    # Маркеры уровней иерархии
    LEVEL_MARKERS = {
        'department': [
            r'отдел', r'департамент', r'управление', r'служба', r'цех',
            r'подразделение', r'сектор', r'группа', r'бюро', r'филиал',
            r'department', r'division', r'sector', r'branch', r'team'
        ],
        'city': [
            r'город', r'г\\.', r'регион', r'область', r'край', r'республика',
            r'москва', r'спб', r'санкт[- ]?петербург', r'казань', r'екатеринбург',
            r'новосибирск', r'челябинск', r'самара', r'краснодар',
            r'city', r'region', r'moscow', r'saint petersburg'
        ],
        'manager': [
            r'менеджер', r'сотрудник', r'специалист', r'руководитель',
            r'директор', r'начальник', r'заместитель', r'куратор',
            r'ответственный', r'агент', r'представитель', r'продавец',
            r'manager', r'specialist', r'director', r'agent', r'representative'
        ],
        'client': [
            r'клиент', r'контрагент', r'заказчик', r'покупатель', r'партнер',
            r'организация', r'компания', r'предприятие', r'фирма',
            r'абонент', r'должник', r'дебитор', r'получатель',
            r'client', r'customer', r'partner', r'company', r'organization',
            r'counterparty'
        ]
    }
    
    # Паттерны для определения типа контрагента
    COUNTERPARTY_PATTERNS = {
        CounterpartyType.LEGAL_ENTITY: [
            r'\bООО\b', r'\bАО\b', r'\bПАО\b', r'\bЗАО\b', r'\bОАО\b',
            r'\bНКО\b', r'\bФГУП\b', r'\bМУП\b', r'\bГБУ\b', r'\bМБУ\b',
            r'\bИФНС\b', r'\bПФР\b', r'\bФСС\b', r'\bМинистерство\b',
            r'\blimited\s+liability\s+company\b', r'\bllc\b', r'\binc\b',
            r'\bcorporation\b', r'\bcorp\b', r'\bjoint\s+stock\s+company\b',
            r'\bобщество\s+с\s+ограниченной\s+ответственностью\b',
            r'\bакционерное\s+общество\b', r'\bпубличное\s+акционерное\s+общество\b'
        ],
        CounterpartyType.INDIVIDUAL_ENTREPRENEUR: [
            r'\bИП\b', r'\bиндивидуальный\s+предприниматель\b',
            r'\bпредприниматель\b', r'\bprivate\s+entrepreneur\b',
            r'\bsole\s+proprietorship\b'
        ],
        CounterpartyType.SELF_EMPLOYED: [
            r'\bсамозанятый\b', r'\bсамозанятая\b', r'\bсамозанятые\b',
            r'\bплательщик\s+нпд\b', r'\bнпд\b',
            r'\bself[- ]?employed\b'
        ],
        CounterpartyType.INDIVIDUAL: [
            # Физлица определяются по отсутствию признаков юрлица/ИП и наличию ФИО
            r'^[А-Я][а-яё]+\s+[А-Я][а-яё]+\s+[А-Я][а-яё]+$',  # ФИО полностью
            r'^[А-Я][а-яё]+\s+[А-Я]\.[А-Я]\.$',  # Фамилия И.О.
            r'^[А-Я]\.[А-Я]\.[а-яё]+$'  # И.О. Фамилия
        ]
    }
    
    # Города России (для точного определения уровня "город")
    RUSSIAN_CITIES = [
        'москва', 'санкт-петербург', 'спб', 'новосибирск', 'екатеринбург',
        'казань', 'нижний новгород', 'челябинск', 'самара', 'омск',
        'ростов-на-дону', 'уфа', 'красноярск', 'воронеж', 'пермь',
        'волгоград', 'краснодар', 'саратов', 'тюмень', 'тольятти',
        'ижевск', 'барнаул', 'ульяновск', 'иркутск', 'хабаровск',
        'ярославль', 'владивосток', 'махачкала', 'томск', 'оренбург',
        'кемерово', 'новокузнецк', 'рязань', 'астрахань', 'пенза',
        'липецк', 'киров', 'тула', 'севастополь', 'симферополь',
        'набережные челны', 'балашшиха', 'калининград', 'курск',
        'мурманск', 'архангельск', 'сургут', 'череповец', 'вологда'
    ]
    
    def __init__(self):
        # Компилируем паттерны для производительности
        self.separator_patterns = [re.compile(pat, re.IGNORECASE) for pat in self.SEPARATORS]
        
        self.level_patterns = {}
        for level, markers in self.LEVEL_MARKERS.items():
            pattern = r'\b(' + '|'.join(markers) + r')\b'
            self.level_patterns[level] = re.compile(pattern, re.IGNORECASE)
        
        self.counterparty_patterns = {}
        for ctype, patterns in self.COUNTERPARTY_PATTERNS.items():
            combined = r'(?:' + '|'.join(patterns) + r')'
            self.counterparty_patterns[ctype] = re.compile(combined, re.IGNORECASE)
    
    def parse_hierarchical_string(self, text: str) -> List[HierarchicalEntity]:
        """
        Разбирает иерархическую строку на компоненты.
        
        Args:
            text: Строка вида "Отдел - Город - Менеджер - Клиент"
        
        Returns:
            Список HierarchicalEntity от корня к листьям
        """
        if not text or not isinstance(text, str):
            return []
        
        text = text.strip()
        logger.debug(f"Парсинг иерархической строки: {text}")
        
        # Определяем разделитель
        separator = self._detect_separator(text)
        
        if separator:
            # Разделяем по найденному разделителю
            parts = re.split(separator, text)
        else:
            # Если разделитель не найден, считаем что это один элемент
            parts = [text]
        
        entities = []
        parent = None
        
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            
            # Определяем уровень иерархии
            level = self._detect_level(part, i, len(parts))
            
            # Определяем тип контрагента (если это уровень клиента)
            counterparty_type = None
            if level == 'client':
                counterparty_type = self._determine_counterparty_type(part)
            
            # Извлекаем ИНН если есть
            inn = self._extract_inn_from_text(part)
            
            entity = HierarchicalEntity(
                level=level,
                value=part,
                confidence=self._calculate_confidence(part, level),
                counterparty_type=counterparty_type,
                inn=inn,
                parent=parent
            )
            
            if parent:
                parent.children.append(entity)
            
            entities.append(entity)
            parent = entity
        
        logger.debug(f"Извлечено {len(entities)} уровней иерархии")
        return entities
    
    def _detect_separator(self, text: str) -> Optional[str]:
        """Определяет используемый разделитель"""
        for pattern in self.separator_patterns:
            if pattern.search(text):
                return pattern.pattern
        return None
    
    def _detect_level(self, text: str, position: int, total_parts: int) -> str:
        """
        Определяет уровень иерархии по тексту и позиции.
        
        Эвристика:
        - Первый элемент часто отдел/департамент
        - Второй может быть город/регион
        - Предпоследний часто менеджер
        - Последний часто клиент
        """
        text_lower = text.lower()
        
        # Проверяем явные маркеры уровней
        for level, pattern in self.level_patterns.items():
            if pattern.search(text):
                logger.debug(f"Уровень '{level}' определен по маркеру в тексте: {text}")
                return level
        
        # Проверяем является ли текст названием города
        for city in self.RUSSIAN_CITIES:
            if city in text_lower:
                logger.debug(f"Уровень 'city' определен по названию города: {text}")
                return 'city'
        
        # Эвристика по позиции
        if position == 0 and total_parts >= 3:
            # Первый элемент в длинной цепочке - скорее всего отдел
            return 'department'
        elif position == 1 and total_parts >= 3:
            # Второй элемент - возможно город
            return 'city'
        elif position == total_parts - 2:
            # Предпоследний - менеджер
            return 'manager'
        elif position == total_parts - 1:
            # Последний - клиент
            return 'client'
        
        # По умолчанию определяем по контексту
        if any(word in text_lower for word in ['менеджер', 'сотрудник', 'специалист']):
            return 'manager'
        elif any(word in text_lower for word in ['клиент', 'контрагент', 'заказчик']):
            return 'client'
        
        # Если ничего не подошло, используем позицию
        if total_parts <= 2:
            return 'client' if position == total_parts - 1 else 'department'
        
        return 'unknown'
    
    def _determine_counterparty_type(self, text: str) -> CounterpartyType:
        """Определяет тип контрагента по тексту"""
        text_clean = text.strip()
        
        # Проверяем паттерны в порядке специфичности
        # Сначала ИП (самый специфичный)
        if self.counterparty_patterns[CounterpartyType.INDIVIDUAL_ENTREPRENEUR].search(text_clean):
            logger.debug(f"Определен ИП: {text_clean}")
            return CounterpartyType.INDIVIDUAL_ENTREPRENEUR
        
        # Затем самозанятые
        if self.counterparty_patterns[CounterpartyType.SELF_EMPLOYED].search(text_clean):
            logger.debug(f"Определен самозанятый: {text_clean}")
            return CounterpartyType.SELF_EMPLOYED
        
        # Затем юрлица
        if self.counterparty_patterns[CounterpartyType.LEGAL_ENTITY].search(text_clean):
            logger.debug(f"Определено юрлицо: {text_clean}")
            return CounterpartyType.LEGAL_ENTITY
        
        # Затем физлица по формату ФИО
        if self.counterparty_patterns[CounterpartyType.INDIVIDUAL].search(text_clean):
            logger.debug(f"Определено физлицо: {text_clean}")
            return CounterpartyType.INDIVIDUAL
        
        # По умолчанию неизвестно
        logger.debug(f"Тип контрагента не определен: {text_clean}")
        return CounterpartyType.UNKNOWN
    
    def _extract_inn_from_text(self, text: str) -> Optional[str]:
        """Извлекает ИНН из текста"""
        # Паттерн для ИНН (10 или 12 цифр)
        inn_pattern = r'\b(\d{10}|\d{12})\b'
        matches = re.findall(inn_pattern, text)
        
        if matches:
            inn = matches[0]
            logger.debug(f"Извлечен ИНН из текста: {inn}")
            return inn
        
        return None
    
    def _calculate_confidence(self, text: str, level: str) -> float:
        """Вычисляет уверенность определения уровня"""
        confidence = 0.5  # Базовая уверенность
        
        # Повышаем если есть явный маркер
        if level in self.level_patterns:
            if self.level_patterns[level].search(text):
                confidence += 0.5  # Увеличили с 0.3 до 0.5 для большей уверенности
        
        # Повышаем если это город из списка
        if level == 'city':
            for city in self.RUSSIAN_CITIES:
                if city in text.lower():
                    confidence += 0.2
                    break
        
        # Повышаем если определен тип контрагента
        if level == 'client':
            ctype = self._determine_counterparty_type(text)
            if ctype != CounterpartyType.UNKNOWN:
                confidence += 0.15
        
        # Повышаем если найден ИНН
        if self._extract_inn_from_text(text):
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def get_hierarchy_as_dict(self, entities: List[HierarchicalEntity]) -> Dict[str, Any]:
        """
        Преобразует список иерархических сущностей в словарь.
        
        Returns:
            Словарь вида:
            {
                'department': {...},
                'city': {...},
                'manager': {...},
                'client': {...},
                'full_path': 'Отдел - Город - Менеджер - Клиент'
            }
        """
        result = {}
        path_parts = []
        
        for entity in entities:
            level_data = {
                'value': entity.value,
                'confidence': entity.confidence,
                'counterparty_type': entity.counterparty_type.value if entity.counterparty_type else None,
                'inn': entity.inn
            }
            result[entity.level] = level_data
            path_parts.append(entity.value)
        
        result['full_path'] = ' - '.join(path_parts)
        result['levels_count'] = len(entities)
        
        return result
    
    def is_manager(self, text: str) -> bool:
        """Проверяет, является ли текст именем менеджера"""
        text_lower = text.lower().strip()
        
        # Прямая проверка маркеров менеджера
        manager_markers = [
            'менеджер', 'сотрудник', 'специалист', 'руководитель',
            'директор', 'начальник', 'заместитель', 'куратор',
            'account manager', 'sales manager', 'representative'
        ]
        for marker in manager_markers:
            if marker in text_lower:
                return True
        
        # Проверка паттерном
        if self.level_patterns['manager'].search(text):
            return True
            
        return False
    
    def is_client(self, text: str) -> bool:
        """Проверяет, является ли текст именем клиента"""
        text_lower = text.lower().strip()
        
        # Прямая проверка маркеров клиента
        client_markers = [
            'клиент', 'контрагент', 'заказчик', 'покупатель',
            'партнер', 'абонент', 'получатель', 'грузополучатель',
            'customer', 'client', 'partner', 'buyer'
        ]
        for marker in client_markers:
            if marker in text_lower:
                return True
        
        # Проверка паттерном
        if self.level_patterns['client'].search(text):
            return True
        
        # Проверка на тип контрагента (ООО, ИП и т.д.) - это точно клиент
        if self._determine_counterparty_type(text) != CounterpartyType.UNKNOWN:
            return True
            
        return False
    
    def distinguish_manager_from_client(self, manager_text: str, client_text: str) -> Tuple[str, str]:
        """
        Надежно различает менеджера и клиента даже если оба - физлица.
        
        Эвристики:
        1. Менеджеры чаще имеют титулы (менеджер, специалист и т.д.)
        2. Клиенты чаще имеют признаки компаний (ООО, ИП и т.д.)
        3. Если оба физлица - смотрим на контекст и позицию
        """
        manager_is_explicit = bool(self.level_patterns['manager'].search(manager_text))
        client_is_explicit = bool(self.level_patterns['client'].search(client_text))
        
        # Если есть явные маркеры - используем их
        if manager_is_explicit and not client_is_explicit:
            return manager_text, client_text
        if client_is_explicit and not manager_is_explicit:
            return client_text, manager_text
        
        # Если оба без маркеров - определяем по типу контрагента
        manager_type = self._determine_counterparty_type(manager_text)
        client_type = self._determine_counterparty_type(client_text)
        
        # Клиент чаще бывает юрлицом или ИП
        if client_type in [CounterpartyType.LEGAL_ENTITY, CounterpartyType.INDIVIDUAL_ENTREPRENEUR]:
            if manager_type == CounterpartyType.INDIVIDUAL:
                return manager_text, client_text
        
        # Менеджер чаще просто физлицо без статуса ИП
        if manager_type == CounterpartyType.INDIVIDUAL and client_type == CounterpartyType.UNKNOWN:
            return manager_text, client_text
        
        # По умолчанию оставляем как есть
        return manager_text, client_text
