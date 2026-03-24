import streamlit as st
import pandas as pd
import time
from datetime import datetime
import os
import hashlib
import json

# --- Конфигурация страницы ---
st.set_page_config(
    page_title="1C Dashboard | Аналитика за 5 минут",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Имитация БД (для MVP) ---
DATA_DIR = "user_data"
os.makedirs(DATA_DIR, exist_ok=True)

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""
if 'dashboards' not in st.session_state:
    st.session_state.dashboards = []

# --- Стили (CSS) ---
st.markdown("""
<style>
    .main-header {font-size: 3rem; font-weight: bold; color: #1E88E5; text-align: center;}
    .sub-header {font-size: 1.2rem; color: #555; text-align: center; margin-bottom: 2rem;}
    .feature-box {padding: 20px; border-radius: 10px; background: #f0f2f6; text-align: center;}
    .login-box {max-width: 400px; margin: 50px auto; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);}
    .dashboard-card {padding: 15px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 10px;}
    .stButton>button {width: 100%; background-color: #1E88E5; color: white;}
</style>
""", unsafe_allow_html=True)

# --- Функции ---
def login_user(email):
    st.session_state.logged_in = True
    st.session_state.user_email = email
    # Загрузка истории (имитация)
    history_file = os.path.join(DATA_DIR, f"{email}_history.csv")
    if os.path.exists(history_file):
        df = pd.read_csv(history_file)
        st.session_state.dashboards = df.to_dict('records')
    else:
        st.session_state.dashboards = []

def save_dashboard_result(name, metrics):
    if not st.session_state.logged_in:
        return
    record = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "name": name,
        "revenue": metrics.get("revenue", 0),
        "profit": metrics.get("profit", 0),
        "status": "Готов"
    }
    st.session_state.dashboards.insert(0, record)
    # Сохранение в CSV
    history_file = os.path.join(DATA_DIR, f"{st.session_state.user_email}_history.csv")
    df = pd.DataFrame(st.session_state.dashboards)
    df.to_csv(history_file, index=False)

def process_file(uploaded_file):
    # Имитация сложной обработки
    time.sleep(1)
    # Здесь должен быть вызов реального пайплайна
    return {"revenue": 1250000, "profit": 350000, "customers": 145}

# --- Роутинг (Страницы) ---

# 1. Лендинг (если не залогинен)
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 class='main-header'>1C → Дашборд за 5 минут</h1>", unsafe_allow_html=True)
        st.markdown("<p class='sub-header'>Загрузите выгрузку из 1С и получите готовый отчет для директора с прогнозами и презентацией.</p>")
        
        st.divider()
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("### 🚀 Мгновенно")
            st.write("Без программистов и настроек. Просто файл Excel.")
        with c2:
            st.markdown("### 🤖 Умный AI")
            st.write("Автоматически распознает колонки и строит метрики.")
        with c3:
            st.markdown("### 📊 Готово к встрече")
            st.write("Экспорт в PowerPoint с выводами за 1 клик.")
            
        st.divider()
        
        st.markdown("#### 👉 Начните работу бесплатно")
        email = st.text_input("Введите ваш Email", placeholder="director@company.com")
        if st.button("Войти / Регистрация"):
            if email:
                login_user(email)
                st.rerun()
            else:
                st.error("Введите корректный Email")

# 2. Личный кабинет и Дашборды (если залогинен)
else:
    # Сайдбар навигации
    with st.sidebar:
        st.title(f"👤 {st.session_state.user_email}")
        menu = st.radio("Меню", ["📂 Мои дашборды", "📤 Новая загрузка", "⚙️ Настройки"])
        if st.button("Выйти"):
            st.session_state.logged_in = False
            st.rerun()

    # Страница: Новая загрузка
    if menu == "📤 Новая загрузка":
        st.header("Загрузка нового отчета")
        uploaded_file = st.file_uploader("Перетащите файл из 1С (.xlsx, .csv)", type=['xlsx', 'csv'])
        
        if uploaded_file is not None:
            st.success("Файл загружен! Начинаем анализ...")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Этапы обработки
            steps = ["Чтение файла...", "AI-распознавание колонок...", "Расчет метрик...", "Построение прогнозов...", "Генерация дашборда..."]
            for i, step in enumerate(steps):
                status_text.text(step)
                progress_bar.progress((i + 1) * 20)
                time.sleep(0.5)
            
            # Имитация результатов
            metrics = process_file(uploaded_file)
            progress_bar.empty()
            status_text.empty()
            
            st.balloons()
            st.subheader("✅ Отчет готов!")
            
            # KPI Карточки
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Выручка", f"{metrics['revenue']:,.0f} ₽", "+12%")
            kpi2.metric("Прибыль", f"{metrics['profit']:,.0f} ₽", "+5%")
            kpi3.metric("Клиенты", f"{metrics['customers']}", "+8")
            
            # Сохранение в историю
            save_dashboard_result(uploaded_file.name, metrics)
            
            if st.button("💾 Сохранить в историю"):
                st.success("Сохранено в личный кабинет!")
                
            if st.button("📥 Скачать Презентацию (PPTX)"):
                st.info("Генерация презентации... (Функция в разработке)")

    # Страница: Мои дашборды (История)
    elif menu == "📂 Мои дашборды":
        st.header("История отчетов")
        if not st.session_state.dashboards:
            st.info("У вас пока нет сохраненных отчетов. Загрузите файл в разделе 'Новая загрузка'.")
        else:
            for item in st.session_state.dashboards:
                with st.container():
                    c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1])
                    c1.write(f"**{item['name']}**")
                    c2.write(item['date'])
                    c3.metric("", f"{item['revenue']:,.0f} ₽")
                    c4.metric("", f"{item['profit']:,.0f} ₽")
                    if c5.button("Открыть", key=item['date']):
                        st.write("🚧 Просмотр дашборда в разработке")
                    st.divider()

    # Страница: Настройки
    elif menu == "⚙️ Настройки":
        st.header("Настройки профиля")
        st.write("Здесь можно сменить тему (Светлая/Темная) и настроить экспорт.")
        theme = st.selectbox("Тема оформления", ["Светлая", "Темная", "Неон"])
        st.info("Изменения применяются мгновенно (демо режим).")
