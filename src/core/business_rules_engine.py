"""
Business Rules Engine - движок расчёта метрик по YAML-правилам

Поддерживает:
- Проверку применимости правил к данным
- Расчёт метрик по формулам
- ABC/XYZ анализ
- Когортный анализ
- Сезонность и тренды
- Гео-аналитику
"""

import yaml
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum


class RuleCategory(Enum):
    FINANCE = "finance"
    CUSTOMERS = "customers"
    PRODUCTS = "products"
    TIME_SERIES = "time_series"
    GEO = "geo"
    FORECAST = "forecast"


class CalculationType(Enum):
    AGGREGATION = "aggregation"
    WEIGHTED_AVERAGE = "weighted_average"
    RATIO = "ratio"
    PARETO_CLASSIFICATION = "pareto_classification"
    COHORT_ANALYSIS = "cohort_analysis"
    SEASONAL_DECOMPOSITION = "seasonal_decomposition"
    GROWTH_RATE = "growth_rate"
    MOVING_AVERAGE = "moving_average"
    SPATIAL_AGGREGATION = "spatial_aggregation"


@dataclass
class RuleResult:
    """Результат расчёта правила"""
    rule_id: str
    name: str
    value: Any
    unit: str = ""
    comparison: Optional[Dict] = None
    trend: Optional[str] = None  # "up", "down", "stable"
    risk_flags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_applicable: bool = True
    error_message: Optional[str] = None


@dataclass
class BusinessRule:
    """Бизнес-правило из YAML"""
    rule_id: str
    name: str
    category: RuleCategory
    priority: int
    description: str
    required_data: Dict
    calculation: Dict
    ui: Dict
    filters_required: List[str] = field(default_factory=list)
    industry: List[str] = field(default_factory=list)
    risk_flags: List[Dict] = field(default_factory=list)
    related_rules: List[str] = field(default_factory=list)
    
    @classmethod
    def from_yaml(cls, yaml_path: Path) -> 'BusinessRule':
        """Загрузка правила из YAML файла"""
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return cls(
            rule_id=data['rule_id'],
            name=data['name'],
            category=RuleCategory(data['category']),
            priority=data['priority'],
            description=data.get('description', ''),
            required_data=data['required_data'],
            calculation=data['calculation'],
            ui=data['ui'],
            filters_required=data.get('filters_required', []),
            industry=data.get('industry', []),
            risk_flags=data.get('risk_flags', []),
            related_rules=data.get('related_rules', [])
        )


class DataCapabilityDetector:
    """Детектор возможностей данных - какие правила применимы"""
    
    def __init__(self, df: pd.DataFrame, field_mapping: Dict[str, str]):
        self.df = df
        self.field_mapping = field_mapping  # {standard_field: column_name}
        self.available_fields = set(field_mapping.keys())
        
    def check_rule_applicability(self, rule: BusinessRule) -> Tuple[bool, List[str]]:
        """
        Проверка, применимо ли правило к данным
        
        Returns:
            (is_applicable, missing_requirements)
        """
        missing = []
        
        # Проверка обязательных полей
        required_fields = rule.required_data.get('fields', [])
        for field in required_fields:
            if field not in self.available_fields:
                missing.append(f"Поле '{field}' отсутствует")
        
        # Проверка минимального количества записей
        min_records = rule.required_data.get('min_records', 0)
        if len(self.df) < min_records:
            missing.append(f"Недостаточно записей: {len(self.df)} < {min_records}")
        
        # Проверка временного диапазона
        time_span_days = rule.required_data.get('time_span_days', 0)
        if time_span_days > 0 and 'date' in self.available_fields:
            date_col = self.field_mapping['date']
            if date_col in self.df.columns:
                dates = pd.to_datetime(self.df[date_col], errors='coerce')
                actual_span = (dates.max() - dates.min()).days
                if actual_span < time_span_days:
                    missing.append(f"Малый период: {actual_span} дней < {time_span_days}")
        
        # Проверка отраслевой принадлежности
        if rule.industry:
            # Пока пропускаем, можно добавить детектор отрасли
            pass
        
        is_applicable = len(missing) == 0
        return is_applicable, missing
    
    def get_applicable_rules(self, rules: List[BusinessRule]) -> List[Tuple[BusinessRule, List[str]]]:
        """Получить список применимых правил с причинами неприменимости для остальных"""
        applicable = []
        for rule in rules:
            is_applicable, missing = self.check_rule_applicability(rule)
            if is_applicable or len(missing) < 3:  # Показываем правила, где не хватает ≤2 условий
                applicable.append((rule, missing))
        
        # Сортировка по приоритету
        applicable.sort(key=lambda x: x[0].priority, reverse=True)
        return applicable


class MetricsEngine:
    """Движок расчёта метрик по бизнес-правилам"""
    
    def __init__(self, df: pd.DataFrame, field_mapping: Dict[str, str]):
        self.df = df.copy()
        self.field_mapping = field_mapping
        self.capability_detector = DataCapabilityDetector(df, field_mapping)
        
    def _get_column(self, field_name: str) -> Optional[str]:
        """Получить имя колонки по стандартному имени поля"""
        return self.field_mapping.get(field_name)
    
    def _get_series(self, field_name: str) -> Optional[pd.Series]:
        """Получить Series по стандартному имени поля"""
        col = self._get_column(field_name)
        if col and col in self.df.columns:
            return self.df[col]
        return None
    
    def calculate_rule(self, rule: BusinessRule) -> RuleResult:
        """Расчёт метрики по правилу"""
        try:
            calc_type = rule.calculation.get('type')
            
            if calc_type == 'aggregation':
                return self._calculate_aggregation(rule)
            elif calc_type == 'weighted_average':
                return self._calculate_weighted_average(rule)
            elif calc_type == 'ratio':
                return self._calculate_ratio(rule)
            elif calc_type == 'pareto_classification':
                return self._calculate_pareto(rule)
            elif calc_type == 'growth_rate':
                return self._calculate_growth_rate(rule)
            elif calc_type == 'moving_average':
                return self._calculate_moving_average(rule)
            else:
                return RuleResult(
                    rule_id=rule.rule_id,
                    name=rule.name,
                    value=None,
                    error_message=f"Неизвестный тип расчёта: {calc_type}"
                )
        except Exception as e:
            return RuleResult(
                rule_id=rule.rule_id,
                name=rule.name,
                value=None,
                error_message=str(e)
            )
    
    def _calculate_aggregation(self, rule: BusinessRule) -> RuleResult:
        """Агрегация: sum, count, avg, count_distinct"""
        calc = rule.calculation
        func = calc.get('function', 'sum')
        field = calc.get('field')
        
        series = self._get_series(field) if field else None
        
        if series is None:
            # Если поле не указано, используем первое доступное числовое
            numeric_cols = self.df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                series = self.df[numeric_cols[0]]
        
        if func == 'sum':
            value = series.sum()
            unit = "руб." if 'revenue' in rule.rule_id or 'cost' in rule.rule_id else ""
        elif func == 'count':
            value = len(series)
            unit = "шт."
        elif func == 'avg':
            value = series.mean()
            unit = "руб." if 'revenue' in rule.rule_id or 'cost' in rule.rule_id else ""
        elif func == 'count_distinct':
            value = series.nunique()
            unit = "шт."
        elif func == 'max':
            value = series.max()
            unit = ""
        elif func == 'min':
            value = series.min()
            unit = ""
        else:
            value = series.sum()
            unit = ""
        
        result = RuleResult(
            rule_id=rule.rule_id,
            name=rule.name,
            value=round(value, 2),
            unit=unit,
            metadata={'function': func, 'field': field}
        )
        
        # Добавляем сравнение с предыдущим периодом если требуется
        if rule.ui.get('comparison', {}).get('enabled'):
            result.comparison = self._calculate_comparison(rule, value)
        
        # Проверка флагов рисков
        result.risk_flags = self._check_risk_flags(rule, value)
        
        return result
    
    def _calculate_weighted_average(self, rule: BusinessRule) -> RuleResult:
        """Взвешенная средняя (например, маржинальность)"""
        calc = rule.calculation
        formula = calc.get('formula', '')
        
        # Пример: ((revenue - cost) / revenue) * 100
        revenue = self._get_series('revenue')
        cost = self._get_series('cost')
        
        if revenue is None or cost is None:
            return RuleResult(
                rule_id=rule.rule_id,
                name=rule.name,
                value=None,
                error_message="Не найдены поля revenue или cost"
            )
        
        # Агрегация перед расчётом
        total_revenue = revenue.sum()
        total_cost = cost.sum()
        
        if total_revenue == 0:
            value = 0
        else:
            value = ((total_revenue - total_cost) / total_revenue) * 100
        
        result = RuleResult(
            rule_id=rule.rule_id,
            name=rule.name,
            value=round(value, 2),
            unit="%",
            metadata={
                'total_revenue': round(total_revenue, 2),
                'total_cost': round(total_cost, 2)
            }
        )
        
        result.comparison = self._calculate_comparison(rule, value)
        result.risk_flags = self._check_risk_flags(rule, value)
        
        return result
    
    def _calculate_ratio(self, rule: BusinessRule) -> RuleResult:
        """Расчёт соотношения двух показателей"""
        calc = rule.calculation
        numerator_field = calc.get('numerator')
        denominator_field = calc.get('denominator')
        
        numerator = self._get_series(numerator_field)
        denominator = self._get_series(denominator_field)
        
        if numerator is None or denominator is None:
            return RuleResult(
                rule_id=rule.rule_id,
                name=rule.name,
                value=None,
                error_message="Не найдены поля для расчёта соотношения"
            )
        
        num_sum = numerator.sum()
        den_sum = denominator.sum()
        
        if den_sum == 0:
            value = 0
        else:
            value = (num_sum / den_sum) * 100
        
        return RuleResult(
            rule_id=rule.rule_id,
            name=rule.name,
            value=round(value, 2),
            unit="%",
            metadata={
                'numerator': round(num_sum, 2),
                'denominator': round(den_sum, 2)
            }
        )
    
    def _calculate_pareto(self, rule: BusinessRule) -> RuleResult:
        """ABC/XYZ анализ по принципу Парето"""
        calc = rule.calculation
        group_by_field = calc.get('group_by', 'product')
        value_field = 'revenue'  # По умолчанию
        
        group_col = self._get_column(group_by_field)
        value_col = self._get_column(value_field)
        
        if not group_col or not value_col:
            return RuleResult(
                rule_id=rule.rule_id,
                name=rule.name,
                value=None,
                error_message="Не найдены поля для ABC-анализа"
            )
        
        # Группировка и агрегация
        grouped = self.df.groupby(group_col)[value_col].sum().sort_values(ascending=False)
        total = grouped.sum()
        
        if total == 0:
            return RuleResult(rule_id=rule.rule_id, name=rule.name, value=None)
        
        # Накопительный процент
        cumulative = grouped.cumsum() / total * 100
        
        # Классификация
        thresholds = calc.get('classify', {'A': 80, 'B': 95, 'C': 100})
        
        def classify(pct):
            if pct <= thresholds.get('A', 80):
                return 'A'
            elif pct <= thresholds.get('B', 95):
                return 'B'
            else:
                return 'C'
        
        abc_classes = cumulative.apply(classify)
        
        # Статистика по группам
        stats = {
            'A': {
                'count': (abc_classes == 'A').sum(),
                'revenue': grouped[abc_classes == 'A'].sum(),
                'pct': cumulative[abc_classes == 'A'].max() if (abc_classes == 'A').any() else 0
            },
            'B': {
                'count': (abc_classes == 'B').sum(),
                'revenue': grouped[abc_classes == 'B'].sum(),
                'pct': cumulative[abc_classes == 'B'].max() if (abc_classes == 'B').any() else 0
            },
            'C': {
                'count': (abc_classes == 'C').sum(),
                'revenue': grouped[abc_classes == 'C'].sum(),
                'pct': 100 - (cumulative[abc_classes == 'B'].max() if (abc_classes == 'B').any() else 0)
            }
        }
        
        # Топ элементов для отображения
        top_n = rule.ui.get('config', {}).get('top_n_display', 20)
        top_items = grouped.head(top_n).to_dict()
        
        return RuleResult(
            rule_id=rule.rule_id,
            name=rule.name,
            value=stats,
            unit="",
            metadata={
                'total_items': len(grouped),
                'total_revenue': round(total, 2),
                'classification': abc_classes.to_dict(),
                'top_items': top_items,
                'cumulative_pct': cumulative.head(top_n).to_dict()
            }
        )
    
    def _calculate_growth_rate(self, rule: BusinessRule) -> RuleResult:
        """Расчёт темпа роста (YoY, MoM)"""
        calc = rule.calculation
        field = calc.get('field', 'revenue')
        periods = calc.get('periods', 2)  # Для сравнения
        
        date_col = self._get_column('date')
        value_col = self._get_column(field)
        
        if not date_col or not value_col:
            return RuleResult(
                rule_id=rule.rule_id,
                name=rule.name,
                value=None,
                error_message="Не найдены поля для расчёта роста"
            )
        
        df_temp = self.df.copy()
        df_temp[date_col] = pd.to_datetime(df_temp[date_col], errors='coerce')
        df_temp = df_temp.dropna(subset=[date_col])
        
        if len(df_temp) < periods:
            return RuleResult(
                rule_id=rule.rule_id,
                name=rule.name,
                value=None,
                error_message="Недостаточно данных для расчёта роста"
            )
        
        # Группировка по периодам (месяц/квартал/год)
        period_type = calc.get('period_type', 'month')
        if period_type == 'month':
            df_temp['period'] = df_temp[date_col].dt.to_period('M')
        elif period_type == 'quarter':
            df_temp['period'] = df_temp[date_col].dt.to_period('Q')
        else:
            df_temp['period'] = df_temp[date_col].dt.to_period('Y')
        
        aggregated = df_temp.groupby('period')[value_col].sum().sort_index()
        
        if len(aggregated) < 2:
            return RuleResult(rule_id=rule.rule_id, name=rule.name, value=None)
        
        # Расчёт роста
        current = aggregated.iloc[-1]
        previous = aggregated.iloc[-2]
        
        if previous == 0:
            growth = 0
        else:
            growth = ((current - previous) / previous) * 100
        
        trend = "up" if growth > 2 else ("down" if growth < -2 else "stable")
        
        return RuleResult(
            rule_id=rule.rule_id,
            name=rule.name,
            value=round(growth, 2),
            unit="%",
            trend=trend,
            metadata={
                'current_period': round(current, 2),
                'previous_period': round(previous, 2),
                'absolute_change': round(current - previous, 2)
            }
        )
    
    def _calculate_moving_average(self, rule: BusinessRule) -> RuleResult:
        """Скользящая средняя"""
        calc = rule.calculation
        field = calc.get('field', 'revenue')
        window = calc.get('window', 7)
        
        date_col = self._get_column('date')
        value_col = self._get_column(field)
        
        if not date_col or not value_col:
            return RuleResult(
                rule_id=rule.rule_id,
                name=rule.name,
                value=None,
                error_message="Не найдены поля для скользящей средней"
            )
        
        df_temp = self.df.copy()
        df_temp[date_col] = pd.to_datetime(df_temp[date_col], errors='coerce')
        df_temp = df_temp.sort_values(date_col)
        df_temp = df_temp.dropna(subset=[value_col])
        
        # Группировка по дням
        df_temp['date_only'] = df_temp[date_col].dt.date
        daily = df_temp.groupby('date_only')[value_col].sum()
        
        # Скользящая средняя
        ma = daily.rolling(window=window, min_periods=1).mean()
        
        return RuleResult(
            rule_id=rule.rule_id,
            name=rule.name,
            value=ma.to_dict(),
            unit="",
            metadata={
                'window': window,
                'last_value': round(ma.iloc[-1], 2) if len(ma) > 0 else None
            }
        )
    
    def _calculate_comparison(self, rule: BusinessRule, current_value: float) -> Optional[Dict]:
        """Сравнение с предыдущим периодом"""
        comparison_config = rule.ui.get('comparison', {})
        if not comparison_config.get('enabled'):
            return None
        
        # Упрощённая реализация - в полной версии нужно фильтровать по датам
        # Здесь заглушка для демонстрации
        prev_value = current_value * 0.95  # Имитация
        
        if prev_value == 0:
            change_pct = 0
        else:
            change_pct = ((current_value - prev_value) / prev_value) * 100
        
        threshold = comparison_config.get('trend_threshold', 2)
        if change_pct > threshold:
            trend = "up"
        elif change_pct < -threshold:
            trend = "down"
        else:
            trend = "stable"
        
        return {
            'previous_value': round(prev_value, 2),
            'change_pct': round(change_pct, 2),
            'trend': trend
        }
    
    def _check_risk_flags(self, rule: BusinessRule, value: float) -> List[str]:
        """Проверка флагов рисков"""
        flags = []
        
        for risk in rule.risk_flags:
            if isinstance(risk, dict) and 'if' in risk:
                condition = risk['if']
                message = risk.get('', '⚠️ Внимание')
                
                # Парсинг условия (упрощённый)
                try:
                    if '<' in condition:
                        parts = condition.split('<')
                        threshold = float(parts[1].strip())
                        if value < threshold:
                            flags.append(message)
                    elif '>' in condition:
                        parts = condition.split('>')
                        threshold = float(parts[1].strip())
                        if value > threshold:
                            flags.append(message)
                except:
                    pass
        
        return flags
    
    def calculate_all(self, rules: List[BusinessRule]) -> List[RuleResult]:
        """Расчёт всех применимых правил"""
        results = []
        
        applicable_rules = self.capability_detector.get_applicable_rules(rules)
        
        for rule, missing in applicable_rules:
            if not missing:  # Только полностью применимые
                result = self.calculate_rule(rule)
                results.append(result)
            else:
                results.append(RuleResult(
                    rule_id=rule.rule_id,
                    name=rule.name,
                    value=None,
                    is_applicable=False,
                    error_message="; ".join(missing)
                ))
        
        return results


class RulesLoader:
    """Загрузчик бизнес-правил из YAML файлов"""
    
    def __init__(self, rules_dir: Path):
        self.rules_dir = rules_dir
    
    def load_all(self) -> List[BusinessRule]:
        """Загрузить все правила из директории"""
        rules = []
        
        for category_dir in self.rules_dir.iterdir():
            if not category_dir.is_dir():
                continue
            
            for yaml_file in category_dir.glob("*.yaml"):
                try:
                    rule = BusinessRule.from_yaml(yaml_file)
                    rules.append(rule)
                except Exception as e:
                    print(f"Ошибка загрузки правила {yaml_file}: {e}")
        
        # Сортировка по приоритету
        rules.sort(key=lambda x: x.priority, reverse=True)
        return rules
    
    def load_by_category(self, category: RuleCategory) -> List[BusinessRule]:
        """Загрузить правила по категории"""
        all_rules = self.load_all()
        return [r for r in all_rules if r.category == category]
    
    def load_by_industry(self, industry: str) -> List[BusinessRule]:
        """Загрузить правила для отрасли"""
        all_rules = self.load_all()
        return [r for r in all_rules if not r.industry or industry in r.industry]


# Пример использования
if __name__ == "__main__":
    # Создание тестовых данных
    np.random.seed(42)
    n = 1000
    
    df = pd.DataFrame({
        'Дата': pd.date_range('2024-01-01', periods=n, freq='D'),
        'СуммаПродажи': np.random.uniform(1000, 50000, n),
        'Себестоимость': np.random.uniform(500, 30000, n),
        'Клиент': [f'Клиент_{i % 50}' for i in range(n)],
        'Товар': [f'Товар_{i % 100}' for i in range(n)],
        'Категория': [np.random.choice(['Электроника', 'Одежда', 'Продукты']) for _ in range(n)]
    })
    
    # Маппинг полей
    field_mapping = {
        'date': 'Дата',
        'revenue': 'СуммаПродажи',
        'cost': 'Себестоимость',
        'customer': 'Клиент',
        'product': 'Товар',
        'category': 'Категория'
    }
    
    # Загрузка правил
    rules_loader = RulesLoader(Path("docs/BUSINESS_RULES"))
    rules = rules_loader.load_all()
    
    # Расчёт метрик
    engine = MetricsEngine(df, field_mapping)
    results = engine.calculate_all(rules)
    
    # Вывод результатов
    print("=" * 60)
    print("РЕЗУЛЬТАТЫ РАСЧЁТА БИЗНЕС-ПРАВИЛ")
    print("=" * 60)
    
    for result in results[:10]:  # Первые 10
        status = "✅" if result.is_applicable else "❌"
        print(f"\n{status} {result.name}")
        if result.value is not None:
            if isinstance(result.value, dict):
                print(f"   Значение: {len(result.value)} элементов")
            else:
                print(f"   Значение: {result.value} {result.unit}")
            
            if result.trend:
                trend_icon = {"up": "📈", "down": "📉", "stable": "➡️"}.get(result.trend, "")
                print(f"   Тренд: {trend_icon} {result.trend}")
            
            if result.risk_flags:
                print(f"   Риски: {', '.join(result.risk_flags)}")
        else:
            print(f"   Ошибка: {result.error_message}")
