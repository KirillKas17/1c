# AI-Enhanced Excel Parser Documentation

## 🚀 Overview

The system now uses a **Hybrid AI Approach** to understand Excel files from 1C and other ERP systems:

1. **Primary**: OpenRouter API (LLaMA-3-70B, Claude, GPT-4)
2. **Fallback**: Local Ollama (Phi-3-mini) for offline/cost-saving mode
3. **Heuristic**: Built-in rules as last resort

## 📁 New Components

### `src/ai_core/ai_analyzer.py`
Main AI analyzer with:
- Structure detection (headers, merged cells, hierarchy)
- 1C report header parsing (filters, periods, currency)
- Column type classification (finance, logistics, clients, etc.)
- VAT distinction (with_vat / without_vat)
- Weight distinction (gross / net)

### `src/ai_core/integration.py`
Integration layer that:
- Converts AI output to parser configuration
- Generates smart recommendations for users
- Auto-configures business rules based on detected structure
- Provides "Wow effect" with automatic insights

## 🔧 Configuration

### Environment Variables

```bash
# OpenRouter API (primary)
export OPENROUTER_API_KEY="your_key_here"

# Ollama local model (fallback)
export OLLAMA_HOST="http://localhost:11434"

# Pull the fallback model first:
ollama pull phi3:mini
```

### Usage Example

```python
from src.ai_core.integration import SmartParser

parser = SmartParser()
result = parser.parse_with_ai("path/to/complex_1c_report.xlsx")

print(f"Confidence: {result['confidence']*100:.1f}%")
print(f"AI Source: {result['ai_source']}")
print(f"Recommendations: {result['recommendations']}")

# Access auto-configured business rules
config = result['config']
print(f"VAT Mode: {config['filters']['vat_mode']}")
print(f"Hierarchy: {config['hierarchy_levels']}")
```

## 🎯 What AI Detects Automatically

### 1. Report Header (1C Style)
```
Валовая выручка предприятия
Период: 01.01.2024 - 31.01.2024
Показывать кроме продаж между собственными юр лицами
Данные продаж в валюте упр. учёта с НДС
Валюта: RUB
Отбор: Контрагент = Торговые сети
```
→ Extracts: period, currency, vat_mode, custom_filters

### 2. Merged Headers
```
|    Январь    |    Февраль    |
| Вес | Выручка| Вес | Выручка |
```
→ Creates: `jan_weight`, `jan_revenue`, `feb_weight`, `feb_revenue`

### 3. Hierarchy Levels
```
Отдел продаж → Город → Менеджер → Клиент
```
→ Auto-detects: department, city, manager, client roles

### 4. Column Semantics
- **Price with VAT** vs **Price without VAT** → Different business rules
- **Weight Gross** vs **Weight Net** → Validation rules
- **Manager** (physical person) vs **Client** (can be any type) → Role separation
- **INN extraction** from text → Counterparty type detection

## 🧠 Smart Recommendations

The system automatically suggests:

### Automatic Grouping
```json
{
  "suggested_views": [
    {
      "type": "hierarchical_tree",
      "levels": ["department", "city", "manager"],
      "description": "Иерархический вид: Отдел → Город → Менеджер"
    }
  ]
}
```

### Time Granularity
- **>1000 rows** → Monthly grouping
- **100-1000 rows** → Weekly grouping  
- **<100 rows** → Daily grouping

### VAT Insights
- If `vat_mode=with_vat`: Suggests net revenue calculation
- If `vat_mode=mixed`: Warns about comparison issues

### Anomaly Detection
Automatically flags columns for anomaly checking based on data patterns.

## 📊 Business Rules Auto-Configuration

### VAT Handling
```python
if vat_mode == 'with_vat':
    rule = 'extract_from_total'  # Extract VAT from total
elif vat_mode == 'without_vat':
    rule = 'calculate_on_top'    # Add VAT on top
else:
    rule = 'detect_auto'         # Try to detect per row
```

### Weight Validation
```python
if has_gross and has_net:
    rule = 'check_gross_net_ratio'  # Gross must be > Net
elif has_gross:
    rule = 'gross_only'
elif has_net:
    rule = 'net_only'
```

### Counterparty Type Detection
Based on INN and name patterns:
- **10 digits** + Company keywords → Legal Entity (ООО, АО)
- **12 digits** + Individual keywords → Individual Entrepreneur (ИП)
- **No INN** + Person name → Physical Person
- **Special markers** → Self-employed (Самозанятый)

## 🔄 Fallback Strategy

```
┌─────────────────┐
│  OpenRouter     │ ← Primary (Cloud, High Accuracy)
│  (LLaMA-3-70B)  │
└────────┬────────┘
         │ Fail/Timeout
         ▼
┌─────────────────┐
│  Ollama Local   │ ← Fallback (Offline, Fast, Free)
│  (Phi-3-mini)   │
└────────┬────────┘
         │ Fail
         ▼
┌─────────────────┐
│  Heuristics     │ ← Last Resort (Rule-based)
│  (Built-in)     │
└─────────────────┘
```

## 🧪 Testing

```python
import pytest
from src.ai_core.ai_analyzer import AIExcelAnalyzer

def test_complex_1c_report():
    analyzer = AIExcelAnalyzer()
    result = analyzer.analyze_file("tests/data/complex_1c_vat_report.xlsx")
    
    assert result['status'] == 'success'
    assert result['confidence_score'] > 0.7
    assert 'hierarchy_levels' in result
    assert result['filters_detected']['vat_mode'] in ['with_vat', 'without_vat', 'mixed']
```

## 🎁 "Wow Effect" Features

1. **Zero Configuration**: User just uploads file → everything works
2. **Smart Defaults**: Period, grouping, metrics chosen automatically
3. **Contextual Insights**: "Data contains VAT. Click here to see net values."
4. **Adaptive UI**: Shows/hides filters based on detected structure
5. **Proactive Alerts**: "Anomaly detected in weight column. Review?"

## 📝 Next Steps

1. Set up OpenRouter API key
2. Install Ollama + Phi-3-mini for fallback
3. Test with real 1C exports
4. Fine-tune prompts based on edge cases
5. Add caching for repeated file structures

## 🔗 Related Files

- `src/core_parser/hierarchy_parser.py` - Hierarchy processing
- `src/core_parser/config.yaml` - Column synonyms (500+)
- `src/analytics/business_rules.py` - Business logic
- `docs/ADVANCED_EXCEL_PROCESSING.md` - Detailed processing guide
