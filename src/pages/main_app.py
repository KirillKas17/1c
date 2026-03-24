"""
Landing Page, Login, Dashboard History & Main App Router.
Full user flow: Landing -> Login -> Upload -> Dashboard -> History.
"""
import streamlit as st
from src.storage.models import get_db, User, DashboardSession
from src.api.auth import login_user, register_user, get_current_user
from src.core.pipeline import DashboardPipeline
from src.utils.logger import get_logger
from datetime import datetime
import pandas as pd

logger = get_logger(__name__)

# --- Page Config ---
st.set_page_config(
    page_title="1C Dashboard | Аналитика за 2 минуты",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Custom CSS for Landing & Auth ---
st.markdown("""
<style>
    /* Landing Page Styles */
    .hero-section {
        text-align: center;
        padding: 4rem 0;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 20px;
        margin-bottom: 2rem;
    }
    .hero-title {
        font-size: 3.5rem;
        font-weight: 800;
        color: #2c3e50;
        margin-bottom: 1rem;
    }
    .hero-subtitle {
        font-size: 1.5rem;
        color: #555;
        margin-bottom: 2rem;
    }
    .feature-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 2rem;
        margin: 3rem 0;
    }
    .feature-card {
        background: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        text-align: center;
    }
    .auth-box {
        max-width: 400px;
        margin: 0 auto;
        padding: 2rem;
        background: white;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    }
    /* History Cards */
    .history-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #3498db;
        margin-bottom: 1rem;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        cursor: pointer;
        transition: transform 0.2s;
    }
    .history-card:hover {
        transform: translateX(5px);
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- Session State Init ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'page' not in st.session_state:
    st.session_state.page = 'landing'

# --- Navigation Logic ---
def navigate_to(page):
    st.session_state.page = page
    st.rerun()

# --- Pages Implementation ---

def render_landing():
    """Landing Page with Hero, Features, and Login CTA"""
    col1, col2, col3 = st.columns([1, 6, 1])
    with col2:
        st.markdown("""
        <div class="hero-section">
            <h1 class="hero-title">1C → Дашборд за 2 минуты</h1>
            <p class="hero-subtitle">Загрузите выгрузку из 1С и получите готовый отчет для директора с прогнозами и презентацией.</p>
            <p style="font-size: 1.2rem; color: #27ae60; font-weight: bold;">✅ Без программистов • ✅ Без настроек • ✅ Конфиденциально</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="feature-grid">
            <div class="feature-card">
                <h3>🚀 Мгновенно</h3>
                <p>AI распознает структуру файла за секунды. Никаких маппингов вручную.</p>
            </div>
            <div class="feature-card">
                <h3>📊 Глубокая аналитика</h3>
                <p>45+ метрик, ABC-анализ, прогнозы продаж и поиск аномалий.</p>
            </div>
            <div class="feature-card">
                <h3>📑 Презентация</h3>
                <p>Автоматическая генерация PPTX с выводами от ИИ для совещания.</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            if st.button("🚀 Попробовать бесплатно", type="primary", use_container_width=True, key="btn_hero"):
                navigate_to('login')
        
        st.markdown("---")
        st.caption("P.S. Ваши данные не покидают сервер. Мы не требуем доступа к вашей 1С.")

def render_auth():
    """Login / Register Form"""
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown('<div class="auth-box">', unsafe_allow_html=True)
        mode = st.radio("Вход или Регистрация?", ["Вход", "Регистрация"], horizontal=True)
        
        email = st.text_input("Email", placeholder="name@company.com")
        password = st.text_input("Пароль", type="password", placeholder="••••••••")
        
        if st.button("Продолжить", type="primary", use_container_width=True):
            db = next(get_db())
            if mode == "Вход":
                user = login_user(db, email, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.current_user = user
                    st.success("Успешный вход!")
                    navigate_to('dashboard_list')
                else:
                    st.error("Неверный email или пароль")
            else:
                user = register_user(db, email, password)
                if user:
                    st.success("Аккаунт создан! Теперь войдите.")
                    mode = "Вход"
                else:
                    st.error("Такой пользователь уже существует")
            db.close()
        st.markdown('</div>', unsafe_allow_html=True)

def render_dashboard_list():
    """Personal Cabinet: List of saved dashboards + Upload New"""
    if not st.session_state.logged_in:
        navigate_to('login')
        return

    db = next(get_db())
    user = st.session_state.current_user
    
    # Header
    c1, c2 = st.columns([3, 1])
    with c1:
        st.title(f"Привет, {user.email.split('@')[0]}! 👋")
        st.subheader("Ваши дашборды")
    with c2:
        if st.button("➕ Новый отчет", type="primary", use_container_width=True):
            st.session_state.page = 'upload'
            st.rerun()
        if st.button("Выйти", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.current_user = None
            navigate_to('landing')
            st.rerun()

    # History List
    sessions = db.query(DashboardSession).filter_by(user_id=user.id).order_by(DashboardSession.created_at.desc()).all()
    
    if not sessions:
        st.info("У вас пока нет сохраненных отчетов. Загрузите первый файл!")
    else:
        for session in sessions:
            with st.container():
                c1, c2, c3, c4 = st.columns([4, 2, 2, 1])
                with c1:
                    st.markdown(f"**{session.file_name}**")
                    st.caption(f"Создан: {session.created_at.strftime('%d.%m.%Y %H:%M')} | Строк: {session.row_count:,}")
                with c2:
                    st.metric("Выручка", f"{session.total_revenue:,.0f} ₽" if session.total_revenue else "-")
                with c3:
                    st.metric("Прогноз", f"+{session.forecast_growth:.1f}%" if session.forecast_growth else "-")
                with c4:
                    if st.button("Открыть", key=f"open_{session.id}"):
                        st.session_state.current_session_id = session.id
                        navigate_to('view_dashboard')
                        st.rerun()
                st.divider()
    
    db.close()

def render_upload():
    """File Upload & Processing"""
    if not st.session_state.logged_in:
        navigate_to('login')
        return

    st.title("📤 Загрузка файла из 1С")
    
    uploaded_file = st.file_uploader(
        "Перетащите сюда файл XLSX/XLS/CSV", 
        type=['xlsx', 'xls', 'csv'],
        help="Стандартная выгрузка из 1С: 'Валовая прибыль', 'Продажи' или 'Оборотно-сальдовая ведомость'"
    )

    if uploaded_file:
        with st.spinner('🤖 AI анализирует структуру файла...'):
            try:
                # Save temp
                temp_path = f"/tmp/{uploaded_file.name}"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Run Pipeline
                pipeline = DashboardPipeline()
                result = pipeline.execute(temp_path, user_id=st.session_state.current_user.id)
                
                # Save to DB
                db = next(get_db())
                new_session = DashboardSession(
                    user_id=st.session_state.current_user.id,
                    file_name=uploaded_file.name,
                    row_count=result.data.shape[0],
                    total_revenue=result.metrics.get('revenue_total', 0),
                    forecast_growth=result.forecast.get('growth_percent', 0),
                    mapping_json=str(result.mapping), # Simplified
                    result_json=str(result.metrics) # Simplified
                )
                db.add(new_session)
                db.commit()
                st.session_state.current_session_id = new_session.id
                db.close()
                
                st.success("Файл успешно обработан!")
                navigate_to('view_dashboard')
                st.rerun()
                
            except Exception as e:
                logger.error(f"Upload error: {e}")
                st.error(f"Ошибка обработки: {str(e)}. Проверьте формат файла.")

def render_view_dashboard():
    """View Specific Dashboard (Cached/History)"""
    if not st.session_state.logged_in or 'current_session_id' not in st.session_state:
        navigate_to('dashboard_list')
        return

    db = next(get_db())
    session = db.query(DashboardSession).get(st.session_state.current_session_id)
    
    if not session:
        st.error("Дашборд не найден")
        db.close()
        return

    st.title(f"📊 Отчет: {session.file_name}")
    
    # Back button
    if st.button("← К списку"):
        navigate_to('dashboard_list')
        st.rerun()

    # Placeholder for actual dashboard rendering (using stored JSON)
    # In real app, we would reconstruct Plotly charts from stored data/metrics
    st.info("Здесь отображается интерактивный дашборд на основе сохраненных данных.")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Выручка", f"{session.total_revenue:,.0f} ₽")
    c2.metric("Прогноз роста", f"{session.forecast_growth:.1f}%")
    c3.metric("Дата анализа", session.created_at.strftime("%d.%m.%Y"))
    
    st.divider()
    
    if st.button("📥 Скачать презентацию (PPTX)"):
        st.download_button(
            label="Скачать PPTX",
            data=b"Fake PPTX Content", # Replace with real generator call
            file_name=f"{session.file_name}_report.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )

    db.close()

# --- Main Router ---
def main():
    page = st.session_state.page
    
    if page == 'landing':
        render_landing()
    elif page == 'login':
        render_auth()
    elif page == 'dashboard_list':
        render_dashboard_list()
    elif page == 'upload':
        render_upload()
    elif page == 'view_dashboard':
        render_view_dashboard()
    else:
        render_landing()

if __name__ == "__main__":
    main()
