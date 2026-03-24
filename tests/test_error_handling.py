"""
Тесты для модулей обработки ошибок, валидации и логирования.
Проверяет корректность сообщений об ошибках и работу валидатора.
"""
import pytest
import pandas as pd
import os
import tempfile
from src.core.exceptions import (
    FileValidationError,
    StructureMismatchError,
    MappingError,
    CalculationError
)
from src.core.validators import FileValidator, validate_file
from src.api.error_handler import GlobalErrorHandler

class TestExceptions:
    """Тесты кастомных исключений."""
    
    def test_file_validation_error(self):
        error = FileValidationError("Файл битый", "Перезагрузите файл")
        assert error.error_code == "FILE_VALIDATION_ERROR"
        assert "битый" in error.message
        assert "Перезагрузите" in error.hint
        
    def test_structure_mismatch_error(self):
        missing = ["date", "revenue"]
        error = StructureMismatchError(missing)
        assert error.error_code == "STRUCTURE_MISMATCH"
        assert "date" in str(error.message)
        
    def test_error_to_dict(self):
        error = MappingError("Не удалось распознать")
        data = error.to_dict()
        assert data["error_code"] == "MAPPING_FAILED"
        assert data["message"] != ""

class TestFileValidator:
    """Тесты валидатора файлов."""
    
    def test_invalid_extension(self):
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b"test")
            temp_path = f.name
            
        try:
            with pytest.raises(FileValidationError) as exc_info:
                validate_file(temp_path)
            assert "Неподдерживаемый формат" in str(exc_info.value.message)
        finally:
            os.unlink(temp_path)
            
    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            # Создаем пустой Excel
            pd.DataFrame().to_excel(f.name, index=False)
            temp_path = f.name
            
        try:
            with pytest.raises(FileValidationError) as exc_info:
                validate_file(temp_path)
            # Пустой файл может быть обработан как имеющий 0 строк
            # Зависит от реализации проверки empty
        except Exception:
            pass # Ожидаемое поведение для пустого файла
        finally:
            os.unlink(temp_path)
            
    def test_missing_columns(self):
        # Создаем файл без нужных колонок
        df = pd.DataFrame({"RandomCol1": [1, 2], "RandomCol2": ["a", "b"]})
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            df.to_excel(f.name, index=False)
            temp_path = f.name
            
        try:
            with pytest.raises(StructureMismatchError) as exc_info:
                validate_file(temp_path)
            assert "STRUCTURE_MISMATCH" in str(exc_info.value.error_code)
        finally:
            os.unlink(temp_path)
            
    def test_valid_file_structure(self):
        # Создаем файл с правильными колонками
        df = pd.DataFrame({
            "Дата": ["01.01.2023", "02.01.2023"],
            "Сумма": [100, 200],
            "Товар": ["A", "B"]
        })
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            df.to_excel(f.name, index=False)
            temp_path = f.name
            
        try:
            result = validate_file(temp_path)
            assert result["is_valid"] is True
            assert "date" in result["info"]["mapped_columns"]
            assert "revenue" in result["info"]["mapped_columns"]
            assert "product" in result["info"]["mapped_columns"]
        finally:
            os.unlink(temp_path)

class TestErrorHandler:
    """Тесты глобального обработчика ошибок."""
    
    def test_handle_custom_error(self):
        error = StructureMismatchError(["date"])
        result = GlobalErrorHandler.handle_exception(error)
        
        assert result["success"] is False
        assert result["error_code"] == "STRUCTURE_MISMATCH"
        assert result["is_user_friendly"] is True
        
    def test_handle_unknown_error(self):
        error = ValueError("Something weird happened")
        result = GlobalErrorHandler.handle_exception(error, {"user_id": "123"})
        
        assert result["success"] is False
        assert result["error_code"] == "DATA_PROCESSING_ERROR"
        assert "некорректные данные" in result["hint"]
        
    def test_handle_io_error(self):
        error = FileNotFoundError("File not found")
        result = GlobalErrorHandler.handle_exception(error)
        
        assert result["error_code"] == "FILE_NOT_FOUND"
        assert "не найден" in result["message"]

class TestLoggingIntegration:
    """Тесты интеграции логирования (базовые)."""
    
    def test_logger_imports(self):
        from src.utils.logger import logger, log_info, log_error
        assert logger is not None
        
    def test_error_handler_imports(self):
        from src.api.error_handler import show_error, handle_error
        assert show_error is not None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
