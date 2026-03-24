"""
Базовый парсер Excel/CSV файлов для 1C Dashboard Service.
Поддерживает загрузку, валидацию и очистку данных из выгрузок 1С.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import logging

logger = logging.getLogger(__name__)


class ParserError(Exception):
    """Исключение для ошибок парсера"""
    pass


class ExcelParser:
    """
    Парсер Excel/CSV файлов с поддержкой различных форматов 1С.
    
    Attributes:
        supported_formats: Поддерживаемые расширения файлов
        max_file_size_mb: Максимальный размер файла в МБ
    """
    
    SUPPORTED_FORMATS = {'.xlsx', '.xls', '.csv'}
    MAX_FILE_SIZE_MB = 100
    
    def __init__(self, max_rows: Optional[int] = None):
        """
        Инициализация парсера.
        
        Args:
            max_rows: Максимальное количество строк для загрузки (None = без ограничений)
        """
        self.max_rows = max_rows
        
    def validate_file(self, file_path: Union[str, Path]) -> Tuple[bool, str]:
        """
        Валидация файла перед загрузкой.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Tuple[bool, str]: (успешно, сообщение)
        """
        file_path = Path(file_path)
        
        # Проверка существования
        if not file_path.exists():
            return False, f"Файл не найден: {file_path}"
        
        # Проверка расширения
        if file_path.suffix.lower() not in self.SUPPORTED_FORMATS:
            return False, f"Неподдерживаемый формат: {file_path.suffix}. Допустимы: {self.SUPPORTED_FORMATS}"
        
        # Проверка размера
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.MAX_FILE_SIZE_MB:
            return False, f"Файл слишком большой: {file_size_mb:.2f} MB (максимум {self.MAX_FILE_SIZE_MB} MB)"
        
        return True, "Файл валиден"
    
    def load_file(self, file_path: Union[str, Path], sheet_name: Optional[Union[int, str]] = 0) -> pd.DataFrame:
        """
        Загрузка файла в DataFrame.
        
        Args:
            file_path: Путь к файлу
            sheet_name: Имя или номер листа (для Excel)
            
        Returns:
            pd.DataFrame: Загруженные данные
            
        Raises:
            ParserError: Ошибка при загрузке
        """
        file_path = Path(file_path)
        
        # Валидация
        is_valid, message = self.validate_file(file_path)
        if not is_valid:
            raise ParserError(message)
        
        try:
            suffix = file_path.suffix.lower()
            
            if suffix == '.csv':
                # Пробуем разные кодировки и разделители
                df = self._load_csv(file_path)
            elif suffix in {'.xlsx', '.xls'}:
                df = pd.read_excel(
                    file_path,
                    sheet_name=sheet_name,
                    nrows=self.max_rows,
                    engine='openpyxl' if suffix == '.xlsx' else 'xlrd'
                )
            else:
                raise ParserError(f"Неподдерживаемый формат: {suffix}")
            
            logger.info(f"Загружен файл: {file_path.name}, строк: {len(df)}, колонок: {len(df.columns)}")
            return df
            
        except Exception as e:
            raise ParserError(f"Ошибка загрузки файла: {str(e)}")
    
    def _load_csv(self, file_path: Path) -> pd.DataFrame:
        """
        Загрузка CSV с авто-определением кодировки и разделителя.
        
        Args:
            file_path: Путь к CSV файлу
            
        Returns:
            pd.DataFrame: Загруженные данные
        """
        encodings = ['utf-8', 'cp1251', 'latin1', 'iso-8859-1']
        delimiters = [',', ';', '\t', '|']
        
        for encoding in encodings:
            for delimiter in delimiters:
                try:
                    df = pd.read_csv(
                        file_path,
                        encoding=encoding,
                        sep=delimiter,
                        nrows=self.max_rows,
                        on_bad_lines='skip'
                    )
                    if len(df.columns) > 1:  # Успешная загрузка
                        logger.debug(f"CSV загружен: encoding={encoding}, delimiter='{delimiter}'")
                        return df
                except Exception:
                    continue
        
        raise ParserError("Не удалось определить кодировку или разделитель CSV")
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Очистка данных от типовых проблем.
        
        Args:
            df: Исходный DataFrame
            
        Returns:
            pd.DataFrame: Очищенный DataFrame
        """
        df_clean = df.copy()
        
        # Удаление полностью пустых строк
        initial_rows = len(df_clean)
        df_clean = df_clean.dropna(how='all')
        removed_rows = initial_rows - len(df_clean)
        if removed_rows > 0:
            logger.info(f"Удалено пустых строк: {removed_rows}")
        
        # Удаление дубликатов
        initial_rows = len(df_clean)
        df_clean = df_clean.drop_duplicates()
        removed_dups = initial_rows - len(df_clean)
        if removed_dups > 0:
            logger.info(f"Удалено дубликатов: {removed_dups}")
        
        # Очистка названий колонок
        df_clean.columns = self._clean_column_names(df_clean.columns)
        
        # Преобразование типов данных
        df_clean = self._infer_types(df_clean)
        
        return df_clean
    
    def _clean_column_names(self, columns: pd.Index) -> pd.Index:
        """
        Очистка названий колонок.
        
        Args:
            columns: Индекс колонок
            
        Returns:
            pd.Index: Очищенные названия
        """
        cleaned = []
        for col in columns:
            if isinstance(col, str):
                # Удаление лишних пробелов, замена спецсимволов
                col = col.strip()
                col = ' '.join(col.split())  # Нормализация пробелов
            cleaned.append(col if col else f"column_{len(cleaned)}")
        
        return pd.Index(cleaned)
    
    def _infer_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Автоматическое определение и преобразование типов данных.
        
        Args:
            df: DataFrame
            
        Returns:
            pd.DataFrame: DataFrame с корректными типами
        """
        for col in df.columns:
            series = df[col]
            
            # Пропускаем если уже числовой
            if pd.api.types.is_numeric_dtype(series):
                continue
            
            # Попытка преобразования в datetime
            if series.dtype == object:
                try:
                    # Проверка на похожие на даты значения
                    sample = series.dropna().head(10)
                    if len(sample) > 0 and any(self._looks_like_date(str(v)) for v in sample):
                        df[col] = pd.to_datetime(series, errors='ignore', dayfirst=True)
                        continue
                except Exception:
                    pass
            
            # Попытка преобразования в числа
            if series.dtype == object:
                try:
                    # Удаляем пробелы и заменяем запятые на точки
                    numeric_series = series.astype(str).str.replace(' ', '').str.replace(',', '.')
                    df[col] = pd.to_numeric(numeric_series, errors='ignore')
                except Exception:
                    pass
        
        return df
    
    def _looks_like_date(self, value: str) -> bool:
        """
        Проверка, похоже ли значение на дату.
        
        Args:
            value: Строковое значение
            
        Returns:
            bool: True если похоже на дату
        """
        import re
        date_patterns = [
            r'\d{1,2}\.\d{1,2}\.\d{2,4}',  # 01.01.2024
            r'\d{4}-\d{2}-\d{2}',           # 2024-01-01
            r'\d{1,2}/\d{1,2}/\d{2,4}',     # 01/01/2024
        ]
        return any(re.match(pattern, str(value)) for pattern in date_patterns)
    
    def get_summary(self, df: pd.DataFrame) -> Dict:
        """
        Получение сводной информации о данных.
        
        Args:
            df: DataFrame
            
        Returns:
            Dict: Сводная информация
        """
        return {
            'rows': len(df),
            'columns': len(df.columns),
            'column_names': list(df.columns),
            'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
            'null_counts': df.isnull().sum().to_dict(),
            'memory_usage_mb': df.memory_usage(deep=True).sum() / (1024 * 1024)
        }


def parse_file(file_path: Union[str, Path], clean: bool = True) -> Tuple[pd.DataFrame, Dict]:
    """
    Удобная функция для загрузки и очистки файла.
    
    Args:
        file_path: Путь к файлу
        clean:是否需要 очистка данных
        
    Returns:
        Tuple[pd.DataFrame, Dict]: (DataFrame, сводная информация)
    """
    parser = ExcelParser()
    df = parser.load_file(file_path)
    
    if clean:
        df = parser.clean_data(df)
    
    summary = parser.get_summary(df)
    return df, summary
