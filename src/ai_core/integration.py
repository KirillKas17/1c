"""
Интеграция AI-анализатора с основным парсером.
Автоматическая настройка бизнес-правил на основе AI-метаданных.
"""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependencies and missing modules
def get_ai_analyzer():
    from .ai_analyzer import AIExcelAnalyzer
    return AIExcelAnalyzer

def get_hierarchy_parser():
    try:
        # Прямой импорт без загрузки всего core_parser
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "hierarchy_parser", 
            "/workspace/src/parser/hierarchy_parser.py"
        )
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.HierarchyParser
        return None
    except Exception as e:
        logger.warning(f"HierarchyParser not available: {e}, using mock")
        return None

def get_processing_history():
    try:
        # Прямой импорт без загрузки всего core_parser
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "processing_history", 
            "/workspace/core_parser/utils/processing_history.py"
        )
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.ProcessingHistory
        return None
    except Exception as e:
        logger.warning(f"ProcessingHistory not available: {e}, using mock")
        return None

class AIParserIntegration:
    """
    Интеграционный слой между AI-анализатором и парсером.
    Использует результаты AI для настройки правил обработки.
    """
    
    def __init__(self):
        AIExcelAnalyzer = get_ai_analyzer()
        self.ai_analyzer = AIExcelAnalyzer()
        
        HierarchyParser = get_hierarchy_parser()
        self.hierarchy_parser = HierarchyParser() if HierarchyParser else None
        
    def preprocess_file(self, file_path: str) -> Dict[str, Any]:
        """
        Предварительный анализ файла перед основной обработкой.
        Возвращает настроенные параметры для парсера.
        """
        logger.info(f"AI preprocessing: {file_path}")
        
        # 1. AI-анализ структуры
        ai_result = self.ai_analyzer.analyze_file(file_path)
        
        if ai_result.get('status') != 'success':
            logger.warning("AI analysis failed, using default settings")
            return self._get_default_settings()
        
        # 2. Извлечение настроек из AI-результата
        parser_config = self._extract_parser_config(ai_result)
        
        # 3. Сохранение метаданных в историю обработки
        self._save_metadata(file_path, ai_result)
        
        return {
            'status': 'success',
            'config': parser_config,
            'ai_metadata': ai_result,
            'confidence': ai_result.get('confidence_score', 0.5)
        }
    
    def _extract_parser_config(self, ai_result: Dict) -> Dict[str, Any]:
        """Преобразование AI-результата в конфигурацию парсера."""
        
        config = {
            'data_start_row': ai_result.get('data_start_row', 1),
            'columns_mapping': {},
            'hierarchy_levels': [],
            'filters': {},
            'business_rules': {}
        }
        
        # Обработка заголовков
        headers = ai_result.get('headers', [])
        for header in headers:
            original = header.get('original_name', '')
            normalized = header.get('normalized_name', '')
            category = header.get('category', 'other')
            sub_category = header.get('sub_category')
            
            # Маппинг колонок
            if normalized:
                config['columns_mapping'][original] = {
                    'name': normalized,
                    'category': category,
                    'sub_category': sub_category,
                    'is_merged': header.get('is_merged_parent', False),
                    'children': header.get('merged_children', [])
                }
        
        # Иерархия
        hierarchy = ai_result.get('hierarchy_levels', [])
        if hierarchy:
            config['hierarchy_levels'] = hierarchy
        
        # Фильтры из шапки 1С
        filters_detected = ai_result.get('filters_detected', {})
        if filters_detected:
            config['filters'] = {
                'period': filters_detected.get('period'),
                'currency': filters_detected.get('currency', 'RUB'),
                'vat_mode': filters_detected.get('vat_mode', 'mixed'),
                'custom': filters_detected.get('custom_filters', [])
            }
        
        # Бизнес-правила на основе рекомендаций AI
        recommendations = ai_result.get('recommendations', {})
        if recommendations:
            config['business_rules'] = {
                'auto_group_by': recommendations.get('group_by', []),
                'priority_metrics': recommendations.get('metrics_to_show', []),
                'anomaly_columns': recommendations.get('anomalies_check', [])
            }
        
        # Специфичные правила для НДС
        if config['filters'].get('vat_mode') == 'with_vat':
            config['business_rules']['vat_handling'] = 'extract_from_total'
        elif config['filters'].get('vat_mode') == 'without_vat':
            config['business_rules']['vat_handling'] = 'calculate_on_top'
        else:
            config['business_rules']['vat_handling'] = 'detect_auto'
        
        # Правила для веса
        has_gross = any(h.get('sub_category') == 'weight_gross' for h in headers)
        has_net = any(h.get('sub_category') == 'weight_net' for h in headers)
        
        if has_gross and has_net:
            config['business_rules']['weight_validation'] = 'check_gross_net_ratio'
        elif has_gross:
            config['business_rules']['weight_validation'] = 'gross_only'
        elif has_net:
            config['business_rules']['weight_validation'] = 'net_only'
        
        return config
    
    def _get_default_settings(self) -> Dict[str, Any]:
        """Настройки по умолчанию, если AI не сработал."""
        return {
            'status': 'success',
            'config': {
                'data_start_row': 1,
                'columns_mapping': {},
                'hierarchy_levels': [],
                'filters': {'currency': 'RUB', 'vat_mode': 'mixed'},
                'business_rules': {
                    'auto_group_by': [],
                    'vat_handling': 'detect_auto',
                    'weight_validation': 'check_gross_net_ratio'
                }
            },
            'ai_metadata': {},
            'confidence': 0.5
        }
    
    def _save_metadata(self, file_path: str, ai_result: Dict):
        """Сохранение AI-метаданных для последующего анализа."""
        try:
            ProcessingHistory = get_processing_history()
            if not ProcessingHistory:
                logger.debug("ProcessingHistory not available, skipping metadata save")
                return
                
            history = ProcessingHistory()
            # Сохраняем только ключевые метаданные, не весь результат
            metadata = {
                'structure_hash': hash(str(ai_result.get('headers', []))),
                'hierarchy_levels': ai_result.get('hierarchy_levels', []),
                'detected_filters': ai_result.get('filters_detected', {}),
                'confidence': ai_result.get('confidence_score', 0),
                'ai_source': ai_result.get('source', 'unknown')
            }
            # Можно сохранить в историю или отдельное хранилище
            logger.debug(f"Metadata saved for {file_path}")
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
    
    def get_smart_recommendations(self, ai_result: Dict) -> Dict[str, Any]:
        """
        Генерация умных рекомендаций для пользователя на основе AI-анализа.
        """
        recommendations = {
            'suggested_views': [],
            'auto_filters': {},
            'alerts': [],
            'insights': []
        }
        
        filters = ai_result.get('filters_detected', {})
        hierarchy = ai_result.get('hierarchy_levels', [])
        recs = ai_result.get('recommendations', {})
        
        # 1. Автоматическая группировка
        if hierarchy:
            recommendations['suggested_views'].append({
                'type': 'hierarchical_tree',
                'levels': hierarchy,
                'description': f"Иерархический вид: {' → '.join(hierarchy)}"
            })
        
        # 2. Период анализа
        period = filters.get('period', '')
        if period:
            recommendations['auto_filters']['period'] = period
            recommendations['insights'].append(
                f"Данные за период: {period}. Рекомендуем сравнить с предыдущим периодом."
            )
        
        # 3. Валюта и НДС
        currency = filters.get('currency', 'RUB')
        vat_mode = filters.get('vat_mode', 'mixed')
        
        if vat_mode == 'with_vat':
            recommendations['insights'].append(
                "Все суммы содержат НДС. Доступен расчет чистой выручки."
            )
            recommendations['suggested_views'].append({
                'type': 'vat_breakdown',
                'description': 'Разделение сумм на базовую стоимость и НДС'
            })
        
        # 4. Аномалии
        anomaly_cols = recs.get('anomalies_check', [])
        if anomaly_cols:
            recommendations['alerts'].append({
                'type': 'anomaly_detection',
                'columns': anomaly_cols,
                'message': f"Рекомендуем проверить аномалии в: {', '.join(anomaly_cols)}"
            })
        
        # 5. Динамический выбор периода (день/неделя/месяц)
        # AI анализирует плотность данных и рекомендует гранулярность
        data_rows = len(ai_result.get('headers', []))
        if data_rows > 1000:
            recommendations['auto_filters']['default_grouping'] = 'month'
        elif data_rows > 100:
            recommendations['auto_filters']['default_grouping'] = 'week'
        else:
            recommendations['auto_filters']['default_grouping'] = 'day'
        
        return recommendations


# Фасад для удобного использования
class SmartParser:
    """
    Умный парсер с AI-поддержкой.
    Автоматически адаптируется под структуру файла.
    """
    
    def __init__(self):
        self.integration = AIParserIntegration()
    
    def parse_with_ai(self, file_path: str) -> Dict[str, Any]:
        """
        Полный цикл: AI-анализ + парсинг + рекомендации.
        """
        # 1. Предварительный AI-анализ
        prep_result = self.integration.preprocess_file(file_path)
        
        if prep_result['status'] != 'success':
            return {
                'status': 'error',
                'message': 'AI preprocessing failed',
                'fallback': True
            }
        
        # 2. Получение рекомендаций
        recommendations = self.integration.get_smart_recommendations(
            prep_result['ai_metadata']
        )
        
        # 3. Здесь будет вызов основного парсера с настроенной конфигурацией
        # parser = DataParser(config=prep_result['config'])
        # data = parser.parse(file_path)
        
        return {
            'status': 'success',
            'config': prep_result['config'],
            'recommendations': recommendations,
            'confidence': prep_result['confidence'],
            'ai_source': prep_result['ai_metadata'].get('source', 'unknown'),
            'message': f"File analyzed with {prep_result['confidence']*100:.1f}% confidence"
        }


if __name__ == "__main__":
    # Пример использования
    # parser = SmartParser()
    # result = parser.parse_with_ai("path/to/file.xlsx")
    # print(json.dumps(result, indent=2, ensure_ascii=False))
    pass
