"""
UI Kit & Theme Manager for 1C Dashboard Service.
Стандартизация визуальных элементов и тем оформления.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import plotly.graph_objects as go
import plotly.io as pio


@dataclass
class ColorPalette:
    """Цветовая палитра темы."""
    primary: str
    secondary: str
    accent: str
    success: str
    warning: str
    danger: str
    background: str
    surface: str
    text_primary: str
    text_secondary: str
    border: str
    gradient_start: Optional[str] = None
    gradient_end: Optional[str] = None


@dataclass
class Theme:
    """Конфигурация темы оформления."""
    name: str
    palette: ColorPalette
    font_family: str = "'Inter', 'Segoe UI', sans-serif"
    border_radius: int = 8
    shadow_enabled: bool = True
    animation_enabled: bool = True
    
    # Настройки компонентов
    kpi_card_bg: str = ""
    chart_grid_color: str = ""
    progress_bar_height: int = 8
    
    def __post_init__(self):
        if not self.kpi_card_bg:
            self.kpi_card_bg = self.palette.surface
        if not self.chart_grid_color:
            self.chart_grid_color = self.palette.border


class ThemeManager:
    """Управление темами оформления."""
    
    THEMES: Dict[str, Theme] = {}
    
    @classmethod
    def register_theme(cls, theme: Theme):
        """Регистрация темы."""
        cls.THEMES[theme.name] = theme
    
    @classmethod
    def get_theme(cls, name: str) -> Theme:
        """Получение темы по имени."""
        if name not in cls.THEMES:
            raise ValueError(f"Theme '{name}' not found. Available: {list(cls.THEMES.keys())}")
        return cls.THEMES[name]
    
    @classmethod
    def list_themes(cls) -> List[str]:
        """Список доступных тем."""
        return list(cls.THEMES.keys())


# === ПРЕДУСТАНОВЛЕННЫЕ ТЕМЫ ===

# 1. Light (Корпоративная светлая)
light_theme = Theme(
    name="Light",
    palette=ColorPalette(
        primary="#2563EB",
        secondary="#64748B",
        accent="#0EA5E9",
        success="#10B981",
        warning="#F59E0B",
        danger="#EF4444",
        background="#F8FAFC",
        surface="#FFFFFF",
        text_primary="#1E293B",
        text_secondary="#64748B",
        border="#E2E8F0"
    ),
    border_radius=8,
    shadow_enabled=True
)

# 2. Dark (Темная профессиональная)
dark_theme = Theme(
    name="Dark",
    palette=ColorPalette(
        primary="#3B82F6",
        secondary="#94A3B8",
        accent="#06B6D4",
        success="#34D399",
        warning="#FBBF24",
        danger="#F87171",
        background="#0F172A",
        surface="#1E293B",
        text_primary="#F1F5F9",
        text_secondary="#94A3B8",
        border="#334155"
    ),
    border_radius=8,
    shadow_enabled=False
)

# 3. Neon (Яркая неоновая)
neon_theme = Theme(
    name="Neon",
    palette=ColorPalette(
        primary="#00FFFF",
        secondary="#FF00FF",
        accent="#FFFF00",
        success="#00FF00",
        warning="#FFAA00",
        danger="#FF0000",
        background="#0A0A0A",
        surface="#1A1A2E",
        text_primary="#FFFFFF",
        text_secondary="#CCCCCC",
        border="#00FFFF",
        gradient_start="#00FFFF",
        gradient_end="#FF00FF"
    ),
    border_radius=12,
    shadow_enabled=True,
    animation_enabled=True
)

# 4. Gradient (Градиентная современная)
gradient_theme = Theme(
    name="Gradient",
    palette=ColorPalette(
        primary="#667EEA",
        secondary="#764BA2",
        accent="#F093FB",
        success="#4ADE80",
        warning="#FCD34D",
        danger="#F87171",
        background="#FDF2F8",
        surface="#FFFFFF",
        text_primary="#1F2937",
        text_secondary="#6B7280",
        border="#E5E7EB",
        gradient_start="#667EEA",
        gradient_end="#764BA2"
    ),
    border_radius=16,
    shadow_enabled=True,
    animation_enabled=True
)

# Регистрация тем
ThemeManager.register_theme(light_theme)
ThemeManager.register_theme(dark_theme)
ThemeManager.register_theme(neon_theme)
ThemeManager.register_theme(gradient_theme)


class UIComponentBuilder:
    """Фабрика для создания стилизованных Plotly компонентов."""
    
    def __init__(self, theme_name: str = "Light"):
        self.theme = ThemeManager.get_theme(theme_name)
    
    def create_kpi_card_config(self) -> dict:
        """Конфигурация KPI карточки."""
        return {
            "bgcolor": self.theme.kpi_card_bg,
            "border_color": self.theme.palette.border,
            "border_radius": self.theme.border_radius,
            "text_color": self.theme.palette.text_primary,
            "shadow": "0 4px 6px rgba(0,0,0,0.1)" if self.theme.shadow_enabled else "none"
        }
    
    def create_progress_bar(self, value: float, max_value: float = 100, 
                           height: Optional[int] = None) -> go.Figure:
        """Создание прогресс-бара."""
        if height is None:
            height = self.theme.progress_bar_height
        
        percentage = min(100, max(0, (value / max_value) * 100))
        
        # Определяем цвет в зависимости от значения
        if percentage < 30:
            color = self.theme.palette.danger
        elif percentage < 70:
            color = self.theme.palette.warning
        else:
            color = self.theme.palette.success
        
        # Градиент если доступен
        colorscale = None
        if self.theme.palette.gradient_start and self.theme.palette.gradient_end:
            colorscale = [[0, self.theme.palette.gradient_start], 
                         [1, self.theme.palette.gradient_end]]
            color = None
        
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=percentage,
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={
                'axis': {'range': [None, 100], 'visible': False},
                'bar': {'color': color, 'thickness': 0.5},
                'bgcolor': self.theme.palette.border,
                'borderwidth': 0,
                'steps': []
            },
            number={'font': {'size': 24, 'color': self.theme.palette.text_primary}}
        ))
        
        fig.update_layout(
            height=60,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor=self.theme.palette.surface,
            font={'color': self.theme.palette.text_primary, 'family': self.theme.font_family}
        )
        
        return fig
    
    def create_line_chart_template(self) -> go.Figure:
        """Шаблон линейного графика."""
        fig = go.Figure()
        
        fig.update_layout(
            plot_bgcolor=self.theme.palette.surface,
            paper_bgcolor=self.theme.palette.surface,
            font={'color': self.theme.palette.text_primary, 'family': self.theme.font_family},
            xaxis=dict(
                gridcolor=self.theme.chart_grid_color,
                linecolor=self.theme.palette.border,
                tickfont={'color': self.theme.palette.text_secondary}
            ),
            yaxis=dict(
                gridcolor=self.theme.chart_grid_color,
                linecolor=self.theme.palette.border,
                tickfont={'color': self.theme.palette.text_secondary}
            ),
            legend=dict(
                font={'color': self.theme.palette.text_primary}
            ),
            margin=dict(l=40, r=40, t=40, b=40)
        )
        
        return fig
    
    def create_bar_chart_template(self) -> go.Figure:
        """Шаблон столбчатого графика."""
        fig = go.Figure()
        
        # Базовые цвета для серий
        self.default_colors = [
            self.theme.palette.primary,
            self.theme.palette.accent,
            self.theme.palette.success,
            self.theme.palette.warning,
            self.theme.palette.danger
        ]
        
        fig.update_layout(
            plot_bgcolor=self.theme.palette.surface,
            paper_bgcolor=self.theme.palette.surface,
            font={'color': self.theme.palette.text_primary, 'family': self.theme.font_family},
            xaxis=dict(
                gridcolor=self.theme.chart_grid_color,
                linecolor=self.theme.palette.border,
                tickfont={'color': self.theme.palette.text_secondary}
            ),
            yaxis=dict(
                gridcolor=self.theme.chart_grid_color,
                linecolor=self.theme.palette.border,
                tickfont={'color': self.theme.palette.text_secondary}
            ),
            barmode='group',
            bargap=0.15,
            bargroupgap=0.1
        )
        
        return fig
    
    def create_alert_config(self, alert_type: str) -> dict:
        """Конфигурация уведомления."""
        colors = {
            'info': self.theme.palette.accent,
            'success': self.theme.palette.success,
            'warning': self.theme.palette.warning,
            'error': self.theme.palette.danger
        }
        
        icons = {
            'info': 'ℹ️',
            'success': '✅',
            'warning': '⚠️',
            'error': '❌'
        }
        
        return {
            'color': colors.get(alert_type, self.theme.palette.text_primary),
            'icon': icons.get(alert_type, '•'),
            'bg_opacity': 0.1,
            'border_radius': self.theme.border_radius
        }


def get_all_theme_previews() -> Dict[str, dict]:
    """Генерация превью всех тем для витрины."""
    previews = {}
    
    for theme_name in ThemeManager.list_themes():
        builder = UIComponentBuilder(theme_name)
        theme = ThemeManager.get_theme(theme_name)
        
        previews[theme_name] = {
            'palette': {
                'primary': theme.palette.primary,
                'secondary': theme.palette.secondary,
                'accent': theme.palette.accent,
                'success': theme.palette.success,
                'warning': theme.palette.warning,
                'danger': theme.palette.danger,
                'background': theme.palette.background,
                'surface': theme.palette.surface,
                'text_primary': theme.palette.text_primary,
                'text_secondary': theme.palette.text_secondary,
                'border': theme.palette.border
            },
            'settings': {
                'border_radius': theme.border_radius,
                'shadow_enabled': theme.shadow_enabled,
                'animation_enabled': theme.animation_enabled
            },
            'sample_progress': builder.create_progress_bar(75),
            'sample_line_chart': builder.create_line_chart_template(),
            'sample_bar_chart': builder.create_bar_chart_template()
        }
    
    return previews
