"""
Модуль прогнозирования временных рядов
Поддерживает: Prophet, XGBoost, Naive, Ensemble
Авто-выбор модели на основе характеристик данных
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import warnings

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# Отключаем предупреждения для чистоты логов
warnings.filterwarnings('ignore')


class ForecastResult:
    """Результат прогнозирования"""
    
    def __init__(
        self,
        forecast: pd.DataFrame,
        model_name: str,
        metrics: Dict[str, float],
        confidence_intervals: Optional[Dict[str, pd.DataFrame]] = None
    ):
        self.forecast = forecast  # DataFrame с колонками: ds, yhat, yhat_lower, yhat_upper
        self.model_name = model_name
        self.metrics = metrics  # MAPE, MAE, RMSE
        self.confidence_intervals = confidence_intervals or {}
    
    def to_dict(self) -> Dict:
        return {
            'model_name': self.model_name,
            'metrics': self.metrics,
            'forecast_points': len(self.forecast),
            'forecast_summary': {
                'mean': float(self.forecast['yhat'].mean()),
                'min': float(self.forecast['yhat'].min()),
                'max': float(self.forecast['yhat'].max()),
                'trend': self._detect_trend()
            }
        }
    
    def _detect_trend(self) -> str:
        """Определяет тренд"""
        if len(self.forecast) < 2:
            return "stable"
        
        first_half = self.forecast['yhat'].iloc[:len(self.forecast)//2].mean()
        second_half = self.forecast['yhat'].iloc[len(self.forecast)//2:].mean()
        
        change_pct = ((second_half - first_half) / first_half) * 100 if first_half != 0 else 0
        
        if change_pct > 5:
            return "growing"
        elif change_pct < -5:
            return "declining"
        else:
            return "stable"


class BaseForecaster(ABC):
    """Базовый класс для всех моделей прогнозирования"""
    
    @abstractmethod
    def fit(self, df: pd.DataFrame) -> 'BaseForecaster':
        pass
    
    @abstractmethod
    def predict(self, periods: int) -> pd.DataFrame:
        pass
    
    @abstractmethod
    def get_metrics(self) -> Dict[str, float]:
        pass


class NaiveForecaster(BaseForecaster):
    """Наивный прогноз: скользящее среднее"""
    
    def __init__(self, window: int = 7):
        self.window = window
        self.last_values: Optional[pd.Series] = None
        self.mean_value: float = 0
        self.std_value: float = 0
        self._metrics: Dict[str, float] = {}
    
    def fit(self, df: pd.DataFrame) -> 'NaiveForecaster':
        """Обучение на исторических данных"""
        if 'y' not in df.columns:
            raise ValueError("DataFrame должен содержать колонку 'y'")
        
        self.last_values = df['y'].tail(self.window)
        self.mean_value = df['y'].mean()
        self.std_value = df['y'].std() if len(df) > 1 else 0
        
        # Leave-one-out cross-validation для оценки качества
        if len(df) > self.window + 1:
            self._calculate_metrics(df)
        
        return self
    
    def _calculate_metrics(self, df: pd.DataFrame):
        """Расчёт метрик на исторических данных"""
        predictions = []
        actuals = []
        
        for i in range(self.window, len(df)):
            window_data = df['y'].iloc[i-self.window:i]
            pred = window_data.mean()
            predictions.append(pred)
            actuals.append(df['y'].iloc[i])
        
        if predictions:
            self._metrics = self._compute_metrics(actuals, predictions)
        else:
            self._metrics = {'MAPE': np.nan, 'MAE': np.nan, 'RMSE': np.nan}
    
    def predict(self, periods: int) -> pd.DataFrame:
        """Прогноз на periods шагов вперёд"""
        forecast_value = self.last_values.mean() if self.last_values is not None else self.mean_value
        
        # Создаём даты прогноза
        last_date = pd.Timestamp.now()
        dates = [last_date + timedelta(days=i+1) for i in range(periods)]
        
        # Генерируем прогноз с доверительным интервалом
        forecast_data = {
            'ds': dates,
            'yhat': [forecast_value] * periods,
            'yhat_lower': [max(0, forecast_value - 1.96 * self.std_value)] * periods,
            'yhat_upper': [forecast_value + 1.96 * self.std_value] * periods
        }
        
        return pd.DataFrame(forecast_data)
    
    def get_metrics(self) -> Dict[str, float]:
        return self._metrics
    
    @staticmethod
    def _compute_metrics(actuals: List[float], predictions: List[float]) -> Dict[str, float]:
        """Вычисление метрик качества"""
        actuals = np.array(actuals)
        predictions = np.array(predictions)
        
        # MAPE
        mask = actuals != 0
        if mask.sum() > 0:
            mape = np.mean(np.abs((actuals[mask] - predictions[mask]) / actuals[mask])) * 100
        else:
            mape = np.nan
        
        # MAE
        mae = np.mean(np.abs(actuals - predictions))
        
        # RMSE
        rmse = np.sqrt(np.mean((actuals - predictions) ** 2))
        
        return {
            'MAPE': float(mape),
            'MAE': float(mae),
            'RMSE': float(rmse)
        }


class ProphetForecaster(BaseForecaster):
    """Упрощённая реализация Prophet-подобного прогнозирования"""
    
    def __init__(self, seasonality_mode: str = 'additive', yearly_seasonality: bool = True):
        self.seasonality_mode = seasonality_mode
        self.yearly_seasonality = yearly_seasonality
        self.trend_slope: float = 0
        self.trend_intercept: float = 0
        self.seasonal_components: Dict[int, float] = {}
        self.residual_std: float = 0
        self._metrics: Dict[str, float] = {}
        self._fitted = False
    
    def fit(self, df: pd.DataFrame) -> 'ProphetForecaster':
        """Обучение модели с выделением тренда и сезонности"""
        if 'y' not in df.columns or 'ds' not in df.columns:
            raise ValueError("DataFrame должен содержать колонки 'y' и 'ds'")
        
        df = df.copy()
        df['ds'] = pd.to_datetime(df['ds'])
        df = df.sort_values('ds').reset_index(drop=True)
        
        # Выделение тренда (линейная регрессия)
        df['t'] = (df['ds'] - df['ds'].min()).dt.days
        slope, intercept, r_value, p_value, std_err = stats.linregress(df['t'], df['y'])
        
        self.trend_slope = slope
        self.trend_intercept = intercept
        self.trend_r_squared = r_value ** 2
        
        # Выделение сезонности (по дням года)
        if self.yearly_seasonality and len(df) >= 60:
            df['day_of_year'] = df['ds'].dt.dayofyear
            seasonal_means = df.groupby('day_of_year')['y'].mean()
            trend_values = self.trend_slope * df['t'] + self.trend_intercept
            df['trend'] = trend_values
            df['seasonal'] = df['y'] - df['trend']
            
            # Сглаживание сезонной компоненты
            self.seasonal_components = df.groupby('day_of_year')['seasonal'].mean().to_dict()
        
        # Оценка остаточной дисперсии
        predictions = self._predict_internal(df['ds'])
        residuals = df['y'] - predictions
        self.residual_std = residuals.std()
        
        # Расчёт метрик
        self._metrics = NaiveForecaster._compute_metrics(df['y'].tolist(), predictions.tolist())
        self._metrics['R_squared'] = float(self.trend_r_squared)
        
        self._fitted = True
        return self
    
    def _predict_internal(self, dates: pd.Series) -> pd.Series:
        """Внутренний прогноз для расчёта метрик"""
        min_date = pd.Timestamp.now() - timedelta(days=365)  # Примерная минимальная дата
        
        predictions = []
        for date in dates:
            # Базовый тренд
            if isinstance(date, (int, float)):
                t = date
            else:
                t = (date - min_date).days
            
            y_pred = self.trend_slope * t + self.trend_intercept
            
            # Добавляем сезонность
            if self.seasonal_components and hasattr(date, 'dayofyear'):
                doy = date.dayofyear
                if doy in self.seasonal_components:
                    y_pred += self.seasonal_components[doy]
            
            predictions.append(y_pred)
        
        return pd.Series(predictions)
    
    def predict(self, periods: int) -> pd.DataFrame:
        """Прогноз на periods дней вперёд"""
        if not self._fitted:
            raise RuntimeError("Модель не обучена. Вызовите fit() сначала.")
        
        start_date = pd.Timestamp.now() + timedelta(days=1)
        dates = [start_date + timedelta(days=i) for i in range(periods)]
        
        predictions = []
        lower_bounds = []
        upper_bounds = []
        
        min_date = pd.Timestamp.now() - timedelta(days=365)
        
        for date in dates:
            t = (date - min_date).days
            
            # Базовый тренд
            y_pred = self.trend_slope * t + self.trend_intercept
            
            # Сезонность
            if self.seasonal_components:
                doy = date.dayofyear
                if doy in self.seasonal_components:
                    y_pred += self.seasonal_components[doy]
            
            predictions.append(max(0, y_pred))  # Не отрицательные значения
            lower_bounds.append(max(0, y_pred - 1.96 * self.residual_std))
            upper_bounds.append(y_pred + 1.96 * self.residual_std)
        
        return pd.DataFrame({
            'ds': dates,
            'yhat': predictions,
            'yhat_lower': lower_bounds,
            'yhat_upper': upper_bounds
        })
    
    def get_metrics(self) -> Dict[str, float]:
        return self._metrics


class XGBoostForecaster(BaseForecaster):
    """Прогнозирование на основе градиентного бустинга (упрощённая версия без xgboost)"""
    
    def __init__(self, max_depth: int = 3, n_estimators: int = 50):
        self.max_depth = max_depth
        self.n_estimators = n_estimators
        self.features: List[str] = []
        self.coefficients: Dict[str, float] = {}
        self.base_prediction: float = 0
        self.residual_std: float = 0
        self._metrics: Dict[str, float] = {}
        self._fitted = False
    
    def _create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Создание признаков для временного ряда"""
        features = pd.DataFrame(index=df.index)
        
        # Временные признаки
        features['day_of_week'] = df['ds'].dt.dayofweek
        features['day_of_month'] = df['ds'].dt.day
        features['month'] = df['ds'].dt.month
        features['quarter'] = df['ds'].dt.quarter
        features['day_of_year'] = df['ds'].dt.dayofyear
        
        # Лаги
        for lag in [1, 7, 30]:
            if len(df) > lag:
                features[f'lag_{lag}'] = df['y'].shift(lag)
        
        # Скользящие статистики
        for window in [7, 30]:
            if len(df) >= window:
                features[f'ma_{window}'] = df['y'].rolling(window).mean()
                features[f'std_{window}'] = df['y'].rolling(window).std()
        
        # Тренд
        features['t'] = (df['ds'] - df['ds'].min()).dt.days
        
        return features
    
    def fit(self, df: pd.DataFrame) -> 'XGBoostForecaster':
        """Обучение упрощённой модели"""
        if 'y' not in df.columns or 'ds' not in df.columns:
            raise ValueError("DataFrame должен содержать колонки 'y' и 'ds'")
        
        df = df.copy()
        df['ds'] = pd.to_datetime(df['ds'])
        df = df.sort_values('ds').reset_index(drop=True)
        
        # Создание признаков
        X = self._create_features(df)
        y = df['y']
        
        # Удаление NaN (из-за лагов)
        mask = X.notna().all(axis=1)
        X = X[mask]
        y = y[mask]
        
        if len(X) < 10:
            logger.warning("Недостаточно данных для обучения XGBoost. Используем упрощённую модель.")
            return self._fit_simple(df)
        
        self.features = X.columns.tolist()
        self.base_prediction = y.mean()
        
        # Упрощённая линейная модель вместо XGBoost
        from sklearn.linear_model import Ridge
        
        model = Ridge(alpha=1.0)
        model.fit(X, y)
        
        self.coefficients = dict(zip(self.features, model.coef_))
        self.intercept = model.intercept_
        
        # Предсказания для метрик
        y_pred = model.predict(X)
        self._metrics = NaiveForecaster._compute_metrics(y.tolist(), y_pred.tolist())
        
        # Остаточная дисперсия
        self.residual_std = (y - y_pred).std()
        
        self._fitted = True
        return self
    
    def _fit_simple(self, df: pd.DataFrame) -> 'XGBoostForecaster':
        """Упрощённое обучение при малом количестве данных"""
        self.base_prediction = df['y'].mean()
        self.residual_std = df['y'].std()
        self._metrics = {'MAPE': np.nan, 'MAE': self.residual_std, 'RMSE': self.residual_std}
        self._fitted = True
        return self
    
    def predict(self, periods: int) -> pd.DataFrame:
        """Прогноз на periods дней вперёд"""
        if not self._fitted:
            raise RuntimeError("Модель не обучена.")
        
        if not self.features:  # Упрощённая модель
            return self._predict_simple(periods)
        
        start_date = pd.Timestamp.now() + timedelta(days=1)
        dates = [start_date + timedelta(days=i) for i in range(periods)]
        
        # Создаём признаки для прогноза (используем последние известные значения)
        # В реальной ситуации здесь нужны были бы последние фактические данные
        predictions = []
        
        for date in dates:
            pred = self.intercept
            
            # Добавляем вклад каждого признака (упрощённо)
            pred += self.coefficients.get('day_of_week', 0) * date.weekday()
            pred += self.coefficients.get('month', 0) * date.month
            pred += self.coefficients.get('t', 0) * 365  # Примерное значение
            
            predictions.append(max(0, pred))
        
        return pd.DataFrame({
            'ds': dates,
            'yhat': predictions,
            'yhat_lower': [max(0, p - 1.96 * self.residual_std) for p in predictions],
            'yhat_upper': [p + 1.96 * self.residual_std for p in predictions]
        })
    
    def _predict_simple(self, periods: int) -> pd.DataFrame:
        """Простой прогноз при недостатке данных"""
        start_date = pd.Timestamp.now() + timedelta(days=1)
        dates = [start_date + timedelta(days=i) for i in range(periods)]
        
        return pd.DataFrame({
            'ds': dates,
            'yhat': [self.base_prediction] * periods,
            'yhat_lower': [max(0, self.base_prediction - 1.96 * self.residual_std)] * periods,
            'yhat_upper': [self.base_prediction + 1.96 * self.residual_std] * periods
        })
    
    def get_metrics(self) -> Dict[str, float]:
        return self._metrics


class ModelSelector:
    """Авто-выбор лучшей модели прогнозирования"""
    
    @staticmethod
    def select_model(df: pd.DataFrame) -> str:
        """
        Выбирает модель на основе характеристик данных
        
        Правила:
        - < 30 точек: Naive
        - 30-100 точек: Prophet
        - > 100 точек: XGBoost
        - Есть явная сезонность: Prophet
        - Высокая волатильность: XGBoost
        """
        n_points = len(df)
        
        if n_points < 30:
            logger.info(f"Мало данных ({n_points} точек). Выбран NaiveForecaster.")
            return 'naive'
        
        # Проверка на сезонность
        has_seasonality = False
        if n_points >= 60:
            # Простая проверка сезонности через автокорреляцию
            if 'y' in df.columns:
                autocorr = df['y'].autocorr(lag=7)  # Недельная сезонность
                if autocorr > 0.3:
                    has_seasonality = True
        
        # Проверка волатильности
        volatility = df['y'].std() / df['y'].mean() if df['y'].mean() != 0 else 0
        
        if has_seasonality or n_points < 100:
            logger.info(f"Обнаружена сезонность или мало данных. Выбран ProphetForecaster.")
            return 'prophet'
        
        if volatility > 0.5:
            logger.info(f"Высокая волатильность ({volatility:.2f}). Выбран XGBoostForecaster.")
            return 'xgboost'
        
        if n_points > 100:
            logger.info(f"Много данных ({n_points} точек). Выбран XGBoostForecaster.")
            return 'xgboost'
        
        logger.info("Выбран ProphetForecaster по умолчанию.")
        return 'prophet'


class ForecastEngine:
    """Основной движок прогнозирования"""
    
    def __init__(self):
        self.models: Dict[str, BaseForecaster] = {}
        self.selected_model: Optional[str] = None
        self.result: Optional[ForecastResult] = None
    
    def prepare_data(
        self,
        df: pd.DataFrame,
        date_column: str,
        value_column: str
    ) -> pd.DataFrame:
        """Подготовка данных для прогнозирования"""
        df = df.copy()
        
        # Преобразование даты
        df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
        df = df.dropna(subset=[date_column])
        
        # Агрегация по дням (если данные чаще)
        df = df.groupby(df[date_column].dt.date)[value_column].sum().reset_index()
        df.rename(columns={date_column: 'ds', value_column: 'y'}, inplace=True)
        
        # Сортировка
        df = df.sort_values('ds').reset_index(drop=True)
        
        # Проверка на пропуски
        if df['y'].isna().any():
            logger.warning("Обнаружены пропуски в данных. Заполняем средним.")
            df['y'] = df['y'].fillna(df['y'].mean())
        
        return df
    
    def forecast(
        self,
        df: pd.DataFrame,
        date_column: str,
        value_column: str,
        periods: int = 30,
        model: Optional[str] = None
    ) -> ForecastResult:
        """
        Построение прогноза
        
        Args:
            df: Исходные данные
            date_column: Название колонки с датами
            value_column: Название колонки со значениями
            periods: Количество дней для прогноза
            model: Модель ('naive', 'prophet', 'xgboost') или None для авто-выбора
        
        Returns:
            ForecastResult с прогнозом и метриками
        """
        # Подготовка данных
        prepared_df = self.prepare_data(df, date_column, value_column)
        
        if len(prepared_df) < 10:
            logger.error(f"Недостаточно данных для прогноза: {len(prepared_df)} точек")
            raise ValueError("Требуется минимум 10 точек данных для прогноза")
        
        # Выбор модели
        if model is None:
            model = ModelSelector.select_model(prepared_df)
        
        self.selected_model = model
        
        # Создание и обучение модели
        if model == 'naive':
            forecaster = NaiveForecaster(window=min(7, len(prepared_df)//2))
        elif model == 'prophet':
            forecaster = ProphetForecaster()
        elif model == 'xgboost':
            forecaster = XGBoostForecaster()
        else:
            raise ValueError(f"Неизвестная модель: {model}")
        
        logger.info(f"Обучение модели: {model}")
        forecaster.fit(prepared_df)
        
        # Прогноз
        forecast_df = forecaster.predict(periods)
        
        # Метрики
        metrics = forecaster.get_metrics()
        
        # Доверительные интервалы
        confidence_intervals = {
            '80': forecast_df[['ds', 'yhat_lower', 'yhat_upper']].copy(),
            '95': forecast_df[['ds', 'yhat_lower', 'yhat_upper']].copy()
        }
        
        self.result = ForecastResult(
            forecast=forecast_df,
            model_name=model,
            metrics=metrics,
            confidence_intervals=confidence_intervals
        )
        
        logger.info(
            f"Прогноз построен: модель={model}, "
            f"MAPE={metrics.get('MAPE', 'N/A'):.2f}%, "
            f"точек прогноза={periods}"
        )
        
        return self.result
    
    def ensemble_forecast(
        self,
        df: pd.DataFrame,
        date_column: str,
        value_column: str,
        periods: int = 30,
        weights: Optional[Dict[str, float]] = None
    ) -> ForecastResult:
        """
        Ансамбль моделей (взвешенное усреднение)
        
        Args:
            weights: Веса моделей, например {'prophet': 0.5, 'xgboost': 0.3, 'naive': 0.2}
        """
        models_to_use = ['prophet', 'xgboost', 'naive']
        
        if weights is None:
            # Авто-веса на основе количества данных
            n_points = len(df)
            if n_points < 50:
                weights = {'prophet': 0.5, 'naive': 0.3, 'xgboost': 0.2}
            elif n_points < 100:
                weights = {'prophet': 0.4, 'xgboost': 0.4, 'naive': 0.2}
            else:
                weights = {'xgboost': 0.5, 'prophet': 0.3, 'naive': 0.2}
        
        forecasts = []
        final_weights = []
        
        for model_name in models_to_use:
            try:
                result = self.forecast(df, date_column, value_column, periods, model=model_name)
                forecasts.append(result.forecast)
                final_weights.append(weights.get(model_name, 0.33))
                self.models[model_name] = getattr(self, f'{model_name}_model', None)
            except Exception as e:
                logger.warning(f"Модель {model_name} не сработала: {e}")
                continue
        
        if not forecasts:
            raise RuntimeError("Ни одна модель не смогла построить прогноз")
        
        # Нормализация весов
        total_weight = sum(final_weights)
        final_weights = [w / total_weight for w in final_weights]
        
        # Взвешенное усреднение
        ensemble_forecast = forecasts[0].copy()
        ensemble_forecast['yhat'] = sum(
            f['yhat'] * w for f, w in zip(forecasts, final_weights)
        )
        ensemble_forecast['yhat_lower'] = sum(
            f['yhat_lower'] * w for f, w in zip(forecasts, final_weights)
        )
        ensemble_forecast['yhat_upper'] = sum(
            f['yhat_upper'] * w for f, w in zip(forecasts, final_weights)
        )
        
        # Средние метрики
        avg_metrics = {}
        for result in forecasts:
            # result - это ForecastResult, а не DataFrame
            if hasattr(result, 'metrics') and isinstance(result.metrics, dict):
                for key, value in result.metrics.items():
                    if not np.isnan(value):
                        if key not in avg_metrics:
                            avg_metrics[key] = []
                        avg_metrics[key].append(value)
        
        avg_metrics = {k: np.mean(v) for k, v in avg_metrics.items()}
        
        self.result = ForecastResult(
            forecast=ensemble_forecast,
            model_name='ensemble',
            metrics=avg_metrics,
            confidence_intervals={'95': ensemble_forecast[['ds', 'yhat_lower', 'yhat_upper']]}
        )
        
        mape_value = avg_metrics.get('MAPE', 0)
        if isinstance(mape_value, (int, float)) and not np.isnan(mape_value):
            logger.info(f"Ансамбль построен: MAPE={mape_value:.2f}%")
        else:
            logger.info("Ансамбль построен")
        
        return self.result


def forecast_revenue(
    df: pd.DataFrame,
    date_column: str = 'date',
    value_column: str = 'revenue',
    periods: int = 30,
    use_ensemble: bool = True
) -> ForecastResult:
    """
    Удобная функция для прогноза выручки
    
    Args:
        df: DataFrame с данными
        date_column: Колонка с датами
        value_column: Колонка со значениями
        periods: Дней для прогноза
        use_ensemble: Использовать ансамбль моделей
    
    Returns:
        ForecastResult
    """
    engine = ForecastEngine()
    
    if use_ensemble and len(df) >= 50:
        return engine.ensemble_forecast(df, date_column, value_column, periods)
    else:
        return engine.forecast(df, date_column, value_column, periods)
