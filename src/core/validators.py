"""
Валидатор структуры файлов выгрузки из 1С.
Проверяет формат, размер, наличие обязательных колонок и типов данных.
"""
import pandas as pd
import os
from typing import List, Dict, Any, Optional
from src.core.exceptions import FileValidationError, StructureMismatchError

# Константы валидации
MAX_FILE_SIZE_MB = 100
ALLOWED_EXTENSIONS = ['.xlsx', '.xls', '.csv']

# Минимальный набор колонок-кандидатов (хотя бы одна из группы должна быть найдена)
REQUIRED_COLUMN_GROUPS = {
    "date": ["Дата", "ДатаДокумента", "Период", "ДатаС", "Date"],
    "revenue": ["Сумма", "Выручка", "СуммаПродажи", "Оборот", "СуммаДокумента", "Amount"],
    "product": ["Товар", "Номенклатура", "Продукция", "Артикул", "Product", "Item"]
}

class FileValidator:
    """Класс для валидации загруженных файлов."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        self.extension = os.path.splitext(file_path)[1].lower()
        self.df: Optional[pd.DataFrame] = None
        
    def validate_all(self) -> Dict[str, Any]:
        """Запускает полную валидацию файла."""
        result = {
            "is_valid": False,
            "errors": [],
            "warnings": [],
            "info": {}
        }
        
        # 1. Проверка расширения
        if self.extension not in ALLOWED_EXTENSIONS:
            raise FileValidationError(
                message=f"Неподдерживаемый формат файла: {self.extension}",
                hint=f"Разрешенные форматы: {', '.join(ALLOWED_EXTENSIONS)}"
            )
            
        # 2. Проверка размера
        if self.file_size_mb > MAX_FILE_SIZE_MB:
            raise FileValidationError(
                message=f"Файл слишком большой ({self.file_size_mb:.2f} MB)",
                hint=f"Максимальный размер файла: {MAX_FILE_SIZE_MB} MB"
            )
            
        # 3. Попытка загрузки и проверка содержимого
        try:
            self.df = self._load_file()
        except Exception as e:
            raise FileValidationError(
                message=f"Не удалось прочитать файл: {str(e)}",
                hint="Проверьте, не поврежден ли файл и не защищен ли он паролем."
            )
            
        if self.df.empty:
            raise FileValidationError(
                message="Файл пуст или не содержит данных",
                hint="Убедитесь, что в файле есть строки данных."
            )
            
        result["info"]["rows_count"] = len(self.df)
        result["info"]["columns_count"] = len(self.df.columns)
        result["info"]["columns"] = list(self.df.columns)
        
        # 4. Проверка наличия обязательных колонок
        found_columns = self._find_required_columns()
        
        missing_groups = []
        for group_name, candidates in REQUIRED_COLUMN_GROUPS.items():
            if group_name not in found_columns:
                missing_groups.append(group_name)
                
        if missing_groups:
            missing_details = []
            for group in missing_groups:
                missing_details.append(f"{group} (ожидалось: {', '.join(REQUIRED_COLUMN_GROUPS[group][:3])}...)")
            raise StructureMismatchError(
                missing_columns=missing_details,
                hint="Используйте стандартные отчеты 1С: 'Валовая прибыль', 'Продажи', 'Реализация'."
            )
            
        # 5. Проверка типов данных в найденных колонках
        type_errors = self._validate_data_types(found_columns)
        if type_errors:
            result["warnings"].extend(type_errors)
            
        result["is_valid"] = True
        result["info"]["mapped_columns"] = found_columns
        
        return result
    
    def _load_file(self) -> pd.DataFrame:
        """Загружает файл в зависимости от расширения."""
        if self.extension == '.csv':
            # Пробуем разные кодировки для CSV
            encodings = ['utf-8', 'cp1251', 'latin1']
            for enc in encodings:
                try:
                    return pd.read_csv(self.file_path, encoding=enc, nrows=1000) # Читаем первые 1000 строк для валидации
                except UnicodeDecodeError:
                    continue
            raise ValueError("Не удалось определить кодировку CSV файла")
        else:
            return pd.read_excel(self.file_path, nrows=1000)
            
    def _find_required_columns(self) -> Dict[str, str]:
        """Ищет колонки, соответствующие требуемым группам."""
        found = {}
        df_columns_upper = [str(c).upper().strip() for c in self.df.columns]
        df_columns_orig = list(self.df.columns)
        
        for group_name, candidates in REQUIRED_COLUMN_GROUPS.items():
            for candidate in candidates:
                candidate_upper = candidate.upper()
                for i, col_upper in enumerate(df_columns_upper):
                    if candidate_upper in col_upper or col_upper in candidate_upper:
                        found[group_name] = df_columns_orig[i]
                        break
                if group_name in found:
                    break
                    
        return found
    
    def _validate_data_types(self, found_columns: Dict[str, str]) -> List[str]:
        """Проверяет типы данных в ключевых колонках."""
        warnings = []
        
        if "revenue" in found_columns:
            col = found_columns["revenue"]
            # Пытаемся привести к числу
            try:
                pd.to_numeric(self.df[col], errors='raise')
            except (ValueError, TypeError):
                warnings.append(f"Колонка '{col}' должна содержать числа, но найдены другие значения.")
                
        if "date" in found_columns:
            col = found_columns["date"]
            # Пытаемся привести к дате
            try:
                pd.to_datetime(self.df[col], errors='raise', dayfirst=True)
            except (ValueError, TypeError):
                warnings.append(f"Колонка '{col}' должна содержать даты, но формат не распознан.")
                
        return warnings

def validate_file(file_path: str) -> Dict[str, Any]:
    """Удобная функция для валидации файла."""
    validator = FileValidator(file_path)
    return validator.validate_all()
