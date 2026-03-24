# Модуль прогнозирования: Спецификация

## 📋 Обзор

Модуль прогнозирования предоставляет автоматическое прогнозирование ключевых бизнес-метрик с использованием современных методов машинного обучения и статистики.

## 🎯 Цели

1. **Авто-выбор модели** — пользователь не выбирает метод, система подбирает оптимальный
2. **Высокая точность** — MAPE < 15% для краткосрочных прогнозов
3. **Прозрачность** — доверительные интервалы и метрики качества
4. **Универсальность** — работает для любых временных рядов из 1С

## 🏗 Архитектура

```
┌─────────────────────────────────────────────────────┐
│              ForecastEngine                         │
├─────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ Model       │  │ Model       │  │ Model       │ │
│  │ Selector    │  │ Library     │  │ Validator   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ Exponential │  │ ARIMA/      │  │ Prophet     │ │
│  │ Smoothing   │  │ SARIMA      │  │             │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │ XGBoost/    │  │ Ensemble    │  │ Neural      │ │
│  │ LightGBM    │  │             │  │ Networks    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│           Forecast Result                           │
│  • forecast_values (точки)                          │
│  • confidence_intervals (80%, 95%)                  │
│  • metrics (MAPE, MAE, RMSE, MASE)                  │
│  • decomposition (trend, seasonality, residual)     │
│  • model_info (название, параметры)                 │
└─────────────────────────────────────────────────────┘
```

## 🔧 Методы прогнозирования

### 1. Exponential Smoothing (ETS)
**Библиотека:** `statsmodels`  
**Когда используется:** Короткие ряды (20-50 точек), простой тренд  
**Преимущества:** Быстро, стабильно, мало данных  
**Недостатки:** Не учитывает сложные паттерны  

```python
from statsmodels.tsa.holtwinters import ExponentialSmoothing

model = ExponentialSmoothing(
    data,
    trend='add',
    seasonal='add',
    seasonal_periods=12
)
```

### 2. ARIMA / SARIMA
**Библиотека:** `statsmodels`  
**Когда используется:** Стационарные ряды, есть сезонность  
**Преимущества:** Классический метод, хорошая точность  
**Недостатки:** Требует стационарности, медленный подбор параметров  

```python
from statsmodels.tsa.arima.model import ARIMA

model = ARIMA(
    data,
    order=(p, d, q),  # автоматически подбирается
    seasonal_order=(P, D, Q, s)
)
```

### 3. Prophet
**Библиотека:** `prophet` (Meta)  
**Когда используется:** Длинные ряды (100+ точек), сезонность, праздники  
**Преимущества:** Учитывает праздники, выбросы, несколько сезонностей  
**Недостатки:** Медленный, требует много данных  

```python
from prophet import Prophet

model = Prophet(
    yearly_seasonality=True,
    weekly_seasonality=True,
    holidays=holidays_df  # праздники РФ
)
```

### 4. XGBoost / LightGBM
**Библиотека:** `xgboost` / `lightgbm`  
**Когда используется:** Много факторов, нелинейные зависимости  
**Преимущества:** Очень высокая точность, учёт внешних факторов  
**Недостатки:** Требует feature engineering, много данных  

```python
import xgboost as xgb

# Feature engineering
features = create_time_series_features(data, lags=[1, 2, 3, 7, 14, 30])

model = xgb.XGBRegressor(
    n_estimators=100,
    max_depth=6,
    learning_rate=0.1
)
```

### 5. Neural Networks (LSTM)
**Библиотека:** `tensorflow` / `pytorch`  
**Когда используется:** Очень длинные ряды (500+ точек), сложные паттерны  
**Преимущества:** Максимальная точность на сложных данных  
**Недостатки:** Очень медленный, требует GPU, много данных  

```python
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

model = Sequential([
    LSTM(50, return_sequences=True, input_shape=(lookback, 1)),
    LSTM(50),
    Dense(1)
])
```

### 6. Ensemble
**Библиотека:** Custom  
**Когда используется:** Достаточно данных для всех моделей  
**Преимущества:** Максимальная точность и стабильность  
**Недостатки:** Медленный, ресурсоёмкий  

```python
predictions = {
    'prophet': prophet_pred,
    'arima': arima_pred,
    'xgboost': xgb_pred
}
ensemble_pred = np.average(
    list(predictions.values()),
    weights=[0.4, 0.3, 0.3]  # на основе валидации
)
```

## 🤖 Авто-выбор модели

### Алгоритм выбора

```python
def select_best_model(time_series: pd.Series) -> str:
    """
    Автоматически выбирает лучшую модель для временного ряда.
    """
    checks = {
        'length': len(time_series),
        'seasonality': detect_seasonality(time_series),
        'trend': detect_trend(time_series),
        'stationarity': adf_test(time_series),
        'outliers': count_outliers(time_series),
        'missing_values': time_series.isna().sum()
    }
    
    # Правила выбора
    if checks['length'] < 20:
        return 'simple_moving_average'  # Недостаточно данных
    elif checks['length'] < 50:
        return 'exponential_smoothing'
    elif checks['seasonality'] and checks['length'] > 100:
        return 'prophet'
    elif checks['stationarity']:
        return 'arima'
    elif checks['length'] > 200:
        return 'xgboost'
    else:
        return 'exponential_smoothing'
```

### Тесты для анализа ряда

| Тест | Библиотека | Что определяет |
|------|-----------|----------------|
| **ADF Test** | `statsmodels` | Стационарность |
| **KPSS Test** | `statsmodels` | Стационарность (дополнительно) |
| **Seasonal Decompose** | `statsmodels` | Сезонность |
| **ACF/PACF** | `statsmodels` | Автокорреляция |
| **Outlier Detection** | `scipy` | Выбросы |

## 📊 Метрики качества

### Реализация

```python
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np

def calculate_metrics(actual: pd.Series, predicted: pd.Series) -> dict:
    """
    Рассчитывает все метрики качества прогноза.
    """
    mape = np.mean(np.abs((actual - predicted) / actual)) * 100
    mae = mean_absolute_error(actual, predicted)
    rmse = np.sqrt(mean_squared_error(actual, predicted))
    
    # MASE (Mean Absolute Scaled Error)
    naive_forecast = actual.shift(1).iloc[1:]
    naive_actual = actual.iloc[1:]
    mase = mae / mean_absolute_error(naive_actual, naive_forecast)
    
    return {
        'mape': mape,
        'mae': mae,
        'rmse': rmse,
        'mase': mase
    }
```

### Бенчмарки

| Метрика | Отлично | Хорошо | Удовлетворительно |
|---------|---------|--------|-------------------|
| **MAPE** | < 10% | 10-15% | 15-25% |
| **MASE** | < 0.8 | 0.8-1.0 | 1.0-1.5 |
| **Coverage (95% ДИ)** | 93-97% | 90-98% | 85-99% |

## 🎨 Визуализация

### Компоненты

1. **Основной график**
   - Линия факта (история)
   - Линия прогноза
   - Доверительный интервал (затенённая область)

2. **Декомпозиция**
   - Тренд
   - Сезонность
   - Остаток

3. **Метрики качества**
   - Таблица с MAPE, MAE, RMSE, MASE

### Пример Plotly

```python
import plotly.graph_objects as go
from plotly.subplots import make_subplots

fig = make_subplots(rows=2, cols=1, shared_xaxes=True)

# Факт и прогноз
fig.add_trace(go.Scatter(x=history.index, y=history, name='Факт'), row=1, col=1)
fig.add_trace(go.Scatter(x=forecast.index, y=forecast, name='Прогноз'), row=1, col=1)
fig.add_trace(go.Scatter(
    x=ci_upper.index, y=ci_upper,
    fill=None, mode='lines', line_color='rgba(0,100,80,0.2)',
    name='95% ДИ'
), row=1, col=1)
fig.add_trace(go.Scatter(
    x=ci_lower.index, y=ci_lower,
    fill='tonexty', mode='lines', line_color='rgba(0,100,80,0.2)',
), row=1, col=1)

# Декомпозиция
fig.add_trace(go.Scatter(x=decomp.index, y=decomp['trend'], name='Тренд'), row=2, col=1)
fig.add_trace(go.Scatter(x=decomp.index, y=decomp['seasonal'], name='Сезонность'), row=2, col=1)

fig.update_layout(height=600, title='Прогноз продаж')
```

## 📦 API модуля

### Эндпоинты

```python
# POST /api/v1/forecast/build
{
    "metric_id": "revenue",
    "data": [...],  # временной ряд
    "horizon_days": 90,
    "confidence_levels": [0.8, 0.95]
}

# Response
{
    "forecast": [...],
    "confidence_intervals": {
        "0.8": {"lower": [...], "upper": [...]},
        "0.95": {"lower": [...], "upper": [...]}
    },
    "metrics": {
        "mape": 8.5,
        "mae": 12500,
        "rmse": 18000,
        "mase": 0.75
    },
    "model_info": {
        "name": "prophet",
        "parameters": {...},
        "selection_reason": "Длинный ряд с сезонностью"
    },
    "decomposition": {
        "trend": [...],
        "seasonal": [...],
        "residual": [...]
    }
}

# GET /api/v1/forecast/methods
# Возвращает список доступных методов

# POST /api/v1/forecast/compare
# Сравнивает несколько моделей на исторических данных
```

## 🧪 Тестирование

### Unit-тесты

```python
def test_exponential_smoothing():
    data = generate_synthetic_data(trend='up', seasonality=True, length=50)
    forecast = forecast_engine.predict(data, horizon=30, method='exponential_smoothing')
    assert len(forecast) == 30
    assert forecast.mape < 20

def test_auto_model_selection():
    short_data = generate_synthetic_data(length=25)
    long_data = generate_synthetic_data(length=150)
    
    assert forecast_engine.select_model(short_data) == 'exponential_smoothing'
    assert forecast_engine.select_model(long_data) in ['prophet', 'xgboost']

def test_confidence_intervals():
    data = generate_synthetic_data(length=100)
    result = forecast_engine.predict(data, horizon=60, confidence_levels=[0.95])
    
    # Проверка, что интервалы корректны (нижняя граница < прогноз < верхняя)
    assert all(result.ci_lower < result.forecast < result.ci_upper)
```

### Интеграционные тесты

```python
def test_full_pipeline():
    # Загрузка реальных данных из 1С
    data = load_1c_data('sales.xlsx')
    
    # Построение прогноза
    result = forecast_engine.predict(data['revenue'], horizon=90)
    
    # Проверка качества
    assert result.metrics['mape'] < 15
    assert result.model_info['name'] in SUPPORTED_MODELS
```

## 📚 Зависимости

```toml
# pyproject.toml
[tool.poetry.dependencies]
prophet = "^1.1"
statsmodels = "^0.14"
scikit-learn = "^1.3"
xgboost = "^1.7"
lightgbm = "^4.0"
tensorflow = "^2.13"  # опционально, для LSTM
plotly = "^5.15"
```

## 🚀 Roadmap реализации

| Неделя | Задача |
|--------|--------|
| 9 | Базовый интерфейс ForecastEngine, простые методы |
| 10 | Prophet + ARIMA, авто-выбор модели |
| 11 | XGBoost, ансамбли, кросс-валидация |
| 12 | Визуализация, интеграция с дашбордом |
