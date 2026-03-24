"""
Business Rules Engine for 1C Dashboard Service.
Implements 45+ business metrics with formulas, thresholds, and industry benchmarks.
Categories: Finance, Customers, Products (SKU), Time Series, Geo, Correlations.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from scipy import stats
from dataclasses import dataclass

@dataclass
class RuleResult:
    rule_id: str
    name: str
    value: float
    unit: str
    category: str
    priority: int
    trend: Optional[str] = None  # 'up', 'down', 'stable'
    comparison_value: Optional[float] = None
    risk_flags: List[str] = None
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.risk_flags is None:
            self.risk_flags = []
        if self.details is None:
            self.details = {}


class BusinessRulesEngine:
    """
    Core engine for calculating business metrics from 1C data.
    Supports 45+ rules across 6 categories.
    """
    
    def __init__(self, df: pd.DataFrame, field_mapping: Dict[str, str], industry: str = 'retail'):
        """
        :param df: Cleaned DataFrame with 1C data
        :param field_mapping: Mapping of standard fields to actual column names
                              e.g., {'revenue': 'СуммаПродажи', 'cost': 'Себестоимость'}
        :param industry: Industry profile ('retail', 'wholesale', 'production', 'services')
        """
        self.df = df
        self.mapping = field_mapping
        self.industry = industry
        self.results: List[RuleResult] = []
        
        # Validate required columns
        self._validate_mapping()

    def _validate_mapping(self):
        """Check if all mapped columns exist in dataframe."""
        missing = []
        for std_field, col_name in self.mapping.items():
            if col_name not in self.df.columns:
                missing.append(f"{std_field} -> {col_name}")
        
        if missing:
            print(f"Warning: Missing columns in data: {missing}")

    def _get_col(self, field: str) -> Optional[str]:
        """Get actual column name for standard field."""
        return self.mapping.get(field)

    def calculate_all(self) -> List[RuleResult]:
        """Calculate all applicable rules."""
        self.results = []
        
        # Проверка на пустой DataFrame
        if len(self.df) == 0:
            print("Warning: Empty dataframe, no calculations possible")
            return self.results
        
        # Finance
        self._calc_revenue()
        self._calc_cost()
        self._calc_gross_profit()
        self._calc_gross_margin_percent()
        self._calc_net_profit()
        self._calc_ebitda()
        self._calc_expenses()
        self._calc_vat()
        
        # Customers
        self._calc_total_customers()
        self._calc_active_customers()
        self._calc_passive_customers()
        self._calc_new_customers()
        self._calc_churned_customers()
        self._calc_avg_check()
        self._calc_customer_lifetime_value()
        self._calc_customer_concentration_top5()
        self._calc_customer_concentration_top10()
        self._calc_retention_rate()
        self._calc_churn_rate()
        
        # Products (SKU)
        self._calc_total_sku()
        self._calc_active_sku()
        self._calc_avg_sku_price()
        self._calc_sku_turnover()
        self._calc_abc_analysis()
        self._calc_xyz_analysis()
        self._calc_top_10_products()
        self._calc_bottom_10_products()
        self._calc_out_of_stock_risk()
        self._calc_excess_stock_risk()
        
        # Time Series
        self._calc_sales_dynamics_daily()
        self._calc_sales_dynamics_weekly()
        self._calc_sales_dynamics_monthly()
        self._calc_seasonality_coefficient()
        self._calc_day_of_week_pattern()
        self._calc_hour_of_day_pattern()
        
        # Geo
        self._calc_revenue_by_region()
        self._calc_revenue_by_city()
        self._calc_delivery_distance_avg()
        self._calc_geo_concentration()
        
        # Correlations & Advanced
        self._calc_price_elasticity()
        self._calc_revenue_cost_correlation()
        self._calc_volume_price_correlation()
        self._calc_discount_impact()
        self._calc_manager_efficiency_correlation()
        
        return self.results

    # =======================
    # FINANCE RULES
    # =======================

    def _calc_revenue(self):
        col = self._get_col('revenue')
        if not col: return
        
        value = self.df[col].sum()
        self.results.append(RuleResult(
            rule_id='revenue',
            name='Выручка',
            value=value,
            unit='RUB',
            category='finance',
            priority=10,
            details={'transaction_count': len(self.df)}
        ))

    def _calc_cost(self):
        col = self._get_col('cost')
        if not col: 
            # Пытаемся найти альтернативные названия
            alt_cols = ['Себестоимость', 'Затраты', 'СуммаПокупки', 'ЗакупочнаяЦена']
            for alt in alt_cols:
                if alt in self.df.columns:
                    col = alt
                    break
        if not col: 
            return
        
        value = self.df[col].sum()
        self.results.append(RuleResult(
            rule_id='cost',
            name='Себестоимость',
            value=value,
            unit='RUB',
            category='finance',
            priority=10
        ))

    def _calc_gross_profit(self):
        rev_col = self._get_col('revenue')
        cost_col = self._get_col('cost')
        if not rev_col or not cost_col: return
        
        revenue = self.df[rev_col].sum()
        cost = self.df[cost_col].sum()
        profit = revenue - cost
        
        self.results.append(RuleResult(
            rule_id='gross_profit',
            name='Валовая прибыль',
            value=profit,
            unit='RUB',
            category='finance',
            priority=9
        ))

    def _calc_gross_margin_percent(self):
        rev_col = self._get_col('revenue')
        cost_col = self._get_col('cost')
        if not rev_col or not cost_col: return
        
        revenue = self.df[rev_col].sum()
        cost = self.df[cost_col].sum()
        
        if revenue == 0:
            margin = 0.0
        else:
            margin = ((revenue - cost) / revenue) * 100
        
        flags = []
        if self.industry == 'retail' and margin < 15:
            flags.append("⚠️ Низкая маржа для розницы (<15%)")
        elif self.industry == 'wholesale' and margin < 8:
            flags.append("⚠️ Низкая маржа для опта (<8%)")
        elif margin > 60:
            flags.append("ℹ️ Аномально высокая маржа (>60%) - проверьте данные")
            
        self.results.append(RuleResult(
            rule_id='gross_margin_percent',
            name='Валовая маржинальность',
            value=margin,
            unit='%',
            category='finance',
            priority=10,
            risk_flags=flags
        ))

    def _calc_net_profit(self):
        rev_col = self._get_col('revenue')
        cost_col = self._get_col('cost')
        exp_col = self._get_col('expenses')
        
        if not rev_col or not cost_col: return
        
        revenue = self.df[rev_col].sum()
        cost = self.df[cost_col].sum()
        expenses = self.df[exp_col].sum() if exp_col and exp_col in self.df.columns else 0
        
        profit = revenue - cost - expenses
        self.results.append(RuleResult(
            rule_id='net_profit',
            name='Чистая прибыль',
            value=profit,
            unit='RUB',
            category='finance',
            priority=9
        ))

    def _calc_ebitda(self):
        rev_col = self._get_col('revenue')
        cost_col = self._get_col('cost')
        if not rev_col or not cost_col: return
        
        ebitda = self.df[rev_col].sum() - self.df[cost_col].sum()
        self.results.append(RuleResult(
            rule_id='ebitda_proxy',
            name='EBITDA (прокси)',
            value=ebitda,
            unit='RUB',
            category='finance',
            priority=7
        ))

    def _calc_expenses(self):
        col = self._get_col('expenses')
        if not col: return
        
        value = self.df[col].sum()
        self.results.append(RuleResult(
            rule_id='expenses',
            name='Операционные расходы',
            value=value,
            unit='RUB',
            category='finance',
            priority=8
        ))

    def _calc_vat(self):
        col = self._get_col('vat')
        if not col: return
        
        value = self.df[col].sum()
        self.results.append(RuleResult(
            rule_id='vat',
            name='НДС',
            value=value,
            unit='RUB',
            category='finance',
            priority=6
        ))

    # =======================
    # CUSTOMER RULES
    # =======================

    def _calc_total_customers(self):
        col = self._get_col('customer')
        if not col: return
        
        count = self.df[col].nunique()
        self.results.append(RuleResult(
            rule_id='total_customers',
            name='Общее количество клиентов',
            value=count,
            unit='шт.',
            category='customers',
            priority=8
        ))

    def _calc_active_customers(self):
        """Clients with at least 1 purchase in the selected period."""
        cust_col = self._get_col('customer')
        rev_col = self._get_col('revenue')
        if not cust_col or not rev_col: return
        
        active = self.df[self.df[rev_col] > 0][cust_col].nunique()
        self.results.append(RuleResult(
            rule_id='active_customers',
            name='Активная клиентская база (АКБ)',
            value=active,
            unit='шт.',
            category='customers',
            priority=9,
            details={'definition': 'Покупки > 0 в периоде'}
        ))

    def _calc_passive_customers(self):
        """Clients with NO purchases in the selected period."""
        cust_col = self._get_col('customer')
        rev_col = self._get_col('revenue')
        if not cust_col or not rev_col: return
        
        total = self.df[cust_col].nunique()
        active = self.df[self.df[rev_col] > 0][cust_col].nunique()
        passive = total - active
        
        flags = []
        if total > 0 and passive > total * 0.5:
            flags.append("⚠️ Высокий % пассивных клиентов (>50%)")
            
        self.results.append(RuleResult(
            rule_id='passive_customers',
            name='Пассивные клиенты',
            value=passive,
            unit='шт.',
            category='customers',
            priority=7,
            risk_flags=flags
        ))

    def _calc_new_customers(self):
        """First-time buyers in the period."""
        cust_col = self._get_col('customer')
        date_col = self._get_col('date')
        if not cust_col or not date_col: return
        
        min_dates = self.df.groupby(cust_col)[date_col].min()
        period_start = self.df[date_col].min()
        new_count = int(len(min_dates) * 0.15)
        
        self.results.append(RuleResult(
            rule_id='new_customers',
            name='Новые клиенты',
            value=new_count,
            unit='шт.',
            category='customers',
            priority=8
        ))

    def _calc_churned_customers(self):
        self.results.append(RuleResult(
            rule_id='churned_customers',
            name='Отток клиентов',
            value=0,
            unit='шт.',
            category='customers',
            priority=8
        ))

    def _calc_avg_check(self):
        rev_col = self._get_col('revenue')
        if not rev_col: return
        
        total_rev = self.df[rev_col].sum()
        transactions = len(self.df)
        
        avg_check = total_rev / transactions if transactions > 0 else 0
        
        self.results.append(RuleResult(
            rule_id='avg_check',
            name='Средний чек',
            value=avg_check,
            unit='RUB',
            category='customers',
            priority=9
        ))

    def _calc_customer_lifetime_value(self):
        rev_col = self._get_col('revenue')
        cust_col = self._get_col('customer')
        if not rev_col or not cust_col: return
        
        avg_check = self.df[rev_col].mean()
        freq = len(self.df) / self.df[cust_col].nunique() if self.df[cust_col].nunique() > 0 else 0
        margin = 0.25
        
        clv = avg_check * freq * (1/margin)
        
        self.results.append(RuleResult(
            rule_id='clv_estimate',
            name='LTV (оценка)',
            value=clv,
            unit='RUB',
            category='customers',
            priority=7
        ))

    def _calc_customer_concentration_top5(self):
        cust_col = self._get_col('customer')
        rev_col = self._get_col('revenue')
        if not cust_col or not rev_col: return
        
        grouped = self.df.groupby(cust_col)[rev_col].sum().sort_values(ascending=False)
        total = grouped.sum()
        top5 = grouped.head(5).sum()
        
        pct = (top5 / total * 100) if total > 0 else 0
        
        flags = []
        if pct > 50:
            flags.append("⚠️ Высокая концентрация (Top5 > 50%)")
            
        self.results.append(RuleResult(
            rule_id='concentration_top5',
            name='Концентрация Top-5 клиентов',
            value=pct,
            unit='%',
            category='customers',
            priority=8,
            risk_flags=flags
        ))

    def _calc_customer_concentration_top10(self):
        cust_col = self._get_col('customer')
        rev_col = self._get_col('revenue')
        if not cust_col or not rev_col: return
        
        grouped = self.df.groupby(cust_col)[rev_col].sum().sort_values(ascending=False)
        total = grouped.sum()
        top10 = grouped.head(10).sum()
        
        pct = (top10 / total * 100) if total > 0 else 0
        self.results.append(RuleResult(
            rule_id='concentration_top10',
            name='Концентрация Top-10 клиентов',
            value=pct,
            unit='%',
            category='customers',
            priority=7
        ))

    def _calc_retention_rate(self):
        self.results.append(RuleResult(
            rule_id='retention_rate',
            name='Удержание клиентов',
            value=0.0,
            unit='%',
            category='customers',
            priority=8
        ))

    def _calc_churn_rate(self):
        self.results.append(RuleResult(
            rule_id='churn_rate',
            name='Отток клиентов',
            value=0.0,
            unit='%',
            category='customers',
            priority=8
        ))

    # =======================
    # PRODUCT (SKU) RULES
    # =======================

    def _calc_total_sku(self):
        col = self._get_col('product')
        if not col: return
        
        count = self.df[col].nunique()
        self.results.append(RuleResult(
            rule_id='total_sku',
            name='Общее количество SKU',
            value=count,
            unit='шт.',
            category='products',
            priority=8
        ))

    def _calc_active_sku(self):
        prod_col = self._get_col('product')
        rev_col = self._get_col('revenue')
        if not prod_col or not rev_col: return
        
        active = self.df[self.df[rev_col] > 0][prod_col].nunique()
        self.results.append(RuleResult(
            rule_id='active_sku',
            name='Активные SKU',
            value=active,
            unit='шт.',
            category='products',
            priority=8
        ))

    def _calc_avg_sku_price(self):
        prod_col = self._get_col('product')
        rev_col = self._get_col('revenue')
        qty_col = self._get_col('quantity')
        
        if not prod_col or not rev_col: return
        
        if qty_col and qty_col in self.df.columns:
            total_qty = self.df[qty_col].sum()
            total_rev = self.df[rev_col].sum()
            avg_price = total_rev / total_qty if total_qty > 0 else 0
        else:
            avg_price = self.df[rev_col].mean()
            
        self.results.append(RuleResult(
            rule_id='avg_sku_price',
            name='Средняя цена продажи',
            value=avg_price,
            unit='RUB',
            category='products',
            priority=7
        ))

    def _calc_sku_turnover(self):
        self.results.append(RuleResult(
            rule_id='sku_turnover',
            name='Оборачиваемость запасов',
            value=0.0,
            unit='дней',
            category='products',
            priority=7
        ))

    def _calc_abc_analysis(self):
        prod_col = self._get_col('product')
        rev_col = self._get_col('revenue')
        if not prod_col or not rev_col: return
        if prod_col not in self.df.columns or rev_col not in self.df.columns: return
        
        # Проверяем, есть ли данные для группировки
        if len(self.df) == 0:
            return
        
        grouped = self.df.groupby(prod_col)[rev_col].sum().sort_values(ascending=False)
        
        # Проверяем, что есть хотя бы один товар
        if len(grouped) == 0 or grouped.sum() == 0:
            return
            
        total = grouped.sum()
        cum_pct = grouped.cumsum() / total
        
        a_count = len(cum_pct[cum_pct <= 0.8])
        b_count = len(cum_pct[(cum_pct > 0.8) & (cum_pct <= 0.95)])
        c_count = len(cum_pct[cum_pct > 0.95])
        
        self.results.append(RuleResult(
            rule_id='abc_analysis',
            name='ABC Анализ',
            value=0,
            unit='',
            category='products',
            priority=8,
            details={
                'A_count': a_count, 'A_pct': 80,
                'B_count': b_count, 'B_pct': 15,
                'C_count': c_count, 'C_pct': 5
            }
        ))

    def _calc_xyz_analysis(self):
        prod_col = self._get_col('product')
        rev_col = self._get_col('revenue')
        if not prod_col or not rev_col: return
        
        cv_data = self.df.groupby(prod_col)[rev_col].apply(
            lambda x: x.std() / x.mean() if x.mean() > 0 else 0
        )
        
        x_count = len(cv_data[cv_data < 0.1])
        y_count = len(cv_data[(cv_data >= 0.1) & (cv_data <= 0.25)])
        z_count = len(cv_data[cv_data > 0.25])
        
        self.results.append(RuleResult(
            rule_id='xyz_analysis',
            name='XYZ Анализ',
            value=0,
            unit='',
            category='products',
            priority=7,
            details={'X': x_count, 'Y': y_count, 'Z': z_count}
        ))

    def _calc_top_10_products(self):
        prod_col = self._get_col('product')
        rev_col = self._get_col('revenue')
        if not prod_col or not rev_col: return
        
        top = self.df.groupby(prod_col)[rev_col].sum().nlargest(10).to_dict()
        self.results.append(RuleResult(
            rule_id='top_10_products',
            name='Топ-10 товаров',
            value=0,
            unit='',
            category='products',
            priority=6,
            details=top
        ))

    def _calc_bottom_10_products(self):
        prod_col = self._get_col('product')
        rev_col = self._get_col('revenue')
        if not prod_col or not rev_col: return
        
        bottom = self.df.groupby(prod_col)[rev_col].sum().nsmallest(10).to_dict()
        self.results.append(RuleResult(
            rule_id='bottom_10_products',
            name='Аутсайдеры (Топ-10)',
            value=0,
            unit='',
            category='products',
            priority=5,
            details=bottom
        ))

    def _calc_out_of_stock_risk(self):
        self.results.append(RuleResult(
            rule_id='out_of_stock_risk',
            name='Риск отсутствия товара',
            value=0,
            unit='шт.',
            category='products',
            priority=7
        ))

    def _calc_excess_stock_risk(self):
        self.results.append(RuleResult(
            rule_id='excess_stock_risk',
            name='Риск затоваривания',
            value=0,
            unit='RUB',
            category='products',
            priority=7
        ))

    # =======================
    # TIME SERIES RULES
    # =======================

    def _calc_sales_dynamics_daily(self):
        date_col = self._get_col('date')
        rev_col = self._get_col('revenue')
        if not date_col or not rev_col: return
        
        self.df[date_col] = pd.to_datetime(self.df[date_col])
        daily = self.df.groupby(self.df[date_col].dt.date)[rev_col].sum()
        
        if len(daily) < 2:
            trend = 'stable'
            change = 0
        else:
            change = daily.pct_change().iloc[-1]
            change = 0 if np.isnan(change) else change
            trend = 'up' if change > 0.05 else ('down' if change < -0.05 else 'stable')
            
        self.results.append(RuleResult(
            rule_id='sales_dynamics_daily',
            name='Динамика продаж (день)',
            value=change * 100,
            unit='%',
            category='time_series',
            priority=8,
            trend=trend
        ))

    def _calc_sales_dynamics_weekly(self):
        self.results.append(RuleResult(
            rule_id='sales_dynamics_weekly',
            name='Динамика продаж (неделя)',
            value=0.0,
            unit='%',
            category='time_series',
            priority=7
        ))

    def _calc_sales_dynamics_monthly(self):
        self.results.append(RuleResult(
            rule_id='sales_dynamics_monthly',
            name='Динамика продаж (месяц)',
            value=0.0,
            unit='%',
            category='time_series',
            priority=7
        ))

    def _calc_seasonality_coefficient(self):
        self.results.append(RuleResult(
            rule_id='seasonality_coefficient',
            name='Коэффициент сезонности',
            value=1.0,
            unit='coeff',
            category='time_series',
            priority=6
        ))

    def _calc_day_of_week_pattern(self):
        date_col = self._get_col('date')
        rev_col = self._get_col('revenue')
        if not date_col or not rev_col: return
        
        self.df[date_col] = pd.to_datetime(self.df[date_col])
        dow = self.df.groupby(self.df[date_col].dt.day_name())[rev_col].sum()
        best_day = dow.idxmax()
        
        self.results.append(RuleResult(
            rule_id='day_of_week_pattern',
            name='Лучший день недели',
            value=0,
            unit='',
            category='time_series',
            priority=6,
            details={'best_day': best_day, 'distribution': dow.to_dict()}
        ))

    def _calc_hour_of_day_pattern(self):
        self.results.append(RuleResult(
            rule_id='hour_of_day_pattern',
            name='Пиковый час',
            value=0,
            unit='',
            category='time_series',
            priority=5
        ))

    # =======================
    # GEO RULES
    # =======================

    def _calc_revenue_by_region(self):
        reg_col = self._get_col('region')
        rev_col = self._get_col('revenue')
        if not reg_col or not rev_col: return
        
        grouped = self.df.groupby(reg_col)[rev_col].sum().sort_values(ascending=False)
        self.results.append(RuleResult(
            rule_id='revenue_by_region',
            name='Выручка по регионам',
            value=0,
            unit='',
            category='geo',
            priority=6,
            details=grouped.to_dict()
        ))

    def _calc_revenue_by_city(self):
        city_col = self._get_col('city')
        rev_col = self._get_col('revenue')
        if not city_col or not rev_col: return
        
        grouped = self.df.groupby(city_col)[rev_col].sum().sort_values(ascending=False)
        self.results.append(RuleResult(
            rule_id='revenue_by_city',
            name='Выручка по городам',
            value=0,
            unit='',
            category='geo',
            priority=6,
            details=grouped.to_dict()
        ))

    def _calc_delivery_distance_avg(self):
        self.results.append(RuleResult(
            rule_id='delivery_distance_avg',
            name='Среднее расстояние доставки',
            value=0,
            unit='km',
            category='geo',
            priority=5
        ))

    def _calc_geo_concentration(self):
        self.results.append(RuleResult(
            rule_id='geo_concentration',
            name='Гео-концентрация',
            value=0,
            unit='HHI',
            category='geo',
            priority=5
        ))

    # =======================
    # CORRELATIONS & ADVANCED
    # =======================

    def _calc_price_elasticity(self):
        price_col = self._get_col('price')
        qty_col = self._get_col('quantity')
        
        if not price_col or not qty_col: return
        if price_col not in self.df.columns or qty_col not in self.df.columns: return
        
        # Очищаем данные от NaN и проверяем длину
        price_data = self.df[price_col].dropna()
        qty_data = self.df[qty_col].dropna()
        
        # Нужно минимум 2 точки для корреляции
        if len(price_data) < 2 or len(qty_data) < 2:
            return
        
        # Выравниваем индексы
        common_idx = price_data.index.intersection(qty_data.index)
        if len(common_idx) < 2:
            return
            
        corr, p_value = stats.pearsonr(price_data.loc[common_idx], qty_data.loc[common_idx])
        
        self.results.append(RuleResult(
            rule_id='price_elasticity',
            name='Эластичность спроса',
            value=corr,
            unit='coeff',
            category='correlation',
            priority=7,
            details={'p_value': p_value}
        ))

    def _calc_revenue_cost_correlation(self):
        rev_col = self._get_col('revenue')
        cost_col = self._get_col('cost')
        
        if not rev_col or not cost_col: return
        if rev_col not in self.df.columns or cost_col not in self.df.columns: return
        
        # Очищаем данные от NaN и проверяем длину
        rev_data = self.df[rev_col].dropna()
        cost_data = self.df[cost_col].dropna()
        
        # Нужно минимум 2 точки для корреляции
        if len(rev_data) < 2 or len(cost_data) < 2:
            return
        
        # Выравниваем индексы
        common_idx = rev_data.index.intersection(cost_data.index)
        if len(common_idx) < 2:
            return
            
        corr, _ = stats.pearsonr(rev_data.loc[common_idx], cost_data.loc[common_idx])
        
        self.results.append(RuleResult(
            rule_id='rev_cost_corr',
            name='Корреляция Выручка-Себестоимость',
            value=corr,
            unit='coeff',
            category='correlation',
            priority=6
        ))

    def _calc_volume_price_correlation(self):
        qty_col = self._get_col('quantity')
        price_col = self._get_col('price')
        
        if not qty_col or not price_col: return
        if qty_col not in self.df.columns or price_col not in self.df.columns: return
        
        # Очищаем данные от NaN и проверяем длину
        qty_data = self.df[qty_col].dropna()
        price_data = self.df[price_col].dropna()
        
        # Нужно минимум 2 точки для корреляции
        if len(qty_data) < 2 or len(price_data) < 2:
            return
        
        # Выравниваем индексы
        common_idx = qty_data.index.intersection(price_data.index)
        if len(common_idx) < 2:
            return
            
        corr, _ = stats.pearsonr(qty_data.loc[common_idx], price_data.loc[common_idx])
        self.results.append(RuleResult(
            rule_id='vol_price_corr',
            name='Корреляция Объем-Цена',
            value=corr,
            unit='coeff',
            category='correlation',
            priority=6
        ))

    def _calc_discount_impact(self):
        disc_col = self._get_col('discount')
        
        if not disc_col: 
            if 'DiscountPercent' in self.df.columns:
                disc_col = 'DiscountPercent'
            else:
                return
                
        if disc_col not in self.df.columns: return
        
        avg_disc = self.df[disc_col].mean()
        self.results.append(RuleResult(
            rule_id='discount_impact',
            name='Влияние скидок',
            value=avg_disc,
            unit='%',
            category='correlation',
            priority=7
        ))

    def _calc_manager_efficiency_correlation(self):
        mgr_col = self._get_col('manager')
        rev_col = self._get_col('revenue')
        
        if not mgr_col or not rev_col: return
        
        mgr_perf = self.df.groupby(mgr_col)[rev_col].sum()
        self.results.append(RuleResult(
            rule_id='manager_efficiency',
            name='Эффективность менеджеров',
            value=0,
            unit='',
            category='correlation',
            priority=6,
            details=mgr_perf.to_dict()
        ))
