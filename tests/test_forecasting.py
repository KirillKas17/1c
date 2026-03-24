"""
Тесты для модуля прогнозирования (forecasting.py)
Проверка всех моделей, метрик и edge cases
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.core.forecasting import (
    NaiveForecaster,
    ProphetForecaster,
    XGBoostForecaster,
    ModelSelector,
    ForecastEngine,
    ForecastResult,
    forecast_revenue
)


def create_test_data(
    n_points: int = 100,
    trend: float = 0.5,
    seasonality: bool = True,
    noise: float = 10.0,
    start_date: str = '2023-01-01'
) -> pd.DataFrame:
    """Создание тестовых временных рядов"""
    dates = [pd.Timestamp(start_date) + timedelta(days=i) for i in range(n_points)]
    
    # Базовый тренд
    base = np.arange(n_points) * trend + 100
    
    # Сезонность
    if seasonality:
        seasonal = 20 * np.sin(np.arange(n_points) * 2 * np.pi / 7)  # Недельная
    else:
        seasonal = 0
    
    # Шум
    np.random.seed(42)
    noise_array = np.random.normal(0, noise, n_points)
    
    values = base + seasonal + noise_array
    
    return pd.DataFrame({
        'ds': dates,
        'y': values
    })


class TestNaiveForecaster:
    """Тесты наивного прогноза"""
    
    def test_fit_basic(self):
        """Базовое обучение"""
        df = create_test_data(50)
        forecaster = NaiveForecaster(window=7)
        result = forecaster.fit(df)
        
        assert result is not None
        assert forecaster.mean_value > 0
        assert forecaster.std_value > 0
    
    def test_predict_returns_dataframe(self):
        """Прогноз возвращает DataFrame"""
        df = create_test_data(50)
        forecaster = NaiveForecaster(window=7)
        forecaster.fit(df)
        
        forecast = forecaster.predict(periods=10)
        
        assert isinstance(forecast, pd.DataFrame)
        assert len(forecast) == 10
        assert 'ds' in forecast.columns
        assert 'yhat' in forecast.columns
        assert 'yhat_lower' in forecast.columns
        assert 'yhat_upper' in forecast.columns
    
    def test_metrics_calculation(self):
        """Расчёт метрик качества"""
        df = create_test_data(100)
        forecaster = NaiveForecaster(window=7)
        forecaster.fit(df)
        
        metrics = forecaster.get_metrics()
        
        assert 'MAPE' in metrics
        assert 'MAE' in metrics
        assert 'RMSE' in metrics
        assert metrics['MAE'] >= 0
        assert metrics['RMSE'] >= 0
    
    def test_edge_case_small_data(self):
        """Мало данных для обучения"""
        df = create_test_data(10)
        forecaster = NaiveForecaster(window=5)
        forecaster.fit(df)
        
        forecast = forecaster.predict(periods=5)
        assert len(forecast) == 5
    
    def test_confidence_intervals(self):
        """Доверительные интервалы корректны"""
        df = create_test_data(50)
        forecaster = NaiveForecaster(window=7)
        forecaster.fit(df)
        
        forecast = forecaster.predict(periods=10)
        
        # Верхняя граница > прогноз > нижняя граница
        assert (forecast['yhat_upper'] > forecast['yhat']).all()
        assert (forecast['yhat'] > forecast['yhat_lower']).all()


class TestProphetForecaster:
    """Тесты Prophet-подобной модели"""
    
    def test_fit_with_trend(self):
        """Обучение с трендом"""
        df = create_test_data(100, trend=1.0)
        forecaster = ProphetForecaster()
        result = forecaster.fit(df)
        
        assert result is not None
        assert abs(forecaster.trend_slope) > 0
    
    def test_seasonality_detection(self):
        """Обнаружение сезонности"""
        df = create_test_data(100, seasonality=True, noise=5)
        forecaster = ProphetForecaster(yearly_seasonality=True)
        forecaster.fit(df)
        
        # Должны быть сезонные компоненты
        assert len(forecaster.seasonal_components) > 0
    
    def test_predict_periods(self):
        """Прогноз на разное количество периодов"""
        df = create_test_data(100)
        forecaster = ProphetForecaster()
        forecaster.fit(df)
        
        for periods in [7, 30, 90]:
            forecast = forecaster.predict(periods)
            assert len(forecast) == periods
    
    def test_r_squared_metric(self):
        """Метрика R² рассчитывается"""
        df = create_test_data(100, trend=1.0, noise=5)
        forecaster = ProphetForecaster()
        forecaster.fit(df)
        
        metrics = forecaster.get_metrics()
        
        assert 'R_squared' in metrics
        assert 0 <= metrics['R_squared'] <= 1
    
    def test_edge_case_no_seasonality(self):
        """Нет сезонности в данных"""
        df = create_test_data(50, seasonality=False)
        forecaster = ProphetForecaster(yearly_seasonality=False)
        forecaster.fit(df)
        
        forecast = forecaster.predict(periods=10)
        assert len(forecast) == 10


class TestXGBoostForecaster:
    """Тесты XGBoost-подобной модели"""
    
    def test_feature_creation(self):
        """Создание признаков"""
        df = create_test_data(100)
        forecaster = XGBoostForecaster()
        
        features = forecaster._create_features(df)
        
        assert 'day_of_week' in features.columns
        assert 'month' in features.columns
        assert 'lag_7' in features.columns
        assert 'ma_7' in features.columns
    
    def test_fit_and_predict(self):
        """Обучение и прогноз"""
        df = create_test_data(100)
        forecaster = XGBoostForecaster()
        forecaster.fit(df)
        
        forecast = forecaster.predict(periods=14)
        
        assert len(forecast) == 14
        assert 'yhat' in forecast.columns
    
    def test_simple_fallback(self):
        """Упрощённая модель при малых данных"""
        df = create_test_data(20)
        forecaster = XGBoostForecaster()
        forecaster.fit(df)
        
        forecast = forecaster.predict(periods=7)
        assert len(forecast) == 7
    
    def test_metrics_present(self):
        """Метрики качества"""
        df = create_test_data(100)
        forecaster = XGBoostForecaster()
        forecaster.fit(df)
        
        metrics = forecaster.get_metrics()
        
        assert 'MAPE' in metrics or 'MAE' in metrics


class TestModelSelector:
    """Тесты авто-выбора модели"""
    
    def test_select_naive_for_small_data(self):
        """Мало данных → Naive"""
        df = create_test_data(20)
        model = ModelSelector.select_model(df)
        assert model == 'naive'
    
    def test_select_prophet_for_medium_data(self):
        """Средние данные → Prophet"""
        df = create_test_data(80)
        model = ModelSelector.select_model(df)
        assert model == 'prophet'
    
    def test_select_xgboost_for_large_data(self):
        """Большие данные → XGBoost"""
        df = create_test_data(150, trend=1.0, noise=20)  # Высокая волатильность
        model = ModelSelector.select_model(df)
        # Модель может выбрать prophet из-за сезонности или xgboost из-за размера
        assert model in ['xgboost', 'prophet']
    
    def test_select_prophet_for_seasonal(self):
        """Есть сезонность → Prophet"""
        df = create_test_data(100, seasonality=True, noise=5)
        model = ModelSelector.select_model(df)
        assert model == 'prophet'


class TestForecastEngine:
    """Тесты основного движка прогнозирования"""
    
    def test_prepare_data(self):
        """Подготовка данных"""
        raw_df = pd.DataFrame({
            'date': pd.date_range('2023-01-01', periods=50),
            'revenue': np.random.uniform(100, 200, 50)
        })
        
        engine = ForecastEngine()
        prepared = engine.prepare_data(raw_df, 'date', 'revenue')
        
        assert 'ds' in prepared.columns
        assert 'y' in prepared.columns
        assert len(prepared) == 50
    
    def test_forecast_auto_model(self):
        """Авто-выбор модели и прогноз"""
        df = create_test_data(100)
        engine = ForecastEngine()
        
        result = engine.forecast(df, 'ds', 'y', periods=30)
        
        assert isinstance(result, ForecastResult)
        assert len(result.forecast) == 30
        assert result.model_name in ['naive', 'prophet', 'xgboost']
    
    def test_forecast_with_specific_model(self):
        """Прогноз с указанной моделью"""
        df = create_test_data(100)
        engine = ForecastEngine()
        
        result = engine.forecast(df, 'ds', 'y', periods=14, model='naive')
        
        assert result.model_name == 'naive'
    
    def test_ensemble_forecast(self):
        """Ансамбль моделей"""
        df = create_test_data(100)
        engine = ForecastEngine()
        
        result = engine.ensemble_forecast(df, 'ds', 'y', periods=30)
        
        assert result.model_name == 'ensemble'
        assert len(result.forecast) == 30
    
    def test_forecast_result_to_dict(self):
        """Конвертация результата в dict"""
        df = create_test_data(100)
        engine = ForecastEngine()
        result = engine.forecast(df, 'ds', 'y', periods=14)
        
        result_dict = result.to_dict()
        
        assert 'model_name' in result_dict
        assert 'metrics' in result_dict
        assert 'forecast_summary' in result_dict
        assert 'trend' in result_dict['forecast_summary']
    
    def test_edge_case_insufficient_data(self):
        """Недостаточно данных"""
        df = create_test_data(5)
        engine = ForecastEngine()
        
        with pytest.raises(ValueError, match="минимум 10 точек"):
            engine.forecast(df, 'ds', 'y', periods=7)


class TestForecastRevenue:
    """Тесты удобной функции прогноза выручки"""
    
    def test_forecast_revenue_basic(self):
        """Базовый прогноз выручки"""
        df = pd.DataFrame({
            'date': pd.date_range('2023-01-01', periods=60),
            'revenue': np.random.uniform(1000, 2000, 60)
        })
        
        result = forecast_revenue(df, 'date', 'revenue', periods=14)
        
        assert isinstance(result, ForecastResult)
        assert len(result.forecast) == 14
    
    def test_forecast_revenue_ensemble(self):
        """Прогноз с ансамблем"""
        df = pd.DataFrame({
            'date': pd.date_range('2023-01-01', periods=100),
            'revenue': np.random.uniform(1000, 2000, 100)
        })
        
        result = forecast_revenue(df, 'date', 'revenue', periods=30, use_ensemble=True)
        
        assert result.model_name == 'ensemble'


class TestTrendDetection:
    """Тесты определения тренда"""
    
    def test_growing_trend(self):
        """Растущий тренд"""
        forecast_df = pd.DataFrame({
            'ds': pd.date_range('2024-01-01', periods=30),
            'yhat': list(range(100, 130))
        })
        
        result = ForecastResult(
            forecast=forecast_df,
            model_name='test',
            metrics={}
        )
        
        assert result.to_dict()['forecast_summary']['trend'] == 'growing'
    
    def test_declining_trend(self):
        """Падающий тренд"""
        forecast_df = pd.DataFrame({
            'ds': pd.date_range('2024-01-01', periods=30),
            'yhat': list(range(130, 100, -1))
        })
        
        result = ForecastResult(
            forecast=forecast_df,
            model_name='test',
            metrics={}
        )
        
        assert result.to_dict()['forecast_summary']['trend'] == 'declining'
    
    def test_stable_trend(self):
        """Стабильный тренд"""
        np.random.seed(42)
        forecast_df = pd.DataFrame({
            'ds': pd.date_range('2024-01-01', periods=30),
            'yhat': 100 + np.random.normal(0, 2, 30)
        })
        
        result = ForecastResult(
            forecast=forecast_df,
            model_name='test',
            metrics={}
        )
        
        assert result.to_dict()['forecast_summary']['trend'] == 'stable'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
