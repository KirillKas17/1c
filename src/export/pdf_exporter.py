"""
PDF Export Module for Dashboard Reports.
Generates professional PDF reports with charts, tables, and analytics.
"""
import os
import io
from datetime import datetime
from typing import Dict, List, Any, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
import pandas as pd
from PIL import Image as PILImage
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class PDFExporter:
    """Export dashboard data to professional PDF format."""
    
    def __init__(self, output_path: Optional[str] = None):
        self.output_path = output_path
        self.styles = getSampleStyleSheet()
        self._setup_styles()
        
    def _setup_styles(self):
        """Configure custom styles for the report."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1E88E5'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='Subtitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#666666'),
            spaceAfter=12,
            alignment=TA_CENTER
        ))
        
        # KPI style
        self.styles.add(ParagraphStyle(
            name='KPI',
            parent=self.styles['Normal'],
            fontSize=18,
            textColor=colors.HexColor('#2E7D32'),
            fontName='Helvetica-Bold'
        ))
        
        # Normal text
        self.styles.add(ParagraphStyle(
            name='NormalText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#333333'),
            spaceAfter=6
        ))
    
    def _create_chart(self, data: Dict[str, Any], chart_type: str = 'line') -> BytesIO:
        """Create a matplotlib chart and return as BytesIO."""
        buf = BytesIO()
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        if chart_type == 'line':
            x_data = data.get('x', [])
            y_data = data.get('y', [])
            ax.plot(x_data, y_data, marker='o', linewidth=2, color='#1E88E5')
            ax.fill_between(x_data, y_data, alpha=0.3, color='#1E88E5')
            
        elif chart_type == 'bar':
            categories = data.get('categories', [])
            values = data.get('values', [])
            bars = ax.bar(categories, values, color=['#1E88E5', '#43A047', '#FB8C00', '#E53935'])
            
        elif chart_type == 'pie':
            labels = data.get('labels', [])
            sizes = data.get('sizes', [])
            colors_list = ['#1E88E5', '#43A047', '#FB8C00', '#E53935', '#8E24AA']
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors_list[:len(labels)])
        
        ax.set_title(data.get('title', ''), fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        buf.seek(0)
        return buf
    
    def _create_kpi_table(self, metrics: Dict[str, Any]) -> Table:
        """Create a KPI summary table."""
        kpi_data = [['Метрика', 'Значение', 'Изменение']]
        
        for key, value in metrics.items():
            if isinstance(value, dict):
                val = value.get('value', 'N/A')
                change = value.get('change', '0%')
                change_str = f"{change}" if change.startswith('+') or change.startswith('-') else f"+{change}"
                kpi_data.append([key, str(val), change_str])
        
        table = Table(kpi_data, colWidths=[2.5*inch, 2*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E88E5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F5F5')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        return table
    
    def _create_data_table(self, df: pd.DataFrame, title: str = '') -> List:
        """Create a data table from DataFrame."""
        elements = []
        
        if title:
            elements.append(Paragraph(title, self.styles['Heading2']))
            elements.append(Spacer(1, 12))
        
        # Limit rows for PDF
        max_rows = 50
        if len(df) > max_rows:
            df = df.head(max_rows)
        
        # Convert to list
        data = [df.columns.tolist()] + df.values.tolist()
        
        # Create table
        table = Table(data, colWidths=[1.2*inch] * min(len(df.columns), 6))
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E88E5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#FAFAFA')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        
        elements.append(table)
        
        if len(df) >= max_rows:
            elements.append(Spacer(1, 12))
            elements.append(Paragraph(
                f"<i>Показано первые {max_rows} строк из {len(df)}</i>",
                self.styles['NormalText']
            ))
        
        return elements
    
    def export_dashboard(
        self,
        metrics: Dict[str, Any],
        charts: List[Dict[str, Any]],
        dataframes: Dict[str, pd.DataFrame],
        title: str = "Аналитический отчет",
        subtitle: str = "",
        output_path: Optional[str] = None
    ) -> str:
        """
        Export complete dashboard to PDF.
        
        Args:
            metrics: Dictionary of KPI metrics
            charts: List of chart configurations
            dataframes: Dictionary of DataFrames to include
            title: Report title
            subtitle: Report subtitle
            output_path: Output file path
            
        Returns:
            Path to generated PDF
        """
        output = output_path or self.output_path or f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        doc = SimpleDocTemplate(
            output,
            pagesize=landscape(A4),
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        elements = []
        
        # Title
        elements.append(Paragraph(title, self.styles['CustomTitle']))
        
        # Subtitle
        if subtitle:
            elements.append(Paragraph(subtitle, self.styles['Subtitle']))
        
        elements.append(Spacer(1, 20))
        
        # Generation date
        elements.append(Paragraph(
            f"Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            self.styles['NormalText']
        ))
        elements.append(Spacer(1, 20))
        
        # KPI Section
        elements.append(Paragraph("Ключевые показатели", self.styles['Heading2']))
        elements.append(Spacer(1, 12))
        elements.append(self._create_kpi_table(metrics))
        elements.append(Spacer(1, 20))
        
        # Charts Section
        if charts:
            elements.append(Paragraph("Графики и диаграммы", self.styles['Heading2']))
            elements.append(Spacer(1, 12))
            
            for chart_config in charts:
                try:
                    chart_buf = self._create_chart(chart_config, chart_config.get('type', 'line'))
                    chart_img = Image(chart_buf, width=6*inch, height=4*inch)
                    elements.append(KeepTogether(chart_img))
                    elements.append(Spacer(1, 12))
                except Exception as e:
                    logger.error(f"Error creating chart: {e}")
            
            elements.append(PageBreak())
        
        # Data Tables Section
        for table_name, df in dataframes.items():
            elements.extend(self._create_data_table(df, title=table_name))
            elements.append(Spacer(1, 20))
        
        # Build PDF
        doc.build(elements)
        
        logger.info(f"PDF report generated: {output}")
        return output
    
    def export_simple_report(
        self,
        data: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> str:
        """Export a simple one-page report."""
        output = output_path or self.output_path or f"simple_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        doc = SimpleDocTemplate(output, pagesize=A4)
        elements = []
        
        # Title
        elements.append(Paragraph("Отчет", self.styles['CustomTitle']))
        elements.append(Spacer(1, 20))
        
        # Content
        for key, value in data.items():
            elements.append(Paragraph(f"<b>{key}:</b> {value}", self.styles['NormalText']))
            elements.append(Spacer(1, 6))
        
        doc.build(elements)
        logger.info(f"Simple PDF report generated: {output}")
        return output


def export_to_pdf(
    metrics: Dict[str, Any],
    charts: Optional[List[Dict[str, Any]]] = None,
    dataframes: Optional[Dict[str, pd.DataFrame]] = None,
    output_path: Optional[str] = None,
    title: str = "Аналитический отчет"
) -> str:
    """
    Convenience function to export dashboard to PDF.
    
    Args:
        metrics: KPI metrics dictionary
        charts: List of chart configurations
        dataframes: Dictionary of DataFrames
        output_path: Output file path
        title: Report title
        
    Returns:
        Path to generated PDF
    """
    exporter = PDFExporter()
    
    charts = charts or []
    dataframes = dataframes or {}
    
    return exporter.export_dashboard(
        metrics=metrics,
        charts=charts,
        dataframes=dataframes,
        output_path=output_path,
        title=title
    )
