"""
Mapping Learner - система обучения на исправлениях пользователя.

Функционал:
- Сохранение подтверждённых маппингов
- Сигнатура файла (columns hash + sample data)
- Авто-применение при повторной загрузке
- Версионирование маппингов
- Statistics: accuracy improvement over time
"""

import json
import hashlib
import sqlite3
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class MappingLearner:
    """Обучение системы на основе исправлений пользователей."""
    
    def __init__(self, db_path: str = "mappings.db"):
        """
        Инициализация базы данных маппингов.
        
        Args:
            db_path: Путь к SQLite базе данных
        """
        self.db_path = Path(db_path)
        self._init_database()
        
        # Статистика
        self.total_mappings = 0
        self.auto_applied = 0
        self.user_corrected = 0
    
    def _init_database(self):
        """Инициализация схемы БД."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица файловых сигнатур
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_signatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signature_hash TEXT UNIQUE NOT NULL,
                columns_json TEXT NOT NULL,
                sample_data_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                usage_count INTEGER DEFAULT 1
            )
        """)
        
        # Таблица маппингов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signature_id INTEGER NOT NULL,
                source_column TEXT NOT NULL,
                mapped_field TEXT NOT NULL,
                confidence_score REAL DEFAULT 1.0,
                source_type TEXT DEFAULT 'auto',  -- auto, user_confirmed, user_corrected
                version INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (signature_id) REFERENCES file_signatures(id),
                UNIQUE(signature_id, source_column, version)
            )
        """)
        
        # Таблица истории исправлений
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS correction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signature_id INTEGER NOT NULL,
                source_column TEXT NOT NULL,
                old_mapping TEXT,
                new_mapping TEXT NOT NULL,
                correction_reason TEXT,
                corrected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (signature_id) REFERENCES file_signatures(id)
            )
        """)
        
        # Индексы для ускорения поиска
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_signature_hash 
            ON file_signatures(signature_hash)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_mapping_lookup 
            ON mappings(signature_id, is_active)
        """)
        
        conn.commit()
        conn.close()
        
        logger.info(f"База данных маппингов инициализирована: {self.db_path}")
    
    def generate_signature(self, columns: List[str], sample_data: List[Dict] = None) -> str:
        """
        Генерация уникальной сигнатуры файла.
        
        Args:
            columns: Список имён колонок
            sample_data: Пример данных (первые 5 строк) для более точной сигнатуры
            
        Returns:
            MD5 хэш сигнатуры
        """
        # Сортируем колонки для консистентности
        sorted_columns = sorted(columns)
        
        # Базовая сигнатура из имён колонок
        base_data = "|".join(sorted_columns)
        
        # Добавляем sample data если есть
        if sample_data:
            sample_str = json.dumps(sample_data, sort_keys=True)
            base_data += f":::{sample_str}"
        
        signature_hash = hashlib.md5(base_data.encode()).hexdigest()
        logger.debug(f"Сигнатура сгенерирована: {signature_hash[:16]}...")
        return signature_hash
    
    def save_mapping(self, signature_hash: str, columns: List[str], 
                     mapping: Dict[str, str], source_type: str = 'user_confirmed'):
        """
        Сохранение маппинга в базу данных.
        
        Args:
            signature_hash: Хэш сигнатуры файла
            columns: Список колонок
            mapping: Словарь маппинга {source_column: mapped_field}
            source_type: Тип источника (auto, user_confirmed, user_corrected)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Проверка существования сигнатуры
            cursor.execute(
                "SELECT id FROM file_signatures WHERE signature_hash = ?",
                (signature_hash,)
            )
            result = cursor.fetchone()
            
            if result:
                signature_id = result[0]
                # Обновление счётчика использований
                cursor.execute(
                    "UPDATE file_signatures SET usage_count = usage_count + 1, updated_at = ? WHERE id = ?",
                    (datetime.now(timezone.utc), signature_id)
                )
            else:
                # Создание новой сигнатуры
                columns_json = json.dumps(columns)
                sample_data_hash = hashlib.md5(json.dumps(columns).encode()).hexdigest()
                
                cursor.execute(
                    """INSERT INTO file_signatures (signature_hash, columns_json, sample_data_hash)
                       VALUES (?, ?, ?)""",
                    (signature_hash, columns_json, sample_data_hash)
                )
                signature_id = cursor.lastrowid
            
            # Сохранение маппингов
            for source_col, mapped_field in mapping.items():
                # Проверка существующего маппинга
                cursor.execute(
                    """SELECT id, mapped_field FROM mappings 
                       WHERE signature_id = ? AND source_column = ? AND is_active = TRUE
                       ORDER BY version DESC LIMIT 1""",
                    (signature_id, source_col)
                )
                existing = cursor.fetchone()
                
                if existing:
                    existing_id, existing_field = existing
                    
                    # Если маппинг изменился - создаём новую версию
                    if existing_field != mapped_field:
                        # Деактивация старой версии
                        cursor.execute(
                            "UPDATE mappings SET is_active = FALSE WHERE id = ?",
                            (existing_id,)
                        )
                        
                        # Определение следующей версии
                        cursor.execute(
                            "SELECT MAX(version) FROM mappings WHERE signature_id = ? AND source_column = ?",
                            (signature_id, source_col)
                        )
                        max_version = cursor.fetchone()[0] or 0
                        
                        # Сохранение новой версии
                        cursor.execute(
                            """INSERT INTO mappings (signature_id, source_column, mapped_field, source_type, version)
                               VALUES (?, ?, ?, ?, ?)""",
                            (signature_id, source_col, mapped_field, source_type, max_version + 1)
                        )
                        
                        # Логирование исправления
                        cursor.execute(
                            """INSERT INTO correction_history (signature_id, source_column, old_mapping, new_mapping, correction_reason)
                               VALUES (?, ?, ?, ?, ?)""",
                            (signature_id, source_col, existing_field, mapped_field, f"User {source_type}")
                        )
                else:
                    # Первый маппинг для этой колонки
                    cursor.execute(
                        """INSERT INTO mappings (signature_id, source_column, mapped_field, source_type)
                           VALUES (?, ?, ?, ?)""",
                        (signature_id, source_col, mapped_field, source_type)
                    )
            
            conn.commit()
            self.total_mappings += 1
            
            if source_type == 'user_corrected':
                self.user_corrected += 1
            else:
                self.auto_applied += 1
            
            logger.info(f"Маппинг сохранён: {len(mapping)} полей, signature={signature_hash[:16]}...")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка сохранения маппинга: {e}")
            raise
        finally:
            conn.close()
    
    def get_mapping(self, signature_hash: str) -> Optional[Dict[str, str]]:
        """
        Получение сохранённого маппинга по сигнатуре.
        
        Args:
            signature_hash: Хэш сигнатуры файла
            
        Returns:
            Словарь маппинга или None если не найден
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Поиск сигнатуры
            cursor.execute(
                "SELECT id FROM file_signatures WHERE signature_hash = ?",
                (signature_hash,)
            )
            result = cursor.fetchone()
            
            if not result:
                logger.debug(f"Сигнатура не найдена: {signature_hash[:16]}...")
                return None
            
            signature_id = result[0]
            
            # Получение активных маппингов последней версии
            cursor.execute(
                """SELECT source_column, mapped_field FROM mappings
                   WHERE signature_id = ? AND is_active = TRUE
                   ORDER BY version DESC""",
                (signature_id,)
            )
            
            mappings = {row[0]: row[1] for row in cursor.fetchall()}
            
            if mappings:
                logger.debug(f"Маппинг найден: {len(mappings)} полей")
                # Обновление счётчика авто-применений
                cursor.execute(
                    "UPDATE file_signatures SET usage_count = usage_count + 1 WHERE id = ?",
                    (signature_id,)
                )
                conn.commit()
                self.auto_applied += 1
            
            return mappings
            
        except Exception as e:
            logger.error(f"Ошибка получения маппинга: {e}")
            return None
        finally:
            conn.close()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики обучения."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Общее количество сигнатур
            cursor.execute("SELECT COUNT(*) as cnt FROM file_signatures")
            total_signatures = cursor.fetchone()[0]
            
            # Количество уникальных маппингов
            cursor.execute("SELECT COUNT(DISTINCT signature_id || source_column) FROM mappings")
            unique_mappings = cursor.fetchone()[0]
            
            # Средняя точность (процент авто-применений)
            total = self.auto_applied + self.user_corrected
            accuracy = (self.auto_applied / total * 100) if total > 0 else 0
            
            # Топ используемых сигнатур
            cursor.execute(
                """SELECT signature_hash, usage_count FROM file_signatures 
                   ORDER BY usage_count DESC LIMIT 5"""
            )
            top_signatures = cursor.fetchall()
            
            return {
                "total_signatures": total_signatures,
                "unique_mappings": unique_mappings,
                "total_learned": self.total_mappings,
                "auto_applied": self.auto_applied,
                "user_corrected": self.user_corrected,
                "accuracy_percent": round(accuracy, 2),
                "top_signatures": [
                    {"hash": h[:16] + "...", "usage": c} 
                    for h, c in top_signatures
                ]
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}
        finally:
            conn.close()
    
    def delete_mapping(self, signature_hash: str) -> bool:
        """Удаление маппинга по сигнатуре."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Удаление маппингов
            cursor.execute(
                """DELETE FROM mappings WHERE signature_id IN (
                    SELECT id FROM file_signatures WHERE signature_hash = ?
                )""",
                (signature_hash,)
            )
            
            # Удаление сигнатуры
            cursor.execute(
                "DELETE FROM file_signatures WHERE signature_hash = ?",
                (signature_hash,)
            )
            
            deleted = cursor.rowcount
            conn.commit()
            
            logger.info(f"Удалено {deleted} записей маппинга")
            return deleted > 0
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка удаления маппинга: {e}")
            return False
        finally:
            conn.close()
    
    def export_mappings(self) -> List[Dict[str, Any]]:
        """Экспорт всех маппингов для бэкапа или анализа."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                """SELECT fs.signature_hash, fs.columns_json, m.source_column, 
                          m.mapped_field, m.source_type, m.version, m.created_at
                   FROM file_signatures fs
                   JOIN mappings m ON fs.id = m.signature_id
                   WHERE m.is_active = TRUE
                   ORDER BY fs.signature_hash, m.source_column"""
            )
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "signature_hash": row[0],
                    "columns": json.loads(row[1]),
                    "source_column": row[2],
                    "mapped_field": row[3],
                    "source_type": row[4],
                    "version": row[5],
                    "created_at": row[6]
                })
            
            logger.info(f"Экспортировано {len(results)} маппингов")
            return results
            
        except Exception as e:
            logger.error(f"Ошибка экспорта маппингов: {e}")
            return []
        finally:
            conn.close()


# Singleton instance
_learner: Optional[MappingLearner] = None


def get_mapping_learner(db_path: str = "mappings.db") -> MappingLearner:
    """Получение singleton экземпляра MappingLearner."""
    global _learner
    if _learner is None:
        _learner = MappingLearner(db_path=db_path)
    return _learner
