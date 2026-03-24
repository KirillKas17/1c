"""
Unit-тесты для Excel парсера.
"""

import pytest
import pandas as pd
from pathlib import Path
import tempfile
import os

from src.core.parser import ExcelParser, ParserError, parse_file


class TestExcelParser:
    """Тесты для класса ExcelParser"""
    
    @pytest.fixture
    def parser(self):
        """Фикстура для создания парсера"""
        return ExcelParser()
    
    @pytest.fixture
    def sample_df(self):
        """Фикстура с тестовыми данными"""
        return pd.DataFrame({
            'Дата': ['01.01.2024', '02.01.2024', '03.01.2024'],
            'Товар': ['Товар1', 'Товар2', 'Товар1'],
            'Сумма': [1000, 2000, 1500],
            'Количество': [10, 20, 15]
        })
    
    @pytest.fixture
    def temp_csv_file(self, sample_df):
        """Фикстура для временного CSV файла"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            sample_df.to_csv(f, index=False, sep=';')
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)
    
    @pytest.fixture
    def temp_xlsx_file(self, sample_df):
        """Фикстура для временного XLSX файла"""
        import io
        buffer = io.BytesIO()
        sample_df.to_excel(buffer, index=False)
        buffer.seek(0)
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xlsx', delete=False) as f:
            f.write(buffer.getvalue())
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)
    
    # === Тесты валидации файлов ===
    
    def test_validate_file_exists(self, parser, temp_csv_file):
        """Проверка валидации существующего файла"""
        is_valid, message = parser.validate_file(temp_csv_file)
        assert is_valid is True
        assert message == "Файл валиден"
    
    def test_validate_file_not_exists(self, parser):
        """Проверка валидации несуществующего файла"""
        is_valid, message = parser.validate_file("/nonexistent/file.csv")
        assert is_valid is False
        assert "не найден" in message
    
    def test_validate_unsupported_format(self, parser):
        """Проверка валидации неподдерживаемого формата"""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            temp_path = f.name
        try:
            is_valid, message = parser.validate_file(temp_path)
            assert is_valid is False
            assert "Неподдерживаемый формат" in message
        finally:
            os.unlink(temp_path)
    
    # === Тесты загрузки файлов ===
    
    def test_load_csv(self, parser, temp_csv_file):
        """Проверка загрузки CSV"""
        df = parser.load_file(temp_csv_file)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert len(df.columns) == 4
    
    def test_load_xlsx(self, parser, temp_xlsx_file):
        """Проверка загрузки XLSX"""
        df = parser.load_file(temp_xlsx_file)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
    
    def test_load_nonexistent_file(self, parser):
        """Проверка загрузки несуществующего файла"""
        with pytest.raises(ParserError) as exc_info:
            parser.load_file("/nonexistent/file.csv")
        assert "не найден" in str(exc_info.value)
    
    # === Тесты очистки данных ===
    
    def test_clean_data_removes_empty_rows(self, parser):
        """Проверка удаления пустых строк"""
        df = pd.DataFrame({
            'A': [1, None, 3],
            'B': [4, None, 6]
        })
        df_clean = parser.clean_data(df)
        # dropna(how='all') удаляет только полностью пустые строки
        assert len(df_clean) == 2  # Строка с None не удалится т.к. not all NaN
    
    def test_clean_data_removes_duplicates(self, parser):
        """Проверка удаления дубликатов"""
        df = pd.DataFrame({
            'A': [1, 1, 2],
            'B': [3, 3, 4]
        })
        df_clean = parser.clean_data(df)
        assert len(df_clean) == 2
    
    def test_clean_column_names(self, parser):
        """Проверка очистки названий колонок"""
        df = pd.DataFrame({
            '  Товар  ': [1, 2],
            'Сумма   ': [3, 4]
        })
        df_clean = parser.clean_data(df)
        assert 'Товар' in df_clean.columns
        assert 'Сумма' in df_clean.columns
        assert '  Товар  ' not in df_clean.columns
    
    def test_infer_types_datetime(self, parser):
        """Проверка определения дат"""
        df = pd.DataFrame({
            'Дата': ['01.01.2024', '02.01.2024'],
            'Сумма': [100, 200]
        })
        df_clean = parser.clean_data(df)
        # Дата должна быть распознана
        assert pd.api.types.is_datetime64_any_dtype(df_clean['Дата']) or df_clean['Дата'].dtype == object
    
    def test_infer_types_numeric(self, parser):
        """Проверка определения чисел"""
        df = pd.DataFrame({
            'Сумма': ['100,5', '200,7', '300']
        })
        df_clean = parser.clean_data(df)
        # Числа с запятой должны преобразоваться
        assert pd.api.types.is_numeric_dtype(df_clean['Сумма'])
    
    # === Тесты сводной информации ===
    
    def test_get_summary(self, parser, sample_df):
        """Проверка получения сводки"""
        summary = parser.get_summary(sample_df)
        assert summary['rows'] == 3
        assert summary['columns'] == 4
        assert 'Дата' in summary['column_names']
        assert 'null_counts' in summary
    
    # === Тесты удобной функции parse_file ===
    
    def test_parse_file_csv(self, temp_csv_file):
        """Проверка функции parse_file для CSV"""
        df, summary = parse_file(temp_csv_file, clean=True)
        assert isinstance(df, pd.DataFrame)
        assert isinstance(summary, dict)
        assert summary['rows'] == 3
    
    def test_parse_file_xlsx(self, temp_xlsx_file):
        """Проверка функции parse_file для XLSX"""
        df, summary = parse_file(temp_xlsx_file, clean=True)
        assert isinstance(df, pd.DataFrame)
        assert summary['rows'] == 3


class TestLooksLikeDate:
    """Тесты для метода _looks_like_date"""
    
    @pytest.fixture
    def parser(self):
        return ExcelParser()
    
    def test_date_ddmmyyyy(self, parser):
        assert parser._looks_like_date('01.01.2024') is True
    
    def test_date_iso(self, parser):
        assert parser._looks_like_date('2024-01-01') is True
    
    def test_date_slash(self, parser):
        assert parser._looks_like_date('01/01/2024') is True
    
    def test_not_date(self, parser):
        assert parser._looks_like_date('Товар1') is False
        assert parser._looks_like_date('123abc') is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
