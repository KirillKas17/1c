"""
Streamlit приложение для 1C Dashboard Service
Загрузка файлов из 1С → AI-распознавание → Дашборд → Экспорт
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
import tempfile
import os

# Импорт наших модулей
from src.core.parser import ExcelParser
from src.core.ai_detector import AIDetector
from src.core.business_rules_engine import BusinessRulesEngine
from src.core.dashboard_optimizer import DashboardOptimizer
from src.core.forecasting import RevenueForecaster
from src.ui.components import DashboardRenderer

# Конфигурация страницы
st.set_page_config(
    page_title="1C Dashboard Service",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Кэширование объектов
@st.cache_resource
def get_parser():
    return ExcelParser()

@st.cache_resource
def get_ai_detector():
    return AIDetector()

@st.cache_resource
def get_rules_engine():
    return BusinessRulesEngine()

@st.cache_resource
def get_renderer():
    return DashboardRenderer()

# Инициализация session state
if 'uploaded_file' not in st.session_state:
    st.session_state.uploaded_file = None
if 'df' not in st.session_state:
    st.session_state.df = None
if 'mapping' not in st.session_state:
    st.session_state.mapping = {}
if 'metrics' not in st.session_state:
    st.session_state.metrics = {}
if 'dashboard_components' not in st.session_state:
    st.session_state.dashboard_components = []

# Заголовок
st.title("📊 1C Dashboard Service")
st.markdown("**Загрузите выгрузку из 1С → получите готовый дашборд за 2 минуты**")

# Сайдбар
with st.sidebar:
    st.header("⚙️ Настройки")
    
    # Выбор отрасли
    industry = st.selectbox(
        "Отрасль",
        ["retail", "wholesale", "production", "services"],
        format_func=lambda x: {"retail": "🏪 Розница", "wholesale": "📦 Опт", "production": "🏭 Производство", "services": "💼 Услуги"}[x]
    )
    
    # Период анализа
    st.subheader("📅 Период анализа")
    date_range = st.date_input("Период", [])
    
    # Фильтры
    st.subheader("🔍 Фильтры")
    show_all_metrics = st.checkbox("Показать все метрики", value=False)
    
    # Экспорт
    st.subheader("📤 Экспорт")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("PNG"):
            st.info("Экспорт в PNG будет реализован")
    with col2:
        if st.button("PDF"):
            st.info("Экспорт в PDF будет реализован")
    with col3:
        if st.button("PPTX"):
            st.info("Экспорт в PPTX будет реализован")
    
    st.divider()
    st.markdown("### 📈 Статистика")
    if st.session_state.df is not None:
        st.metric("Строк в файле", f"{len(st.session_state.df):,}")
        st.metric("Распознано полей", len(st.session_state.mapping))
        st.metric("Метрик рассчитано", len(st.session_state.metrics))

# Основная область
# Шаг 1: Загрузка файла
st.header("1️⃣ Загрузка файла")

uploaded_file = st.file_uploader(
    "Перетащите файл сюда или нажмите для выбора",
    type=['xlsx', 'xls', 'csv'],
    help="Поддерживаются форматы: XLSX, XLS, CSV"
)

if uploaded_file is not None:
    if uploaded_file != st.session_state.uploaded_file:
        st.session_state.uploaded_file = uploaded_file
        st.session_state.df = None
        st.session_state.mapping = {}
        st.session_state.metrics = {}
        st.rerun()
    
    # Отображение информации о файле
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Файл", uploaded_file.name)
    with col2:
        st.metric("Размер", f"{uploaded_file.size / 1024:.1f} KB")
    with col3:
        st.metric("Тип", uploaded_file.type.split('/')[-1].upper())
    
    # Шаг 2: Парсинг и AI-распознавание
    st.header("2️⃣ Распознавание структуры")
    
    if st.session_state.df is None:
        with st.spinner("🔄 Обработка файла..."):
            try:
                # Сохраняем во временный файл
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                
                # Парсинг
                parser = get_parser()
                df = parser.parse(tmp_path)
                
                # AI-распознавание
                detector = get_ai_detector()
                mapping_result = detector.detect(df)
                
                # Сохранение в session state
                st.session_state.df = df
                st.session_state.mapping = mapping_result['mapping']
                
                # Очистка временного файла
                os.unlink(tmp_path)
                
                st.success("✅ Файл успешно обработан!")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Ошибка обработки: {str(e)}")
                st.stop()
    
    # Отображение маппинга для подтверждения
    if st.session_state.df is not None and st.session_state.mapping:
        st.subheader("🤖 Распознанные поля:")
        
        mapping_df = pd.DataFrame([
            {
                "Колонка в файле": col,
                "Распознано как": info.get('field_type', 'Не распознано'),
                "Уверенность": f"{info.get('confidence', 0):.0%}",
                "Статус": "✅" if info.get('confidence', 0) > 0.7 else "⚠️"
            }
            for col, info in st.session_state.mapping.items()
        ])
        
        st.dataframe(mapping_df, use_container_width=True, hide_index=True)
        
        # Интерактивное исправление
        with st.expander("✏️ Исправить распознавание"):
            st.write("Выберите колонку и укажите правильный тип поля:")
            col_to_fix = st.selectbox(
                "Колонка",
                list(st.session_state.mapping.keys())
            )
            correct_type = st.selectbox(
                "Правильный тип",
                ["revenue", "cost", "quantity", "product", "customer", "date", "category", "region"]
            )
            if st.button("Применить исправление"):
                if col_to_fix in st.session_state.mapping:
                    st.session_state.mapping[col_to_fix]['field_type'] = correct_type
                    st.session_state.mapping[col_to_fix]['confidence'] = 1.0
                    st.success(f"✅ Колонка '{col_to_fix}' теперь распознана как '{correct_type}'")
                    st.rerun()
        
        # Шаг 3: Расчёт метрик
        st.header("3️⃣ Расчёт метрик")
        
        if not st.session_state.metrics:
            with st.spinner("🔄 Расчёт бизнес-метрик..."):
                try:
                    rules_engine = get_rules_engine()
                    
                    # Применяем правила
                    metrics = rules_engine.calculate_all(
                        st.session_state.df,
                        st.session_state.mapping,
                        industry=industry
                    )
                    
                    st.session_state.metrics = metrics
                    
                    # Оптимизация дашборда
                    optimizer = DashboardOptimizer()
                    components = optimizer.optimize(metrics, max_components=12)
                    st.session_state.dashboard_components = components
                    
                    st.success(f"✅ Рассчитано {len(metrics)} метрик!")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Ошибка расчёта метрик: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
                    st.stop()
        
        # Отображение дашборда
        if st.session_state.metrics and st.session_state.dashboard_components:
            st.header("4️⃣ Дашборд")
            
            # Вкладки
            tabs = st.tabs(["📊 Главная", "📈 Прогноз", "📋 Детали"])
            
            with tabs[0]:
                renderer = get_renderer()
                
                # KPI карточки (первые 6)
                kpi_components = [c for c in st.session_state.dashboard_components if c['type'] == 'kpi_card'][:6]
                if kpi_components:
                    cols = st.columns(min(len(kpi_components), 3))
                    for idx, comp in enumerate(kpi_components):
                        with cols[idx % 3]:
                            renderer.render_kpi_card(comp)
                
                st.divider()
                
                # Графики
                chart_components = [c for c in st.session_state.dashboard_components if c['type'] in ['line_chart', 'bar_chart', 'pie_chart']]
                for comp in chart_components:
                    fig = renderer.render_chart(comp)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                
                # Таблицы
                table_components = [c for c in st.session_state.dashboard_components if c['type'] == 'table']
                for comp in table_components:
                    renderer.render_table(comp)
            
            with tabs[1]:
                st.subheader("🔮 Прогнозирование")
                
                if 'revenue' in st.session_state.mapping or 'Выручка' in str(st.session_state.mapping.values()):
                    with st.spinner("🔄 Построение прогноза..."):
                        try:
                            forecaster = RevenueForecaster()
                            
                            # Поиск колонки выручки и даты
                            revenue_col = None
                            date_col = None
                            for col, info in st.session_state.mapping.items():
                                if info.get('field_type') == 'revenue':
                                    revenue_col = col
                                elif info.get('field_type') == 'date':
                                    date_col = col
                            
                            if revenue_col and date_col:
                                # Подготовка данных
                                df_temp = st.session_state.df.copy()
                                df_temp[date_col] = pd.to_datetime(df_temp[date_col], errors='coerce')
                                df_temp = df_temp.dropna(subset=[date_col, revenue_col])
                                df_temp = df_temp.groupby(date_col)[revenue_col].sum().reset_index()
                                df_temp.columns = ['ds', 'y']
                                
                                if len(df_temp) >= 10:
                                    # Прогноз на 30 дней
                                    forecast_df = forecaster.predict(df_temp, periods=30)
                                    
                                    # Визуализация
                                    fig = go.Figure()
                                    fig.add_trace(go.Scatter(
                                        x=df_temp['ds'],
                                        y=df_temp['y'],
                                        mode='lines+markers',
                                        name='Факт',
                                        line=dict(color='#2E86AB', width=2)
                                    ))
                                    
                                    if 'yhat' in forecast_df.columns:
                                        fig.add_trace(go.Scatter(
                                            x=forecast_df['ds'],
                                            y=forecast_df['yhat'],
                                            mode='lines',
                                            name='Прогноз',
                                            line=dict(color='#A23B72', width=2, dash='dash')
                                        ))
                                    
                                    if 'yhat_upper' in forecast_df.columns and 'yhat_lower' in forecast_df.columns:
                                        fig.add_trace(go.Scatter(
                                            x=pd.concat([forecast_df['ds'], forecast_df['ds'][::-1]]),
                                            y=pd.concat([forecast_df['yhat_upper'], forecast_df['yhat_lower'][::-1]]),
                                            fill='toself',
                                            fillcolor='rgba(162, 59, 114, 0.2)',
                                            line=dict(color='rgba(255,255,255,0)'),
                                            name='Доверительный интервал (95%)'
                                        ))
                                    
                                    fig.update_layout(
                                        title="📈 Прогноз выручки на 30 дней",
                                        xaxis_title="Дата",
                                        yaxis_title="Выручка",
                                        hovermode='x unified',
                                        template='plotly_white',
                                        height=500
                                    )
                                    
                                    st.plotly_chart(fig, use_container_width=True)
                                    
                                    # Метрики качества прогноза
                                    if 'mape' in forecast_df.attrs:
                                        col1, col2, col3 = st.columns(3)
                                        with col1:
                                            st.metric("MAPE", f"{forecast_df.attrs.get('mape', 0):.1f}%")
                                        with col2:
                                            st.metric("MAE", f"{forecast_df.attrs.get('mae', 0):,.0f}")
                                        with col3:
                                            st.metric("RMSE", f"{forecast_df.attrs.get('rmse', 0):,.0f}")
                                else:
                                    st.warning("⚠️ Недостаточно данных для прогноза (минимум 10 точек)")
                            else:
                                st.warning("⚠️ Не найдены колонки выручки и/или даты")
                        
                        except Exception as e:
                            st.error(f"❌ Ошибка прогнозирования: {str(e)}")
                else:
                    st.info("ℹ️ Для построения прогноза необходима колонка 'Выручка'")
            
            with tabs[2]:
                st.subheader("📋 Детальные данные")
                
                # Показать исходные данные
                with st.expander("📄 Исходные данные (первые 100 строк)"):
                    st.dataframe(st.session_state.df.head(100), use_container_width=True)
                
                # Показать все метрики
                with st.expander("📊 Все рассчитанные метрики"):
                    if st.session_state.metrics:
                        metrics_df = pd.DataFrame([
                            {
                                "Метрика": k,
                                "Значение": v.get('value', 'N/A'),
                                "Ед. изм.": v.get('unit', ''),
                                "Приоритет": v.get('priority', 0)
                            }
                            for k, v in st.session_state.metrics.items()
                        ])
                        st.dataframe(metrics_df, use_container_width=True, hide_index=True)
                
                # Показать маппинг
                with st.expander("🗺️ Полный маппинг полей"):
                    mapping_detail = pd.DataFrame([
                        {
                            "Колонка": col,
                            "Тип": info.get('field_type', 'N/A'),
                            "Уверенность": f"{info.get('confidence', 0):.0%}",
                            "Метод": info.get('detection_method', 'N/A')
                        }
                        for col, info in st.session_state.mapping.items()
                    ])
                    st.dataframe(mapping_detail, use_container_width=True, hide_index=True)

else:
    # Инструкция при отсутствии файла
    st.info("👆 Загрузите файл выше, чтобы начать")
    
    st.markdown("""
    ### Как это работает:
    1. **Загрузите файл** — перетащите XLSX/XLS/CSV выгрузку из 1С
    2. **AI распознает структуру** — автоматически определит колонки (Выручка, Себестоимость, Товары и т.д.)
    3. **Проверьте маппинг** — подтвердите или исправьте распознавание
    4. **Получите дашборд** — система рассчитает 45+ метрик и построит визуализации
    5. **Экспортируйте** — скачайте отчёт в PNG, PDF или PPTX
    
    ### Поддерживаемые конфигурации 1С:
    - 1С:Управление торговлей (УТ)
    - 1С:Комплексная автоматизация (КА)
    - 1С:Бухгалтерия предприятия (БП)
    - 1С:Управление нашей фирмой (УНФ)
    """)
    
    # Примеры файлов
    st.markdown("### 📁 Примеры файлов для тестирования:")
    st.code("""
    - Отчёт "Продажи по контрагентам"
    - Отчёт "Валовая прибыль предприятия"
    - Оборотно-сальдовая ведомость
    - Анализ продаж по товарам
    """)

# Футер
st.divider()
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        <small>1C Dashboard Service v0.4.0 | Powered by AI & Business Rules</small>
    </div>
    """,
    unsafe_allow_html=True
)
