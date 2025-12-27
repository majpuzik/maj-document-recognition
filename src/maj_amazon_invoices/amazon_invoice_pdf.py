#!/usr/bin/env python3
"""
Amazon Business Invoice PDF Generator
======================================
Generates professional PDF invoices from Amazon Business order data.
Style matches Amazon Business invoice format.

Uses data from AmazonInvoiceCSVParser.

Author: Claude Code
Date: 2025-12-27
"""

import os
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, PageBreak
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Try to import AmazonOrder, but allow standalone use
try:
    from .amazon_invoice_csv import AmazonOrder, AmazonOrderItem
except ImportError:
    AmazonOrder = None
    AmazonOrderItem = None


# Amazon brand colors
AMAZON_ORANGE = colors.HexColor('#FF9900')
AMAZON_DARK = colors.HexColor('#232F3E')
AMAZON_LIGHT_GRAY = colors.HexColor('#F7F7F7')
AMAZON_GRAY = colors.HexColor('#565959')
AMAZON_LINK = colors.HexColor('#007185')

# Register open-source DejaVu fonts with Czech diacritics support
_fonts_registered = False
_FONT_DIR = Path(__file__).parent / 'fonts'

def _register_fonts():
    """Register bundled DejaVu fonts (open source, Bitstream Vera license)"""
    global _fonts_registered
    if _fonts_registered:
        return

    try:
        dejavu_regular = _FONT_DIR / 'DejaVuSans.ttf'
        dejavu_bold = _FONT_DIR / 'DejaVuSans-Bold.ttf'

        if dejavu_regular.exists() and dejavu_bold.exists():
            pdfmetrics.registerFont(TTFont('DejaVuSans', str(dejavu_regular)))
            pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', str(dejavu_bold)))

            from reportlab.pdfbase.pdfmetrics import registerFontFamily
            registerFontFamily('DejaVuSans',
                normal='DejaVuSans',
                bold='DejaVuSans-Bold',
            )
            _fonts_registered = True
        else:
            print(f"Warning: DejaVu fonts not found in {_FONT_DIR}")
    except Exception as e:
        print(f"Warning: Could not register DejaVu fonts: {e}")
        # Fallback will use Helvetica

_register_fonts()


class AmazonInvoicePDF:
    """
    Generates Amazon-style PDF invoices

    Usage:
        generator = AmazonInvoicePDF()
        generator.generate(order, '/path/to/invoice.pdf')
    """

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        """Setup custom paragraph styles with Czech diacritics support"""
        # Use DejaVu Sans (open source) for Czech support, fallback to Helvetica
        font_normal = 'DejaVuSans' if _fonts_registered else 'Helvetica'
        font_bold = 'DejaVuSans-Bold' if _fonts_registered else 'Helvetica-Bold'

        # Title style
        self.styles.add(ParagraphStyle(
            name='InvoiceTitle',
            parent=self.styles['Heading1'],
            fontName=font_bold,
            fontSize=24,
            textColor=AMAZON_DARK,
            spaceAfter=6*mm,
            alignment=TA_LEFT,
        ))

        # Subtitle
        self.styles.add(ParagraphStyle(
            name='InvoiceSubtitle',
            parent=self.styles['Normal'],
            fontName=font_normal,
            fontSize=11,
            textColor=AMAZON_GRAY,
            spaceAfter=3*mm,
        ))

        # Section header
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontName=font_bold,
            fontSize=12,
            textColor=AMAZON_DARK,
            spaceBefore=6*mm,
            spaceAfter=3*mm,
            borderPadding=2*mm,
        ))

        # Normal text
        self.styles.add(ParagraphStyle(
            name='InvoiceNormal',
            parent=self.styles['Normal'],
            fontName=font_normal,
            fontSize=9,
            textColor=AMAZON_GRAY,
            leading=12,
        ))

        # Bold text
        self.styles.add(ParagraphStyle(
            name='InvoiceBold',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=AMAZON_DARK,
            fontName=font_bold,
        ))

        # Right aligned
        self.styles.add(ParagraphStyle(
            name='InvoiceRight',
            parent=self.styles['Normal'],
            fontName=font_normal,
            fontSize=9,
            textColor=AMAZON_GRAY,
            alignment=TA_RIGHT,
        ))

        # Small text
        self.styles.add(ParagraphStyle(
            name='InvoiceSmall',
            parent=self.styles['Normal'],
            fontName=font_normal,
            fontSize=7,
            textColor=AMAZON_GRAY,
            leading=9,
        ))

        # Total style
        self.styles.add(ParagraphStyle(
            name='TotalAmount',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=AMAZON_DARK,
            fontName=font_bold,
            alignment=TA_RIGHT,
        ))

    def generate(self, order, output_path: str) -> str:
        """
        Generate PDF invoice from AmazonOrder

        Args:
            order: AmazonOrder object or dict with order data
            output_path: Path for output PDF file

        Returns:
            Path to generated PDF
        """
        # Handle dict input
        if isinstance(order, dict):
            order = self._dict_to_order(order)

        # Create PDF document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=15*mm,
            bottomMargin=20*mm,
        )

        # Build content
        story = []

        # Header
        story.extend(self._build_header(order))

        # Order info
        story.extend(self._build_order_info(order))

        # Parties (seller/buyer)
        story.extend(self._build_parties(order))

        # Items table
        story.extend(self._build_items_table(order))

        # Totals
        story.extend(self._build_totals(order))

        # Payment info
        story.extend(self._build_payment_info(order))

        # Footer
        story.extend(self._build_footer(order))

        # Generate PDF
        doc.build(story, onFirstPage=self._add_page_elements, onLaterPages=self._add_page_elements)

        return output_path

    def _build_header(self, order) -> List:
        """Build invoice header with Amazon branding"""
        elements = []

        # Font for logo
        logo_font = 'DejaVuSans-Bold' if _fonts_registered else 'Helvetica-Bold'

        # Amazon logo - two lines stacked and vertically centered
        logo_style = ParagraphStyle(
            'Logo',
            fontSize=12,
            textColor=colors.white,
            fontName=logo_font,
            leading=14,
            spaceBefore=0,
            spaceAfter=0,
        )

        # Amazon logo placeholder (orange bar)
        logo_table = Table(
            [[Paragraph('<b>amazon</b><br/>business', logo_style)]],
            colWidths=[45*mm],
            rowHeights=[12*mm],
        )
        logo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), AMAZON_ORANGE),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3*mm),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))

        # Header row with logo and invoice title
        header_data = [
            [logo_table, Paragraph('FAKTURA / INVOICE', self.styles['InvoiceTitle'])]
        ]
        header_table = Table(header_data, colWidths=[55*mm, 125*mm])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(header_table)

        # Orange line separator
        elements.append(Spacer(1, 3*mm))
        elements.append(HRFlowable(
            width='100%',
            thickness=2,
            color=AMAZON_ORANGE,
            spaceBefore=0,
            spaceAfter=5*mm,
        ))

        return elements

    def _build_order_info(self, order) -> List:
        """Build order information section"""
        elements = []

        # Format dates
        order_date = order.order_date.strftime('%d.%m.%Y') if order.order_date else '-'
        invoice_date = order.invoice_date.strftime('%d.%m.%Y') if order.invoice_date else order_date
        due_date = order.due_date.strftime('%d.%m.%Y') if order.due_date else '-'

        # Order info table
        info_data = [
            [
                Paragraph('<b>Číslo objednávky / Order Number:</b>', self.styles['InvoiceNormal']),
                Paragraph(f'<b>{order.order_number}</b>', self.styles['InvoiceBold']),
            ],
            [
                Paragraph('Datum objednávky / Order Date:', self.styles['InvoiceNormal']),
                Paragraph(order_date, self.styles['InvoiceNormal']),
            ],
            [
                Paragraph('Datum vystavení / Invoice Date:', self.styles['InvoiceNormal']),
                Paragraph(invoice_date, self.styles['InvoiceNormal']),
            ],
            [
                Paragraph('Datum splatnosti / Due Date:', self.styles['InvoiceNormal']),
                Paragraph(due_date, self.styles['InvoiceNormal']),
            ],
            [
                Paragraph('Měna / Currency:', self.styles['InvoiceNormal']),
                Paragraph(order.currency, self.styles['InvoiceNormal']),
            ],
            [
                Paragraph('Stav / Status:', self.styles['InvoiceNormal']),
                Paragraph(order.status, self.styles['InvoiceNormal']),
            ],
        ]

        info_table = Table(info_data, colWidths=[60*mm, 60*mm])
        info_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 1*mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1*mm),
        ]))

        elements.append(info_table)
        elements.append(Spacer(1, 5*mm))

        return elements

    def _build_parties(self, order) -> List:
        """Build seller/buyer information"""
        elements = []

        # Get first item's seller info
        seller_name = "Amazon EU S.a.r.l."
        seller_vat = ""
        seller_country = "LU"

        if order.items:
            item = order.items[0]
            if item.seller_name:
                seller_name = item.seller_name
            if item.seller_vat_id:
                seller_vat = item.seller_vat_id
            if item.seller_country:
                seller_country = item.seller_country

        # Seller info
        seller_content = f"""
        <b>{seller_name}</b><br/>
        {f'DIC/VAT: {seller_vat}' if seller_vat else ''}<br/>
        Země/Country: {seller_country}
        """

        # Buyer info
        buyer_name = order.account_group or order.account_user or "Unknown"
        buyer_content = f"""
        <b>{buyer_name}</b><br/>
        {order.account_user or ''}<br/>
        {order.user_email or ''}<br/>
        {f'DIC/VAT: {order.user_vat_id}' if order.user_vat_id else ''}<br/>
        Země/Country: {order.user_vat_country or 'CZ'}
        """

        # Two column layout
        parties_data = [
            [
                Paragraph('<b>Prodávající / Seller:</b>', self.styles['SectionHeader']),
                Paragraph('<b>Odběratel / Buyer:</b>', self.styles['SectionHeader']),
            ],
            [
                Paragraph(seller_content, self.styles['InvoiceNormal']),
                Paragraph(buyer_content, self.styles['InvoiceNormal']),
            ]
        ]

        parties_table = Table(parties_data, colWidths=[90*mm, 90*mm])
        parties_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (-1, 0), AMAZON_LIGHT_GRAY),
            ('TOPPADDING', (0, 0), (-1, -1), 2*mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2*mm),
            ('LEFTPADDING', (0, 0), (-1, -1), 3*mm),
        ]))

        elements.append(parties_table)
        elements.append(Spacer(1, 5*mm))

        return elements

    def _build_items_table(self, order) -> List:
        """Build items table"""
        elements = []

        elements.append(Paragraph('<b>Položky / Items:</b>', self.styles['SectionHeader']))

        # Table header
        header = [
            Paragraph('<b>#</b>', self.styles['InvoiceSmall']),
            Paragraph('<b>ASIN</b>', self.styles['InvoiceSmall']),
            Paragraph('<b>Popis / Description</b>', self.styles['InvoiceSmall']),
            Paragraph('<b>Množství</b>', self.styles['InvoiceSmall']),
            Paragraph('<b>Cena/ks</b>', self.styles['InvoiceSmall']),
            Paragraph('<b>DPH %</b>', self.styles['InvoiceSmall']),
            Paragraph('<b>Celkem</b>', self.styles['InvoiceSmall']),
        ]

        # Table data
        table_data = [header]

        for idx, item in enumerate(order.items, 1):
            # Truncate long titles
            title = item.title
            if len(title) > 60:
                title = title[:57] + '...'

            row = [
                Paragraph(str(idx), self.styles['InvoiceSmall']),
                Paragraph(item.asin or '-', self.styles['InvoiceSmall']),
                Paragraph(title, self.styles['InvoiceSmall']),
                Paragraph(f'{item.quantity:.0f}', self.styles['InvoiceSmall']),
                Paragraph(f'{item.unit_price:.2f}', self.styles['InvoiceSmall']),
                Paragraph(f'{item.vat_rate:.0f}%', self.styles['InvoiceSmall']),
                Paragraph(f'{item.gross_total:.2f}', self.styles['InvoiceSmall']),
            ]
            table_data.append(row)

        # Column widths
        col_widths = [8*mm, 22*mm, 75*mm, 15*mm, 18*mm, 15*mm, 20*mm]

        # Font for table header
        table_font = 'DejaVuSans-Bold' if _fonts_registered else 'Helvetica-Bold'

        items_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        items_table.setStyle(TableStyle([
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), AMAZON_DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), table_font),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

            # Data rows
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # #
            ('ALIGN', (3, 1), (3, -1), 'CENTER'),  # Qty
            ('ALIGN', (4, 1), (-1, -1), 'RIGHT'),  # Prices

            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, AMAZON_LIGHT_GRAY]),

            # Borders
            ('LINEBELOW', (0, 0), (-1, 0), 1, AMAZON_ORANGE),
            ('LINEBELOW', (0, -1), (-1, -1), 1, AMAZON_GRAY),

            # Padding
            ('TOPPADDING', (0, 0), (-1, -1), 2*mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2*mm),
            ('LEFTPADDING', (0, 0), (-1, -1), 1*mm),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1*mm),

            # Valign
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))

        elements.append(items_table)
        elements.append(Spacer(1, 5*mm))

        return elements

    def _build_totals(self, order) -> List:
        """Build totals section"""
        elements = []

        currency = order.currency

        # Calculate net total from items
        items_net = sum(item.net_total for item in order.items)
        items_vat = sum(item.vat_amount for item in order.items)
        items_gross = sum(item.gross_total for item in order.items)

        # Use order totals if available, otherwise calculated
        subtotal = order.subtotal if order.subtotal else items_net
        shipping = order.shipping if order.shipping else 0
        promotion = order.promotion if order.promotion else 0
        vat = order.vat if order.vat else items_vat
        total = order.total_incl_vat if order.total_incl_vat else items_gross

        totals_data = [
            [
                Paragraph('Mezisoučet položek / Items subtotal:', self.styles['InvoiceNormal']),
                Paragraph(f'{subtotal:.2f} {currency}', self.styles['InvoiceRight']),
            ],
            [
                Paragraph('Doprava / Shipping:', self.styles['InvoiceNormal']),
                Paragraph(f'{shipping:.2f} {currency}', self.styles['InvoiceRight']),
            ],
        ]

        if promotion != 0:
            totals_data.append([
                Paragraph('Sleva / Promotion:', self.styles['InvoiceNormal']),
                Paragraph(f'{promotion:.2f} {currency}', self.styles['InvoiceRight']),
            ])

        totals_data.extend([
            [
                Paragraph('DPH / VAT:', self.styles['InvoiceNormal']),
                Paragraph(f'{vat:.2f} {currency}', self.styles['InvoiceRight']),
            ],
            [
                Paragraph('<b>CELKEM / TOTAL:</b>', self.styles['InvoiceBold']),
                Paragraph(f'<b>{total:.2f} {currency}</b>', self.styles['TotalAmount']),
            ],
        ])

        # Right-aligned totals table
        totals_table = Table(totals_data, colWidths=[50*mm, 35*mm])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 1*mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1*mm),
            ('LINEABOVE', (0, -1), (-1, -1), 1, AMAZON_ORANGE),
            ('BACKGROUND', (0, -1), (-1, -1), AMAZON_LIGHT_GRAY),
        ]))

        # Wrap in outer table to right-align
        outer_data = [[Spacer(1, 1), totals_table]]
        outer_table = Table(outer_data, colWidths=[95*mm, 85*mm])
        outer_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))

        elements.append(outer_table)
        elements.append(Spacer(1, 5*mm))

        return elements

    def _build_payment_info(self, order) -> List:
        """Build payment information section"""
        elements = []

        if order.payment_method:
            elements.append(Paragraph('<b>Platba / Payment:</b>', self.styles['SectionHeader']))

            payment_date = order.payment_date.strftime('%d.%m.%Y') if order.payment_date else '-'

            payment_content = f"""
            Způsob platby / Payment method: <b>{order.payment_method}</b><br/>
            Datum platby / Payment date: {payment_date}<br/>
            {f'Reference: {order.payment_reference}' if order.payment_reference else ''}
            """

            elements.append(Paragraph(payment_content, self.styles['InvoiceNormal']))
            elements.append(Spacer(1, 5*mm))

        return elements

    def _build_footer(self, order) -> List:
        """Build invoice footer"""
        elements = []

        elements.append(HRFlowable(
            width='100%',
            thickness=1,
            color=AMAZON_GRAY,
            spaceBefore=5*mm,
            spaceAfter=3*mm,
        ))

        footer_text = f"""
        Tento doklad byl vygenerován automaticky ze systému Amazon Business.<br/>
        This document was automatically generated from Amazon Business system.<br/>
        <br/>
        Objednávka / Order: {order.order_number}<br/>
        Vygenerováno / Generated: {datetime.now().strftime('%d.%m.%Y %H:%M')}
        """

        elements.append(Paragraph(footer_text, self.styles['InvoiceSmall']))

        return elements

    def _add_page_elements(self, canvas, doc):
        """Add page numbers and other elements"""
        canvas.saveState()

        # Page number with Czech-friendly font
        page_font = 'DejaVuSans' if _fonts_registered else 'Helvetica'
        page_num = canvas.getPageNumber()
        text = f"Strana / Page {page_num}"
        canvas.setFont(page_font, 8)
        canvas.setFillColor(AMAZON_GRAY)
        canvas.drawRightString(A4[0] - 15*mm, 10*mm, text)

        canvas.restoreState()

    def _dict_to_order(self, data: dict):
        """Convert dictionary to order-like object"""
        class DictOrder:
            pass

        class DictItem:
            pass

        order = DictOrder()
        order.order_number = data.get('number', data.get('order_number', ''))
        order.order_date = data.get('issue_date', data.get('order_date', datetime.now()))
        order.invoice_date = data.get('issue_date')
        order.due_date = data.get('due_date')
        order.currency = data.get('currency', 'EUR')
        order.status = data.get('status', 'Completed')

        # Customer info
        customer = data.get('customer', {})
        order.account_group = customer.get('name')
        order.account_user = customer.get('contact_name')
        order.user_email = customer.get('email')
        order.user_vat_id = customer.get('dic')
        order.user_vat_country = customer.get('country', 'CZ')

        # Totals
        summary = data.get('summary', {})
        order.subtotal = summary.get('total_net', 0)
        order.shipping = summary.get('shipping', 0)
        order.promotion = summary.get('promotion', 0)
        order.vat = summary.get('total_vat', 0)
        order.total_incl_vat = summary.get('total_gross', 0)

        # Payment
        payment = data.get('payment', {})
        order.payment_method = payment.get('method')
        order.payment_date = payment.get('date')
        order.payment_reference = payment.get('reference')

        # Items
        order.items = []
        for item_data in data.get('items', []):
            item = DictItem()
            item.asin = item_data.get('asin', '')
            item.title = item_data.get('description', '')
            item.quantity = item_data.get('quantity', 1)
            item.unit_price = item_data.get('unit_price', 0)
            item.vat_rate = item_data.get('vat_rate', 0)
            item.net_total = item_data.get('net_amount', 0)
            item.vat_amount = item_data.get('vat_amount', 0)
            item.seller_name = item_data.get('seller_name')
            item.seller_vat_id = item_data.get('seller_vat_id')
            item.seller_country = None

            # Calculated gross
            item.gross_total = item.net_total + item.vat_amount

            order.items.append(item)

        return order


def generate_amazon_invoice_pdf(order, output_path: str) -> str:
    """
    Convenience function to generate Amazon invoice PDF

    Args:
        order: AmazonOrder object or dict
        output_path: Output PDF path

    Returns:
        Path to generated PDF
    """
    generator = AmazonInvoicePDF()
    return generator.generate(order, output_path)


if __name__ == "__main__":
    import sys
    import json

    print("=" * 70)
    print("Amazon Invoice PDF Generator")
    print("=" * 70)

    # Test with sample data
    sample_order = {
        "number": "028-5217580-1995537",
        "issue_date": datetime(2025, 12, 21),
        "due_date": datetime(2026, 1, 21),
        "currency": "EUR",
        "status": "Abgeschlossen",
        "customer": {
            "name": "Softel Consulting s.r.o",
            "contact_name": "maj puzik",
            "email": "Puzik@softel.cz",
            "dic": "CZ16188047",
            "country": "CZ"
        },
        "summary": {
            "total_net": 54.70,
            "total_vat": 0.0,
            "total_gross": 54.70,
            "shipping": 6.98,
            "promotion": -6.98
        },
        "payment": {
            "method": "MasterCard",
            "date": datetime(2025, 12, 22),
            "reference": "3213"
        },
        "items": [
            {
                "asin": "B0C364Y72M",
                "description": "Wireless Charger 20W Max Schnelles Kabellosen Ladepad",
                "quantity": 1,
                "unit_price": 10.17,
                "vat_rate": 0,
                "net_amount": 10.17,
                "vat_amount": 0.0,
                "seller_name": "Huizhou Yili Information Technology Co., Ltd",
                "seller_vat_id": "DE341831782"
            },
            {
                "asin": "B0CHJM5P88",
                "description": "USB C Ladegerat 45W PD 3.0 Schnellladegerat mit GaN",
                "quantity": 1,
                "unit_price": 44.53,
                "vat_rate": 0,
                "net_amount": 44.53,
                "vat_amount": 0.0,
                "seller_name": "Shenzhen BHHB Technology Co., Ltd",
                "seller_vat_id": None
            }
        ]
    }

    output_path = "/tmp/amazon_invoice_test.pdf"
    result = generate_amazon_invoice_pdf(sample_order, output_path)
    print(f"\nGenerated: {result}")
    print(f"File size: {os.path.getsize(result)} bytes")
