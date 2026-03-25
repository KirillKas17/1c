"""
Module: Industry Context Engine
Purpose: Automatically detect business type and key metrics from uploaded data using LLM.
Approach: Extract headers + sample data -> Ask LLM to classify -> Inject context into analysis.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

# Import from existing ai_analyzer module
import sys
sys.path.append('/workspace/src')
from ai_core.ai_analyzer import AIExcelAnalyzer

logger = logging.getLogger(__name__)

class IndustryInsight(BaseModel):
    """Structure for LLM response regarding business context"""
    industry_type: str = Field(..., description="e.g., 'Auto Service', 'Woodworking', 'Retail', 'SaaS'")
    confidence_score: float = Field(..., description="0.0 to 1.0, how sure the model is")
    key_metrics: List[str] = Field(..., description="List of 5-7 most important KPIs for this specific business")
    critical_alerts: List[str] = Field(..., description="What negative trends to watch for in this industry")
    business_logic_hints: List[str] = Field(..., description="Specific logic rules, e.g., 'High return rate is critical for retail'")
    suggested_dashboard_focus: str = Field(..., description="One sentence summary of what the dashboard should highlight")

class IndustryContextEngine:
    """
    Autonomous engine to detect business context without user input.
    Uses LLM to analyze column headers and sample data.
    """
    
    def __init__(self):
        self.llm_client = AIExcelAnalyzer()  # Use existing analyzer
        self.system_prompt = """
You are an expert Business Analyst and Data Scientist. 
Your task is to analyze the structure of a dataset (column names and sample values) and determine:
1. The specific industry/business type.
2. The 5-7 most critical KPIs for this business owner.
3. Specific risks or alerts relevant to this industry.
4. How to interpret the data correctly (business logic hints).

Respond strictly in JSON format matching the schema provided.
Do not invent data, infer only from column names and samples.
If the industry is unclear, choose the most likely one based on common patterns.
"""

    async def analyze_structure(
        self, 
        columns: List[str], 
        samples: Dict[str, List[Any]], 
        row_count: int
    ) -> IndustryInsight:
        """
        Analyze file structure to determine business context.
        
        Args:
            columns: List of column headers
            samples: Dict of {column_name: [sample_value_1, sample_value_2]}
            row_count: Total rows in file
            
        Returns:
            IndustryInsight object with classification and metrics
        """
        
        # 1. Prepare compact context for LLM (optimize token usage)
        # Note: AIExcelAnalyzer handles this internally

        try:
            # 2. Call LLM using AIExcelAnalyzer methods
            # Prepare context text for the analyzer
            context_text = f"""Dataset Structure:
Columns: {', '.join(columns)}
Total Rows: {row_count}

Sample Data (first 3 values per column):
{json.dumps({k: v[:3] for k, v in samples.items()}, indent=2, ensure_ascii=False)}
"""
            
            # Try OpenRouter first, then fallback to Ollama
            response_data = self.llm_client.analyze_with_openrouter(context_text)
            
            if response_data is None:
                logger.warning("OpenRouter failed, trying Ollama fallback...")
                response_data = self.llm_client.analyze_with_ollama(context_text)
            
            if response_data is None:
                raise Exception("Both LLM providers failed")
            
            response_text = json.dumps(response_data)
            
            # 3. Parse and Validate
            if isinstance(response_text, str):
                # Clean markdown code blocks if present
                response_text = response_text.replace("```json", "").replace("```", "").strip()
                data = json.loads(response_text)
            else:
                data = response_text
                
            insight = IndustryInsight(**data)
            
            logger.info(f"Industry detected: {insight.industry_type} (Confidence: {insight.confidence_score})")
            return insight
            
        except Exception as e:
            logger.error(f"Failed to detect industry context: {e}")
            # Fallback to generic analysis if LLM fails
            return self._get_fallback_insight(columns)

    def _get_fallback_insight(self, columns: List[str]) -> IndustryInsight:
        """Generic fallback if LLM is unavailable"""
        return IndustryInsight(
            industry_type="General Business",
            confidence_score=0.5,
            key_metrics=["Revenue", "Profit Margin", "Total Transactions"],
            critical_alerts=["Negative Growth", "Data Inconsistencies"],
            business_logic_hints=["Analyze trends over time"],
            suggested_dashboard_focus="General financial performance overview."
        )

# Singleton instance
_engine_instance: Optional[IndustryContextEngine] = None

def get_industry_engine() -> IndustryContextEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = IndustryContextEngine()
    return _engine_instance
