#!/usr/bin/env python3
"""
NAS5 Docker Apps Collection
"""

"""
This project implements a Model Context Protocol (MCP) server that allows interaction with Gmail accounts via IMAP and SMTP. It provides tools for searching emails, retrieving content, managing labels
"""

"""
This project implements a Model Context Protocol (MCP) server that allows interaction with Gmail accounts via IMAP and SMTP. It provides tools for searching emails, retrieving content, managing labels
"""

"""
Excel Bank Statement Processor
Zpracovává Excel bankovní výpisy a převádí je na PDF + vkládá do databáze
"""
import pandas as pd
from pathlib import Path
import sys
import logging
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import cm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ExcelStatementProcessor:
    """Procesor pro Excel bankovní výpisy"""

    def __init__(self):
        pass

    def analyze_excel_statement(self, excel_path: str):
        """
        Analyzuje Excel bankovní výpis a zjistí typ

        Returns:
            Dict with analysis results
        """
        try:
            # Try to read with openpyxl (xlsx)
            if excel_path.endswith('.xlsx'):
                df = pd.read_excel(excel_path, engine='openpyxl', sheet_name=0)
            else:  # xls
                df = pd.read_excel(excel_path, engine='xlrd', sheet_name=0)

            logger.info(f"📊 Excel má {len(df)} řádků a {len(df.columns)} sloupců")
            logger.info(f"   Sloupce: {list(df.columns)[:5]}")

            # Detect if it's bank statement
            is_bank_statement = False
            confidence = 0

            # Check column names
            column_names = ' '.join([str(c).lower() for c in df.columns])

            keywords = ['datum', 'date', 'částka', 'amount', 'castka', 'zůstatek',
                       'zustatek', 'balance', 'transakce', 'transaction', 'popis', 'description']

            for keyword in keywords:
                if keyword in column_names:
                    confidence += 15

            # Check for numeric amounts
            numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
            if len(numeric_cols) >= 1:
                confidence += 20

            # Check for date columns
            for col in df.columns:
                if 'datum' in str(col).lower() or 'date' in str(col).lower():
                    confidence += 20
                    break

            if confidence >= 50:
                is_bank_statement = True

            return {
                'type': 'bank_statement' if is_bank_statement else 'spreadsheet',
                'confidence': min(confidence, 100),
                'rows': len(df),
                'columns': len(df.columns),
                'has_amounts': len(numeric_cols) > 0
            }

        except Exception as e:
            logger.error(f"❌ Chyba při analýze Excel: {e}")
            return None

    def convert_to_pdf(self, excel_path: str, pdf_path: str = None):
        """
        Převede Excel bankovní výpis na formátované PDF

        Args:
            excel_path: Cesta k Excel souboru
            pdf_path: Cesta k výstupnímu PDF (optional)

        Returns:
            Path to created PDF
        """
        if pdf_path is None:
            pdf_path = excel_path.replace('.xlsx', '.pdf').replace('.xls', '.pdf')

        try:
            # Load Excel
            if excel_path.endswith('.xlsx'):
                df = pd.read_excel(excel_path, engine='openpyxl', sheet_name=0)
            else:
                df = pd.read_excel(excel_path, engine='xlrd', sheet_name=0)

            logger.info(f"📄 Převádím {excel_path} na PDF...")
            logger.info(f"   Shape: {df.shape}")

            # Create PDF
            doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                                   leftMargin=1*cm, rightMargin=1*cm,
                                   topMargin=1.5*cm, bottomMargin=1.5*cm)
            story = []
            styles = getSampleStyleSheet()

            # Title
            filename = Path(excel_path).name
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=14,
                textColor=colors.HexColor('#003366'),
                spaceAfter=20,
            )
            story.append(Paragraph(f"Bankovní výpis - {filename}", title_style))
            story.append(Spacer(1, 12))

            # Info
            info_style = styles['Normal']
            story.append(Paragraph(f"Počet transakcí: {len(df)}", info_style))
            story.append(Spacer(1, 12))

            # Table data
            # Limit columns to fit on page (max 6 columns)
            max_cols = 6
            df_display = df.iloc[:, :max_cols]

            # Convert to list of lists for reportlab
            data = [list(df_display.columns)]

            for idx, row in df_display.iterrows():
                row_data = []
                for val in row:
                    # Format values
                    if pd.isna(val):
                        row_data.append('')
                    elif isinstance(val, (int, float)):
                        row_data.append(f"{val:.2f}" if isinstance(val, float) else str(val))
                    else:
                        val_str = str(val)
                        # Truncate long strings
                        row_data.append(val_str[:50] + '...' if len(val_str) > 50 else val_str)
                data.append(row_data)

            # Calculate column widths dynamically
            available_width = 500  # points
            col_width = available_width / len(df_display.columns)
            col_widths = [col_width] * len(df_display.columns)

            # Create table
            table = Table(data, colWidths=col_widths, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('TOPPADDING', (0, 1), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))

            story.append(table)

            # Build PDF
            doc.build(story)
            logger.info(f"✅ PDF vytvořeno: {pdf_path}")
            return pdf_path

        except Exception as e:
            logger.error(f"❌ Chyba při konverzi na PDF: {e}")
            import traceback
            traceback.print_exc()
            return None


def main():
    """Process all Excel bank statements in MBW folder"""
    mbw_path = Path.home() / "Dropbox" / "MBW"

    # Find all Excel files
    excel_files = list(mbw_path.glob("**/*.xlsx")) + list(mbw_path.glob("**/*.xls"))

    logger.info(f"🔍 Nalezeno {len(excel_files)} Excel souborů")

    processor = ExcelStatementProcessor()

    for excel_file in excel_files:
        # Skip temp/system files
        if excel_file.name.startswith('~') or excel_file.name.startswith('.'):
            continue

        logger.info(f"\n📊 Zpracovávám: {excel_file.name}")

        # Analyze
        analysis = processor.analyze_excel_statement(str(excel_file))
        if analysis:
            logger.info(f"   Typ: {analysis['type']} (confidence: {analysis['confidence']}%)")

            if analysis['type'] == 'bank_statement':
                # Convert to PDF
                pdf_path = str(excel_file).replace('.xlsx', '_converted.pdf').replace('.xls', '_converted.pdf')
                result = processor.convert_to_pdf(str(excel_file), pdf_path)

                if result:
                    logger.info(f"   ✅ Úspěch: {pdf_path}")

                    # Now the PDF can be processed by main document processor
                    logger.info(f"   💡 Nyní můžete zpracovat: {pdf_path}")
        else:
            logger.warning(f"   ⚠️  Analýza selhala")

    logger.info(f"\n✅ Hotovo! Zpracováno {len(excel_files)} souborů")


if __name__ == '__main__':
    main()
