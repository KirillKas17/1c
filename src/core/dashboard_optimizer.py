"""
Dashboard Optimizer - защита от перегрузки и приоритизация компонентов

Принципы:
- Максимум 12 компонентов на главный экран
- Приоритет по важности метрик
- Группировка по вкладкам при превышении лимита
- Progressive disclosure (сначала главное, детали по клику)
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class ComponentType(Enum):
    KPI_CARD = "kpi_card"
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    PARETO_CHART = "pareto_chart"
    HEATMAP_MAP = "heatmap_map"
    COHORT_TABLE = "cohort_table"
    WATERFALL_CHART = "waterfall_chart"
    TABLE = "table"
    FORECAST_CHART = "forecast_chart"


@dataclass
class DashboardComponent:
    """Компонент дашборда"""
    component_id: str
    component_type: ComponentType
    title: str
    rule_id: str
    priority: int  # 1-10, 10 = критически важно
    data: Any
    config: Dict[str, Any] = field(default_factory=dict)
    tab: str = "main"  # Вкладка для группировки
    is_collapsible: bool = False
    
    def to_dict(self) -> Dict:
        return {
            'component_id': self.component_id,
            'component_type': self.component_type.value,
            'title': self.title,
            'rule_id': self.rule_id,
            'priority': self.priority,
            'data': self.data,
            'config': self.config,
            'tab': self.tab,
            'is_collapsible': self.is_collapsible
        }


class DashboardOptimizer:
    """Оптимизатор дашборда - защита от перегрузки"""
    
    # Лимиты компонентов
    MAX_KPI_CARDS = 6
    MAX_CHARTS = 8
    MAX_FILTERS = 5
    MAX_TABLE_ROWS = 100
    AUTO_TAB_THRESHOLD = 12  # Если компонентов >12 — создаём вкладки
    
    # Приоритеты типов компонентов
    COMPONENT_PRIORITY = {
        ComponentType.KPI_CARD: 10,
        ComponentType.LINE_CHART: 8,
        ComponentType.BAR_CHART: 7,
        ComponentType.PARETO_CHART: 6,
        ComponentType.FORECAST_CHART: 6,
        ComponentType.HEATMAP_MAP: 5,
        ComponentType.WATERFALL_CHART: 4,
        ComponentType.COHORT_TABLE: 3,
        ComponentType.PIE_CHART: 2,
        ComponentType.TABLE: 1
    }
    
    # Категории для группировки по вкладкам
    TAB_CATEGORIES = {
        "main": ["finance", "customers"],
        "products": ["products"],
        "time_series": ["time_series", "forecast"],
        "geo": ["geo"]
    }
    
    def __init__(self):
        self.components: List[DashboardComponent] = []
        self.tabs: Dict[str, List[DashboardComponent]] = {"main": []}
    
    def add_component(self, component: DashboardComponent) -> None:
        """Добавить компонент с учётом приоритета"""
        self.components.append(component)
    
    def optimize(self, components: List[DashboardComponent]) -> Dict[str, List[DashboardComponent]]:
        """
        Оптимизация набора компонентов
        
        Returns:
            Словарь {tab_name: [components]}
        """
        if not components:
            return {"main": []}
        
        # Сортировка по приоритету (правило + тип компонента)
        sorted_components = sorted(
            components,
            key=lambda c: (c.priority, self.COMPONENT_PRIORITY.get(c.component_type, 0)),
            reverse=True
        )
        
        # Разделение по типам
        kpi_cards = [c for c in sorted_components if c.component_type == ComponentType.KPI_CARD]
        charts = [c for c in sorted_components if c.component_type != ComponentType.KPI_CARD and c.component_type != ComponentType.TABLE]
        tables = [c for c in sorted_components if c.component_type == ComponentType.TABLE]
        
        # Применение лимитов
        limited_kpi = kpi_cards[:self.MAX_KPI_CARDS]
        limited_charts = charts[:self.MAX_CHARTS]
        limited_tables = tables[:3]  # Максимум 3 таблицы
        
        # Объединение
        optimized = limited_kpi + limited_charts + limited_tables
        
        # Проверка необходимости вкладок
        if len(optimized) > self.AUTO_TAB_THRESHOLD:
            return self._group_by_tabs(optimized)
        else:
            return {"main": optimized}
    
    def _group_by_tabs(self, components: List[DashboardComponent]) -> Dict[str, List[DashboardComponent]]:
        """Группировка компонентов по вкладкам"""
        tabs = {}
        
        for component in components:
            # Определение вкладки по категории правила
            assigned_tab = "main"
            
            for tab_name, categories in self.TAB_CATEGORIES.items():
                # Здесь можно проверить категорию правила
                # Пока упрощённо по названию
                if any(cat in component.rule_id.lower() for cat in categories):
                    assigned_tab = tab_name
                    break
            
            if assigned_tab not in tabs:
                tabs[assigned_tab] = []
            
            tabs[assigned_tab].append(component)
        
        # Сортировка вкладок (main всегда первая)
        ordered_tabs = {"main": tabs.get("main", [])}
        for tab_name, comps in tabs.items():
            if tab_name != "main":
                ordered_tabs[tab_name] = comps
        
        return ordered_tabs
    
    @classmethod
    def from_rule_results(cls, rule_results: List[Any], field_mapping: Dict[str, str]) -> 'DashboardOptimizer':
        """
        Создание оптимизатора из результатов расчёта правил
        
        Args:
            rule_results: Список RuleResult из MetricsEngine
            field_mapping: Маппинг полей
        """
        optimizer = cls()
        
        for result in rule_results:
            if not result.is_applicable or result.value is None:
                continue
            
            # Определение типа компонента из UI конфига правила
            ui_config = getattr(result, 'ui_config', {})
            component_type_str = ui_config.get('component', 'kpi_card')
            
            try:
                component_type = ComponentType(component_type_str)
            except ValueError:
                component_type = ComponentType.KPI_CARD
            
            # Преобразование значения в данные для визуализации
            if isinstance(result.value, dict):
                # Для сложных структур (ABC-анализ, когорты)
                data = result.value
            else:
                # Для простых метрик
                data = {
                    'value': result.value,
                    'unit': result.unit,
                    'comparison': result.comparison,
                    'trend': result.trend,
                    'risk_flags': result.risk_flags
                }
            
            component = DashboardComponent(
                component_id=f"comp_{result.rule_id}",
                component_type=component_type,
                title=result.name,
                rule_id=result.rule_id,
                priority=getattr(result, 'priority', 5),
                data=data,
                config=ui_config.get('config', {}),
                is_collapsible=component_type != ComponentType.KPI_CARD
            )
            
            optimizer.add_component(component)
        
        return optimizer


class FilterManager:
    """Менеджер фильтров дашборда"""
    
    SUPPORTED_FILTERS = {
        'date_range': {'type': 'daterange', 'required': False},
        'category': {'type': 'multiselect', 'required': False},
        'region': {'type': 'multiselect', 'required': False},
        'customer_segment': {'type': 'select', 'required': False},
        'product_group': {'type': 'multiselect', 'required': False},
        'manager': {'type': 'select', 'required': False}
    }
    
    def __init__(self, df, field_mapping: Dict[str, str]):
        self.df = df
        self.field_mapping = field_mapping
        self.active_filters: Dict[str, Any] = {}
    
    def get_available_filters(self) -> List[str]:
        """Получить список доступных фильтров для данных"""
        available = []
        
        for filter_name, config in self.SUPPORTED_FILTERS.items():
            field_name = self._get_field_for_filter(filter_name)
            if field_name and field_name in self.df.columns:
                available.append(filter_name)
        
        return available
    
    def _get_field_for_filter(self, filter_name: str) -> Optional[str]:
        """Получить имя поля для фильтра"""
        mapping = {
            'date_range': 'date',
            'category': 'category',
            'region': 'region',
            'customer_segment': 'customer_segment',
            'product_group': 'product_group',
            'manager': 'manager'
        }
        field_std = mapping.get(filter_name)
        return self.field_mapping.get(field_std) if field_std else None
    
    def get_filter_options(self, filter_name: str) -> List[Any]:
        """Получить варианты значений для фильтра"""
        field_name = self._get_field_for_filter(filter_name)
        
        if not field_name or field_name not in self.df.columns:
            return []
        
        series = self.df[field_name]
        
        if series.dtype == 'datetime64[ns]' or 'date' in filter_name:
            # Для дат返回 мин/макс
            return [series.min(), series.max()]
        else:
            # Для категорий返回 уникальные значения
            return sorted(series.dropna().unique().tolist())[:50]  # Максимум 50 вариантов
    
    def apply_filter(self, filter_name: str, value: Any) -> None:
        """Применить фильтр"""
        self.active_filters[filter_name] = value
    
    def clear_filters(self) -> None:
        """Очистить все фильтры"""
        self.active_filters = {}
    
    def get_filtered_df(self) -> Any:
        """Получить отфильтрованный DataFrame"""
        # Упрощённая реализация
        # В полной версии нужно применять каждый фильтр к df
        return self.df


# Пример использования
if __name__ == "__main__":
    # Тестирование
    print("Dashboard Optimizer готов к использованию")
    print(f"Лимиты: KPI={DashboardOptimizer.MAX_KPI_CARDS}, Charts={DashboardOptimizer.MAX_CHARTS}")
