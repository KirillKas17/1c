"""
Service: Context-Aware Analysis Service
Purpose: Orchestrate file parsing, industry detection, and dynamic rule injection.
Flow: Parse File -> Detect Industry (LLM) -> Inject Rules -> Generate Report
"""

import logging
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.industry_context import get_industry_engine, IndustryInsight
from src.api.services.file_parser_service import parse_excel_file, ParsedData
from src.api.services.business_rules_engine import BusinessRulesEngine
from src.api.services.forecasting_service import ForecastingService

logger = logging.getLogger(__name__)

class ContextAwareAnalysisService:
    """
    Main orchestrator for autonomous business analysis.
    No user configuration needed - AI determines everything.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.industry_engine = get_industry_engine()
        self.rules_engine = BusinessRulesEngine()
        self.forecast_service = ForecastingService()

    async def analyze_upload(
        self, 
        file_path: str, 
        user_id: int
    ) -> Dict[str, Any]:
        """
        Complete analysis pipeline:
        1. Parse file
        2. Detect industry via LLM
        3. Dynamically inject business rules
        4. Run analysis & forecasting
        5. Return context-aware report
        """
        
        # STEP 1: Parse File
        logger.info(f"Parsing file: {file_path}")
        parsed_data: ParsedData = await parse_excel_file(file_path)
        
        if not parsed_data or not parsed_data.columns:
            raise ValueError("Failed to parse file or file is empty")
        
        # STEP 2: Detect Industry Context (The Magic Step)
        logger.info("Detecting business context via LLM...")
        industry_insight: IndustryInsight = await self.industry_engine.analyze_structure(
            columns=parsed_data.columns,
            samples=parsed_data.sample_values,
            row_count=parsed_data.total_rows
        )
        
        logger.info(f"Industry identified: {industry_insight.industry_type} "
                    f"(Confidence: {industry_insight.confidence_score})")
        
        # STEP 3: Dynamic Rule Injection
        # Pass industry hints to the rules engine to prioritize specific checks
        logger.info("Injecting dynamic business rules...")
        custom_rules_context = {
            "industry": industry_insight.industry_type,
            "priority_metrics": industry_insight.key_metrics,
            "critical_alerts": industry_insight.critical_alerts,
            "logic_hints": industry_insight.business_logic_hints
        }
        
        # Run standard rules + context-aware adjustments
        analysis_results = await self.rules_engine.run_full_analysis(
            data=parsed_data.df,
            context=custom_rules_context
        )
        
        # STEP 4: Forecasting (Context-Aware)
        # Adjust forecast parameters based on industry volatility hints
        logger.info("Running context-aware forecasting...")
        forecast_results = await self.forecast_service.generate_forecast(
            df=parsed_data.df,
            industry_type=industry_insight.industry_type,
            horizon_months=3 # Default, could be adjusted by industry
        )
        
        # STEP 5: Assemble Final Report
        report = {
            "meta": {
                "file_name": file_path.split("/")[-1],
                "rows_processed": parsed_data.total_rows,
                "columns_detected": len(parsed_data.columns),
                "processing_timestamp": parsed_data.timestamp.isoformat()
            },
            "industry_context": {
                "type": industry_insight.industry_type,
                "confidence": industry_insight.confidence_score,
                "dashboard_focus": industry_insight.suggested_dashboard_focus,
                "key_metrics_identified": industry_insight.key_metrics
            },
            "analysis": analysis_results,
            "forecast": forecast_results,
            "alerts": {
                "critical": industry_insight.critical_alerts,
                "detected_issues": analysis_results.get("alerts", [])
            },
            "recommendations": self._generate_recommendations(
                industry_insight, 
                analysis_results
            )
        }
        
        logger.info(f"Analysis complete for {industry_insight.industry_type}. "
                    f"Found {len(report['alerts']['detected_issues'])} issues.")
        
        return report

    def _generate_recommendations(
        self, 
        insight: IndustryInsight, 
        analysis: Dict
    ) -> List[str]:
        """
        Generate plain-English recommendations based on findings.
        """
        recommendations = []
        
        # Add generic recommendation based on industry focus
        recommendations.append(
            f"Focus on tracking: {', '.join(insight.key_metrics[:3])} as they are critical for {insight.industry_type}."
        )
        
        # Add specific advice if issues found
        if analysis.get("alerts"):
            recommendations.append(
                "Immediate attention required for detected anomalies. Review the 'Alerts' section."
            )
            
        # Add forecast-based advice
        if analysis.get("forecast_summary") == "negative_trend":
            recommendations.append(
                "Forecast indicates a downward trend. Consider reviewing cost structures and sales strategies."
            )
            
        return recommendations

# Factory function
def get_analysis_service(db: AsyncSession) -> ContextAwareAnalysisService:
    return ContextAwareAnalysisService(db)
