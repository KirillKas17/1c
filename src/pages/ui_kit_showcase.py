"""
UI Kit Showcase - Витрина компонентов интерфейса.
Страница для просмотра и тестирования всех UI элементов в разных темах.
"""

import streamlit as st
import plotly.graph_objects as go
from src.ui.theme_manager import (
    ThemeManager, 
    UIComponentBuilder, 
    get_all_theme_previews,
    Theme
)

st.set_page_config(
    page_title="UI Kit Showcase",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS для витрины
st.markdown("""
<style>
    .component-section {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        border: 1px solid #e9ecef;
    }
    .theme-preview {
        border: 2px solid #dee2e6;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
    }
    .color-swatch {
        width: 100%;
        height: 60px;
        border-radius: 6px;
        display: inline-block;
        margin: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .component-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 20px;
    }
</style>
""", unsafe_allow_html=True)

# Заголовок
st.title("🎨 UI Kit Showcase")
st.markdown("**Витрина компонентов и тем оформления** для 1C Dashboard Service")
st.divider()

# Сайдбар с выбором темы для предпросмотра
with st.sidebar:
    st.header("🛠 Настройки витрины")
    
    # Выбор активной темы для демо
    available_themes = ThemeManager.list_themes()
    selected_theme = st.selectbox(
        "Выберите тему для превью:",
        options=available_themes,
        index=0
    )
    
    st.info(f"Доступно тем: {len(available_themes)}")
    
    # Переключатель режима отображения
    view_mode = st.radio(
        "Режим просмотра:",
        ["Все темы сразу", "Только выбранная"],
        index=1
    )
    
    st.divider()
    
    # Информация о теме
    theme_info = ThemeManager.get_theme(selected_theme)
    st.subheader(f"Инфо: {theme_info.name}")
    st.metric("Border Radius", f"{theme_info.border_radius}px")
    st.metric("Тени", "Вкл" if theme_info.shadow_enabled else "Выкл")
    st.metric("Анимации", "Вкл" if theme_info.animation_enabled else "Выкл")

# Определение тем для отображения
if view_mode == "Все темы сразу":
    themes_to_show = available_themes
else:
    themes_to_show = [selected_theme]

# ============================================
# СЕКЦИЯ 1: Цветовые палитры
# ============================================
st.header("1️⃣ Цветовые палитры")
st.markdown("Базовые цвета для каждой темы")

for theme_name in themes_to_show:
    with st.expander(f"🎨 Палитра: {theme_name}", expanded=(theme_name == selected_theme)):
        theme = ThemeManager.get_theme(theme_name)
        builder = UIComponentBuilder(theme_name)
        
        cols = st.columns(5)
        
        # Основные цвета
        colors = {
            "Primary": theme.palette.primary,
            "Secondary": theme.palette.secondary,
            "Accent": theme.palette.accent,
            "Success": theme.palette.success,
            "Warning": theme.palette.warning,
            "Danger": theme.palette.danger
        }
        
        for i, (name, color) in enumerate(colors.items()):
            with cols[i % 5]:
                st.markdown(f"**{name}**")
                st.markdown(
                    f'<div style="background-color:{color}; height:60px; '
                    f'border-radius:6px; box-shadow:0 2px 4px rgba(0,0,0,0.1);"></div>',
                    unsafe_allow_html=True
                )
                st.code(color)
        
        # Фоновые цвета
        st.subheader("Фоновые цвета")
        bg_cols = st.columns(3)
        bg_colors = {
            "Background": theme.palette.background,
            "Surface": theme.palette.surface,
            "Border": theme.palette.border
        }
        
        for i, (name, color) in enumerate(bg_colors.items()):
            with bg_cols[i]:
                st.markdown(f"**{name}**")
                st.markdown(
                    f'<div style="background-color:{color}; height:60px; '
                    f'border-radius:6px; border:1px solid #ddd;"></div>',
                    unsafe_allow_html=True
                )
                st.code(color)
        
        # Градиенты если есть
        if theme.palette.gradient_start and theme.palette.gradient_end:
            st.subheader("Градиент")
            gradient_html = f'''
            <div style="background: linear-gradient(to right, {theme.palette.gradient_start}, {theme.palette.gradient_end});
                        height:60px; border-radius:6px; margin:10px 0;"></div>
            '''
            st.markdown(gradient_html, unsafe_allow_html=True)
            st.code(f"{theme.palette.gradient_start} → {theme.palette.gradient_end}")

st.divider()

# ============================================
# СЕКЦИЯ 2: Прогресс-бары
# ============================================
st.header("2️⃣ Прогресс-бары")
st.markdown("Индикаторы выполнения для различных состояний")

for theme_name in themes_to_show:
    with st.expander(f"📊 Прогресс-бары: {theme_name}", expanded=(theme_name == selected_theme)):
        builder = UIComponentBuilder(theme_name)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Низкий прогресс (25%)**")
            fig = builder.create_progress_bar(25)
            st.plotly_chart(fig, use_container_width=True, key=f"{theme_name}_prog_25")
        
        with col2:
            st.markdown("**Средний прогресс (50%)**")
            fig = builder.create_progress_bar(50)
            st.plotly_chart(fig, use_container_width=True, key=f"{theme_name}_prog_50")
        
        with col3:
            st.markdown("**Высокий прогресс (85%)**")
            fig = builder.create_progress_bar(85)
            st.plotly_chart(fig, use_container_width=True, key=f"{theme_name}_prog_85")
        
        # Пример использования в контексте
        st.markdown("**Пример: Загрузка файла**")
        progress_placeholder = st.empty()
        for percent in range(0, 101, 10):
            fig = builder.create_progress_bar(percent)
            progress_placeholder.plotly_chart(fig, use_container_width=True, key=f"{theme_name}_anim_{percent}")
            if percent == 100:
                break

st.divider()

# ============================================
# СЕКЦИЯ 3: Графики (Templates)
# ============================================
st.header("3️⃣ Шаблоны графиков")
st.markdown("Базовые настройки для различных типов визуализаций")

for theme_name in themes_to_show:
    with st.expander(f"📈 Графики: {theme_name}", expanded=False):
        builder = UIComponentBuilder(theme_name)
        
        # Линейный график
        st.subheader("Линейный график (Динамика)")
        fig_line = builder.create_line_chart_template()
        # Добавляем тестовые данные
        fig_line.add_scatter(x=[1, 2, 3, 4, 5], y=[10, 15, 13, 17, 20], 
                            mode='lines+markers', name='Выручка',
                            line=dict(color=ThemeManager.get_theme(theme_name).palette.primary, width=3))
        st.plotly_chart(fig_line, use_container_width=True, key=f"{theme_name}_line")
        
        # Столбчатый график
        st.subheader("Столбчатый график (Сравнение)")
        fig_bar = builder.create_bar_chart_template()
        # Добавляем тестовые данные
        fig_bar.add_bar(x=['Янв', 'Фев', 'Мар', 'Апр'], y=[120, 150, 180, 200], 
                       name='2024',
                       marker_color=ThemeManager.get_theme(theme_name).palette.primary)
        fig_bar.add_bar(x=['Янв', 'Фев', 'Мар', 'Апр'], y=[100, 130, 160, 190], 
                       name='2023',
                       marker_color=ThemeManager.get_theme(theme_name).palette.secondary)
        st.plotly_chart(fig_bar, use_container_width=True, key=f"{theme_name}_bar")

st.divider()

# ============================================
# СЕКЦИЯ 4: Уведомления (Alerts)
# ============================================
st.header("4️⃣ Уведомления и алерты")
st.markdown("Стили для информационных сообщений")

for theme_name in themes_to_show:
    with st.expander(f"🔔 Уведомления: {theme_name}", expanded=False):
        builder = UIComponentBuilder(theme_name)
        theme = ThemeManager.get_theme(theme_name)
        
        alert_types = ['info', 'success', 'warning', 'error']
        
        for alert_type in alert_types:
            config = builder.create_alert_config(alert_type)
            
            messages = {
                'info': "ℹ️ **Информация**: Обработка файла завершена успешно.",
                'success': "✅ **Успех**: Дашборд сгенерирован и готов к просмотру.",
                'warning': "⚠️ **Внимание**: Найдены подозрительные значения в данных.",
                'error': "❌ **Ошибка**: Не удалось распознать структуру файла. Проверьте выгрузку."
            }
            
            # Стилизация через Streamlit native alerts
            if alert_type == 'info':
                st.info(messages['info'], icon="ℹ️")
            elif alert_type == 'success':
                st.success(messages['success'], icon="✅")
            elif alert_type == 'warning':
                st.warning(messages['warning'], icon="⚠️")
            elif alert_type == 'error':
                st.error(messages['error'], icon="❌")

st.divider()

# ============================================
# СЕКЦИЯ 5: KPI Карточки (Mockup)
# ============================================
st.header("5️⃣ KPI Карточки")
st.markdown("Отображение ключевых метрик")

for theme_name in themes_to_show:
    with st.expander(f"💼 KPI Карточки: {theme_name}", expanded=False):
        theme = ThemeManager.get_theme(theme_name)
        
        cols = st.columns(4)
        
        kpi_data = [
            {"title": "Выручка", "value": "₽12.5M", "delta": "+15%", "positive": True},
            {"title": "Клиенты", "value": "1,245", "delta": "+8%", "positive": True},
            {"title": "Маржа", "value": "23.5%", "delta": "-2%", "positive": False},
            {"title": "Заказы", "value": "3,890", "delta": "+22%", "positive": True}
        ]
        
        for i, kpi in enumerate(kpi_data):
            with cols[i]:
                # Имитация карточки через markdown
                delta_color = theme.palette.success if kpi['positive'] else theme.palette.danger
                delta_symbol = "↑" if kpi['positive'] else "↓"
                
                card_html = f"""
                <div style="
                    background-color: {theme.palette.surface};
                    border: 1px solid {theme.palette.border};
                    border-radius: {theme.border_radius}px;
                    padding: 20px;
                    box-shadow: {'0 4px 6px rgba(0,0,0,0.1)' if theme.shadow_enabled else 'none'};
                    text-align: center;
                ">
                    <div style="color: {theme.palette.text_secondary}; font-size: 14px; margin-bottom: 8px;">
                        {kpi['title']}
                    </div>
                    <div style="color: {theme.palette.text_primary}; font-size: 28px; font-weight: bold;">
                        {kpi['value']}
                    </div>
                    <div style="color: {delta_color}; font-size: 16px; margin-top: 8px; font-weight: 500;">
                        {delta_symbol} {kpi['delta']}
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)

st.divider()

# ============================================
# СЕКЦИЯ 6: Кнопки (Mockup)
# ============================================
st.header("6️⃣ Кнопки и элементы управления")
st.markdown("Стили кнопок для различных действий")

for theme_name in themes_to_show:
    with st.expander(f"🔘 Кнопки: {theme_name}", expanded=False):
        theme = ThemeManager.get_theme(theme_name)
        
        cols = st.columns(4)
        
        with cols[0]:
            st.markdown(
                f'''<div style="text-align:center">
                    <button style="
                        background-color: {theme.palette.primary};
                        color: white;
                        border: none;
                        padding: 12px 24px;
                        border-radius: {theme.border_radius}px;
                        font-size: 16px;
                        cursor: pointer;
                        box-shadow: {'0 4px 6px rgba(0,0,0,0.1)' if theme.shadow_enabled else 'none'};
                    ">Primary</button>
                </div>''',
                unsafe_allow_html=True
            )
        
        with cols[1]:
            st.markdown(
                f'''<div style="text-align:center">
                    <button style="
                        background-color: {theme.palette.surface};
                        color: {theme.palette.text_primary};
                        border: 2px solid {theme.palette.border};
                        padding: 12px 24px;
                        border-radius: {theme.border_radius}px;
                        font-size: 16px;
                        cursor: pointer;
                    ">Secondary</button>
                </div>''',
                unsafe_allow_html=True
            )
        
        with cols[2]:
            st.markdown(
                f'''<div style="text-align:center">
                    <button style="
                        background-color: {theme.palette.success};
                        color: white;
                        border: none;
                        padding: 12px 24px;
                        border-radius: {theme.border_radius}px;
                        font-size: 16px;
                        cursor: pointer;
                        box-shadow: {'0 4px 6px rgba(0,0,0,0.1)' if theme.shadow_enabled else 'none'};
                    ">Success</button>
                </div>''',
                unsafe_allow_html=True
            )
        
        with cols[3]:
            st.markdown(
                f'''<div style="text-align:center">
                    <button style="
                        background-color: {theme.palette.danger};
                        color: white;
                        border: none;
                        padding: 12px 24px;
                        border-radius: {theme.border_radius}px;
                        font-size: 16px;
                        cursor: pointer;
                        box-shadow: {'0 4px 6px rgba(0,0,0,0.1)' if theme.shadow_enabled else 'none'};
                    ">Danger</button>
                </div>''',
                unsafe_allow_html=True
            )

st.divider()

# Футер
st.markdown("---")
st.caption(
    "**UI Kit Showcase v1.0** | "
    f"Активная тема: **{selected_theme}** | "
    f"Всего тем: **{len(ThemeManager.THEMES)}**"
)
