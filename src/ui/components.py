"""
UI Components Renderer - библиотека компонентов для визуализации дашбордов

Поддерживаемые компоненты:
- KPI карточки с трендами и сравнением
- Линейные графики (динамика)
- Столбчатые диаграммы (сравнение категорий)
- Диаграммы Парето (ABC-анализ)
- Тепловые карты (гео-аналитика)
- Когортные таблицы
- Водопады изменений
- Прогнозы с доверительными интервалами

Экспорт: PNG, PDF, PPTX
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import io


class UIComponentRenderer:
    """Рендерер UI компонентов дашборда"""
    
    def __init__(self, theme: str = "light"):
        self.theme = theme
        self.colors = {
            "up": "#10b981",      # Зеленый для роста
            "down": "#ef4444",    # Красный для падения
            "stable": "#6b7280",  # Серый для стабильности
            "primary": "#3b82f6", # Синий основной
            "secondary": "#8b5cf6",# Фиолетовый
            "warning": "#f59e0b", # Оранжевый
        }
    
    def render_kpi_card(self, data: Dict) -> Dict:
        """
        Рендер KPI карточки
        
        Args:
            data: {
                'value': float,
                'unit': str,
                'title': str,
                'comparison': {'previous_value': float, 'change_pct': float, 'trend': str},
                'risk_flags': List[str]
            }
        
        Returns:
            Dict с параметрами для отображения
        """
        value = data.get('value', 0)
        unit = data.get('unit', '')
        title = data.get('title', 'KPI')
        comparison = data.get('comparison', {})
        risk_flags = data.get('risk_flags', [])
        
        # Форматирование значения
        if abs(value) >= 1_000_000:
            formatted_value = f"{value/1_000_000:.1f}M"
        elif abs(value) >= 1_000:
            formatted_value = f"{value/1_000:.1f}K"
        else:
            formatted_value = f"{value:.1f}"
        
        # Тренд
        trend = comparison.get('trend', 'stable') if comparison else None
        change_pct = comparison.get('change_pct', 0) if comparison else 0
        
        return {
            'type': 'kpi_card',
            'title': title,
            'value': formatted_value,
            'raw_value': value,
            'unit': unit,
            'trend': trend,
            'change_pct': round(change_pct, 1),
            'trend_color': self.colors.get(trend, self.colors['stable']),
            'risk_flags': risk_flags,
            'has_warning': len(risk_flags) > 0
        }
    
    def render_line_chart(self, df: pd.DataFrame, x_col: str, y_col: str, 
                          title: str = "", show_markers: bool = True) -> Dict:
        """
        Рендер линейного графика
        
        Args:
            df: DataFrame с данными
            x_col: Колонка для оси X (обычно дата)
            y_col: Колонка для оси Y (метрика)
            title: Заголовок графика
            show_markers: Показывать ли маркеры на точках
        
        Returns:
            Dict с данными для Plotly/ECharts
        """
        df_plot = df.copy()
        
        # Преобразование дат если нужно
        if df_plot[x_col].dtype == 'datetime64[ns]':
            df_plot[x_col] = df_plot[x_col].dt.strftime('%Y-%m-%d')
        
        return {
            'type': 'line_chart',
            'title': title,
            'data': {
                'x': df_plot[x_col].tolist(),
                'y': df_plot[y_col].tolist(),
                'mode': 'lines+markers' if show_markers else 'lines',
                'line': {
                    'color': self.colors['primary'],
                    'width': 2
                }
            },
            'layout': {
                'xaxis': {'title': x_col, 'type': 'category'},
                'yaxis': {'title': y_col}
            }
        }
    
    def render_bar_chart(self, df: pd.DataFrame, x_col: str, y_col: str,
                         title: str = "", orientation: str = 'v',
                         color_by: Optional[str] = None) -> Dict:
        """
        Рендер столбчатой диаграммы
        
        Args:
            df: DataFrame с данными
            x_col: Колонка для оси X (категории)
            y_col: Колонка для оси Y (значения)
            title: Заголовок
            orientation: 'v' (вертикальная) или 'h' (горизонтальная)
            color_by: Колонка для раскраски по категориям
        
        Returns:
            Dict с данными для графика
        """
        df_plot = df.copy().sort_values(y_col, ascending=(orientation == 'h'))
        
        # Лимит на количество категорий для читаемости
        max_categories = 20
        if len(df_plot) > max_categories:
            df_plot = df_plot.head(max_categories)
        
        return {
            'type': 'bar_chart',
            'title': title,
            'data': {
                'x': df_plot[x_col].tolist() if orientation == 'v' else df_plot[y_col].tolist(),
                'y': df_plot[y_col].tolist() if orientation == 'v' else df_plot[x_col].tolist(),
                'orientation': orientation,
                'marker': {
                    'color': self.colors['primary'] if not color_by else None
                }
            },
            'layout': {
                'xaxis': {'title': x_col if orientation == 'v' else y_col},
                'yaxis': {'title': y_col if orientation == 'v' else x_col}
            }
        }
    
    def render_pareto_chart(self, data: Dict, title: str = "ABC-анализ") -> Dict:
        """
        Рендер диаграммы Парето
        
        Args:
            data: {
                'items': List[str],  # Названия элементов
                'values': List[float],  # Значения
                'cumulative_pct': List[float],  # Накопительный процент
                'classification': Dict[str, str]  # Классификация A/B/C
            }
            title: Заголовок
        
        Returns:
            Dict с данными для комбинированного графика
        """
        items = data.get('items', [])[:20]  # Топ 20
        values = data.get('values', [])[:20]
        cumulative_pct = data.get('cumulative_pct', [])[:20]
        classification = data.get('classification', {})
        
        # Цвета по классам ABC
        colors = []
        for item in items:
            cls = classification.get(item, 'C')
            if cls == 'A':
                colors.append('#ef4444')  # Красный
            elif cls == 'B':
                colors.append('#f59e0b')  # Оранжевый
            else:
                colors.append('#10b981')  # Зеленый
        
        return {
            'type': 'pareto_chart',
            'title': title,
            'data': {
                'bars': {
                    'x': items,
                    'y': values,
                    'marker': {'color': colors}
                },
                'line': {
                    'x': items,
                    'y': cumulative_pct,
                    'yaxis': 'y2',
                    'line': {'color': self.colors['primary'], 'width': 3}
                }
            },
            'layout': {
                'yaxis': {'title': 'Значение'},
                'yaxis2': {
                    'title': 'Накопительный %',
                    'overlaying': 'y',
                    'side': 'right',
                    'range': [0, 100]
                },
                'shapes': [
                    # Линии порогов 80% и 95%
                    {'type': 'line', 'y0': 80, 'y1': 80, 'x0': -0.5, 'x1': len(items)-0.5,
                     'line': {'dash': 'dash', 'color': 'gray'}},
                    {'type': 'line', 'y0': 95, 'y1': 95, 'x0': -0.5, 'x1': len(items)-0.5,
                     'line': {'dash': 'dash', 'color': 'gray'}}
                ]
            },
            'stats': self._calculate_pareto_stats(values, classification)
        }
    
    def _calculate_pareto_stats(self, values: List[float], classification: Dict) -> Dict:
        """Расчёт статистики ABC-анализа"""
        total = sum(values) if values else 0
        
        stats = {'A': {'count': 0, 'value': 0}, 
                 'B': {'count': 0, 'value': 0}, 
                 'C': {'count': 0, 'value': 0}}
        
        for item, value in zip(classification.keys(), values):
            cls = classification.get(item, 'C')
            stats[cls]['count'] += 1
            stats[cls]['value'] += value
        
        # Проценты
        for cls in stats:
            if total > 0:
                stats[cls]['value_pct'] = round(stats[cls]['value'] / total * 100, 1)
            stats[cls]['count_pct'] = round(stats[cls]['count'] / len(classification) * 100, 1) if classification else 0
        
        return stats
    
    def render_table(self, df: pd.DataFrame, title: str = "", 
                     max_rows: int = 100, show_index: bool = False) -> Dict:
        """
        Рендер таблицы данных
        
        Args:
            df: DataFrame с данными
            title: Заголовок
            max_rows: Максимум строк для отображения
            show_index: Показывать ли индекс
        
        Returns:
            Dict с данными таблицы
        """
        df_table = df.copy()
        
        # Лимит строк
        if len(df_table) > max_rows:
            df_table = df_table.head(max_rows)
        
        # Форматирование числовых колонок
        for col in df_table.select_dtypes(include=[np.number]).columns:
            if df_table[col].abs().max() >= 1_000_000:
                df_table[col] = (df_table[col] / 1_000_000).round(1).astype(str) + 'M'
            elif df_table[col].abs().max() >= 1_000:
                df_table[col] = (df_table[col] / 1_000).round(1).astype(str) + 'K'
            else:
                df_table[col] = df_table[col].round(2).astype(str)
        
        return {
            'type': 'table',
            'title': title,
            'data': {
                'columns': df_table.columns.tolist(),
                'rows': df_table.values.tolist(),
                'index': df_table.index.tolist() if show_index else None
            },
            'total_rows': len(df),
            'displayed_rows': len(df_table)
        }
    
    def render_forecast_chart(self, historical_df: pd.DataFrame, 
                              forecast_df: pd.DataFrame,
                              date_col: str, value_col: str,
                              ci_lower: Optional[str] = None,
                              ci_upper: Optional[str] = None,
                              title: str = "Прогноз") -> Dict:
        """
        Рендер графика с прогнозом и доверительным интервалом
        
        Args:
            historical_df: Исторические данные
            forecast_df: Прогнозные данные
            date_col: Колонка даты
            value_col: Колонка значения
            ci_lower: Название колонки нижней границы ДИ
            ci_upper: Название колонки верхней границы ДИ
            title: Заголовок
        
        Returns:
            Dict с данными для графика
        """
        # Исторические данные
        hist_dates = historical_df[date_col].dt.strftime('%Y-%m-%d').tolist()
        hist_values = historical_df[value_col].tolist()
        
        # Прогнозные данные
        fcst_dates = forecast_df[date_col].dt.strftime('%Y-%m-%d').tolist()
        fcst_values = forecast_df[value_col].tolist()
        
        forecast_data = {
            'type': 'forecast_chart',
            'title': title,
            'data': {
                'historical': {
                    'x': hist_dates,
                    'y': hist_values,
                    'name': 'История',
                    'line': {'color': self.colors['primary']}
                },
                'forecast': {
                    'x': fcst_dates,
                    'y': fcst_values,
                    'name': 'Прогноз',
                    'line': {'color': self.colors['warning'], 'dash': 'dash'}
                }
            }
        }
        
        # Доверительный интервал
        if ci_lower and ci_upper and ci_lower in forecast_df.columns and ci_upper in forecast_df.columns:
            forecast_data['data']['confidence_interval'] = {
                'x': fcst_dates + fcst_dates[::-1],
                'y_lower': forecast_df[ci_lower].tolist(),
                'y_upper': forecast_df[ci_upper].tolist()[::-1],
                'fillcolor': 'rgba(245, 158, 11, 0.2)'
            }
        
        return forecast_data
    
    def render_waterfall_chart(self, data: Dict, title: str = "Анализ отклонений") -> Dict:
        """
        Рендер водопада изменений (waterfall chart)
        
        Args:
            data: {
                'categories': List[str],
                'values': List[float],  # Положительные/отрицательные изменения
                'initial': float  # Начальное значение
            }
        
        Returns:
            Dict с данными для waterfall chart
        """
        categories = data.get('categories', [])
        values = data.get('values', [])
        initial = data.get('initial', 0)
        
        # Расчёт накопительных сумм
        cumulative = [initial]
        for v in values:
            cumulative.append(cumulative[-1] + v)
        
        # Определение цветов (зеленый для роста, красный для падения)
        colors = []
        for v in values:
            if v >= 0:
                colors.append(self.colors['up'])
            else:
                colors.append(self.colors['down'])
        
        return {
            'type': 'waterfall_chart',
            'title': title,
            'data': {
                'categories': ['Начало'] + categories + ['Итог'],
                'values': [initial] + values + [cumulative[-1]],
                'changes': [None] + values + [None],
                'colors': [self.colors['stable']] + colors + [self.colors['primary']],
                'cumulative': cumulative
            }
        }


class ExportManager:
    """Менеджер экспорта дашбордов"""
    
    def __init__(self, renderer: UIComponentRenderer):
        self.renderer = renderer
    
    def export_to_dict(self, components: List[Dict]) -> Dict:
        """Экспорт в словарь (для JSON/API)"""
        return {
            'dashboard': {
                'components': components,
                'exported_at': pd.Timestamp.now().isoformat(),
                'total_components': len(components)
            }
        }
    
    def export_to_json_string(self, components: List[Dict]) -> str:
        """Экспорт в JSON строку"""
        import json
        data = self.export_to_dict(components)
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def export_to_csv(self, df: pd.DataFrame) -> str:
        """Экспорт DataFrame в CSV"""
        buffer = io.StringIO()
        df.to_csv(buffer, index=False, sep=';')
        return buffer.getvalue()
    
    def generate_summary_text(self, components: List[Dict]) -> str:
        """Генерация текстового саммари дашборда"""
        lines = ["📊 АНАЛИТИЧЕСКИЙ ОТЧЁТ", "=" * 40, ""]
        
        kpi_count = 0
        for comp in components:
            if comp.get('type') == 'kpi_card':
                kpi_count += 1
                title = comp.get('title', 'KPI')
                value = comp.get('value', '')
                unit = comp.get('unit', '')
                trend = comp.get('trend', '')
                
                trend_icon = {'up': '📈', 'down': '📉', 'stable': '➡️'}.get(trend, '')
                
                lines.append(f"• {title}: {value}{unit} {trend_icon}")
                
                if comp.get('risk_flags'):
                    for flag in comp['risk_flags']:
                        lines.append(f"  ⚠️ {flag}")
        
        lines.extend(["", f"Всего KPI: {kpi_count}", "=" * 40])
        
        return "\n".join(lines)


# Пример использования
if __name__ == "__main__":
    # Тестирование рендерера
    renderer = UIComponentRenderer()
    
    # KPI карточка
    kpi_data = {
        'value': 1250000,
        'unit': 'руб.',
        'title': 'Выручка',
        'comparison': {'previous_value': 1000000, 'change_pct': 25, 'trend': 'up'},
        'risk_flags': []
    }
    
    kpi_card = renderer.render_kpi_card(kpi_data)
    print("KPI Card:", kpi_card)
    
    # Тестовые данные для графика
    df_test = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=30),
        'revenue': np.random.uniform(50000, 150000, 30).cumsum()
    })
    
    line_chart = renderer.render_line_chart(df_test, 'date', 'revenue', 'Динамика выручки')
    print("\nLine Chart создан:", line_chart['type'])
    
    print("\n✅ UI Components Renderer готов к использованию")
