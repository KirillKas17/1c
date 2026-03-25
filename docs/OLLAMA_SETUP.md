# 🦙 Ollama Local LLM Setup Guide

## Быстрая установка для 1C Dashboard Service

### Шаг 1: Установка Ollama

#### Linux/macOS
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

#### Windows
1. Скачайте установщик с https://ollama.com/download
2. Запустите `OllamaSetup.exe`
3. Следуйте инструкциям мастера установки

### Шаг 2: Проверка установки
```bash
ollama --version
# Должно вывести: ollama version 0.x.x
```

### Шаг 3: Запуск Ollama сервера
```bash
# Сервер запускается автоматически при установке
# Для ручной проверки:
ollama serve
```

В отдельном терминале проверьте доступность:
```bash
curl http://localhost:11434/api/version
```

### Шаг 4: Скачивание модели

#### Рекомендуемая модель (баланс скорость/качество):
```bash
ollama pull llama3.2
```

#### Альтернативные модели:

| Модель | Размер | Качество | Скорость | RAM | Рекомендация |
|--------|--------|----------|----------|-----|--------------|
| `phi3:mini` | 3.8GB | Среднее | Очень быстро | 4GB | Для тестирования |
| `llama3.2` | 7GB | Хорошее | Быстро | 8GB | **Рекомендуется** |
| `llama3.1:70b` | 40GB | Отличное | Медленно | 64GB+ | Для production с GPU |
| `mistral:7b` | 4GB | Хорошее | Быстро | 8GB | Альтернатива |

### Шаг 5: Настройка переменных окружения

Создайте или обновите `.env`:
```bash
# .env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Опционально: пороги уверенности
LLM_CONFIDENCE_THRESHOLD_DICTIONARY=0.9
LLM_CONFIDENCE_THRESHOLD_HEURISTIC=0.7
LLM_CONFIDENCE_THRESHOLD_LLM=0.6
```

### Шаг 6: Тестирование

#### Прямой запрос к Ollama:
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2",
  "prompt": "Привет! Как дела?",
  "stream": false
}'
```

#### Тест через Python:
```python
import requests

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "llama3.2",
        "prompt": "Что такое 1С?",
        "stream": False
    }
)
print(response.json()["response"])
```

#### Тест через приложение:
```bash
# Запустите приложение
docker-compose up

# Загрузите тестовый файл через API
curl -X POST http://localhost:8000/api/v1/files/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test_report.xlsx"
```

---

## 🔧 Продвинутая настройка

### Использование с Docker

Если приложение работает в Docker, а Ollama на хосте:

#### macOS/Windows:
```bash
# .env
OLLAMA_HOST=http://host.docker.internal:11434
```

#### Linux:
```bash
# docker-compose.yml
services:
  app:
    extra_hosts:
      - "host.docker.internal:host-gateway"
    
# .env
OLLAMA_HOST=http://host.docker.internal:11434
```

### GPU ускорение (NVIDIA)

1. Установите NVIDIA Container Toolkit:
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

2. Обновите `docker-compose.yml`:
```yaml
services:
  ollama:
    image: ollama/ollama:latest
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    volumes:
      - ollama_data:/root/.ollama
    ports:
      - "11434:11434"
```

### Оптимизация производительности

#### Параметры модели:
```python
# В ai_detector.py или ai_analyzer.py
options = {
    "temperature": 0.1,      # Низкая для точности JSON
    "max_tokens": 500,       # Ограничьте длину ответа
    "top_p": 0.9,
    "num_predict": 200
}
```

#### Кэширование:
```bash
# Redis для кэширования LLM ответов
REDIS_URL=redis://redis:6379/0
```

---

## 🐛 Решение проблем

### Проблема: Ollama не запускается
```bash
# Проверьте логи
journalctl -u ollama -f

# Перезапустите сервис
sudo systemctl restart ollama
```

### Проблема: Модель не загружается
```bash
# Очистите кэш и скачайте заново
ollama rm llama3.2
ollama pull llama3.2
```

### Проблема: Недостаточно памяти
```bash
# Используйте меньшую модель
ollama pull phi3:mini

# Или увеличьте swap
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Проблема: Медленная генерация
- Используйте GPU (см. выше)
- Уменьшите размер модели
- Увеличьте `num_thread` в параметрах:
```bash
OLLAMA_NUM_THREAD=8
```

---

## 📊 Мониторинг

### Статус сервера:
```bash
curl http://localhost:11434/api/ps
```

### Список моделей:
```bash
ollama list
```

### Использование ресурсов:
```bash
# Linux
htop -p $(pgrep ollama)

# macOS
top -pid $(pgrep ollama)
```

---

## 💰 Сравнение затрат

### Ollama (локально):
- ✅ Бесплатно
- ✅ Приватно
- ❌ Требует ресурсы сервера

### OpenRouter (облако):
- ❌ ~$0.01-0.10 за запрос
- ❌ Данные уходят во внешнюю службу
- ✅ Не требует ресурсов
- ✅ Высокое качество

**Рекомендация:** Используйте Ollama для production, OpenRouter только как fallback.

---

## 📚 Дополнительные ресурсы

- [Официальная документация Ollama](https://ollama.com/)
- [GitHub репозиторий](https://github.com/ollama/ollama)
- [Список доступных моделей](https://ollama.com/library)
- [API документация](https://github.com/ollama/ollama/blob/main/docs/api.md)

---

**Обновлено:** 2025-01-XX  
**Версия:** 1.0
