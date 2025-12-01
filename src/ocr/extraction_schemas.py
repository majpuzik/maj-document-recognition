#!/usr/bin/env python3
"""
JSON Schemas for Structured Data Extraction
Validates output from data extractors

Author: Claude Code
Date: 2025-11-30
"""

from typing import Dict, Any, Optional
import json

# JSON Schema definitions following STRUCTURED_DATA_EXTRACTION.md

INVOICE_LINE_ITEMS_SCHEMA = {
    "type": "object",
    "required": ["line_items", "summary"],
    "properties": {
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["line_number", "description", "quantity", "unit_price", "total_gross"],
                "properties": {
                    "line_number": {"type": "integer", "minimum": 1},
                    "description": {"type": "string", "minLength": 1},
                    "quantity": {"type": "number", "minimum": 0},
                    "unit": {"type": "string"},
                    "unit_price": {"type": "number", "minimum": 0},
                    "vat_rate": {"type": "integer", "enum": [0, 10, 15, 21]},
                    "vat_amount": {"type": "number", "minimum": 0},
                    "total_net": {"type": "number", "minimum": 0},
                    "total_gross": {"type": "number", "minimum": 0}
                }
            }
        },
        "summary": {
            "type": "object",
            "required": ["total_net", "total_vat", "total_gross", "currency"],
            "properties": {
                "total_net": {"type": "number", "minimum": 0},
                "total_vat": {"type": "number", "minimum": 0},
                "total_gross": {"type": "number", "minimum": 0},
                "currency": {"type": "string", "pattern": "^[A-Z]{3}$"}
            }
        },
        "extraction_confidence": {"type": "number", "minimum": 0, "maximum": 100}
    }
}

BANK_STATEMENT_TRANSACTIONS_SCHEMA = {
    "type": "object",
    "required": ["transactions", "summary"],
    "properties": {
        "transactions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["date", "type", "amount", "currency"],
                "properties": {
                    "date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                    "type": {"type": "string", "enum": ["incoming", "outgoing", "unknown"]},
                    "amount": {"type": "number"},
                    "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
                    "counterparty": {"type": "string"},
                    "counterparty_account": {"type": "string"},
                    "variable_symbol": {"type": "string"},
                    "constant_symbol": {"type": "string"},
                    "specific_symbol": {"type": "string"},
                    "description": {"type": "string"}
                }
            }
        },
        "summary": {
            "type": "object",
            "required": ["opening_balance", "closing_balance", "total_incoming", "total_outgoing", "currency"],
            "properties": {
                "opening_balance": {"type": "number"},
                "closing_balance": {"type": "number"},
                "total_incoming": {"type": "number", "minimum": 0},
                "total_outgoing": {"type": "number", "minimum": 0},
                "transaction_count": {"type": "integer", "minimum": 0},
                "currency": {"type": "string", "pattern": "^[A-Z]{3}$"}
            }
        },
        "extraction_confidence": {"type": "number", "minimum": 0, "maximum": 100}
    }
}

RECEIPT_ITEMS_SCHEMA = {
    "type": "object",
    "required": ["items", "summary"],
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["line_number", "description", "total"],
                "properties": {
                    "line_number": {"type": "integer", "minimum": 1},
                    "description": {"type": "string", "minLength": 1},
                    "quantity": {"type": "number", "minimum": 0},
                    "unit": {"type": "string"},
                    "unit_price": {"type": "number", "minimum": 0},
                    "vat_rate": {"type": "integer", "enum": [0, 10, 15, 21]},
                    "total": {"type": "number", "minimum": 0}
                }
            }
        },
        "summary": {
            "type": "object",
            "required": ["total", "vat_breakdown", "currency"],
            "properties": {
                "total": {"type": "number", "minimum": 0},
                "vat_breakdown": {
                    "type": "object",
                    "properties": {
                        "21": {"type": "number", "minimum": 0},
                        "15": {"type": "number", "minimum": 0},
                        "10": {"type": "number", "minimum": 0}
                    }
                },
                "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
                "item_count": {"type": "integer", "minimum": 0}
            }
        },
        "eet": {
            "type": "object",
            "properties": {
                "fik": {"type": "string"},
                "bkp": {"type": "string"}
            }
        },
        "extraction_confidence": {"type": "number", "minimum": 0, "maximum": 100}
    }
}


class SchemaValidator:
    """Validates extracted data against JSON schemas"""

    SCHEMAS = {
        'invoice': INVOICE_LINE_ITEMS_SCHEMA,
        'bank_statement': BANK_STATEMENT_TRANSACTIONS_SCHEMA,
        'receipt': RECEIPT_ITEMS_SCHEMA
    }

    @classmethod
    def validate(cls, data: Dict[str, Any], doc_type: str) -> tuple[bool, Optional[str]]:
        """
        Validate extracted data against schema

        Args:
            data: Extracted data dictionary
            doc_type: 'invoice', 'bank_statement', or 'receipt'

        Returns:
            (is_valid, error_message)
        """
        try:
            # Try importing jsonschema (optional dependency)
            try:
                from jsonschema import validate, ValidationError

                schema = cls.SCHEMAS.get(doc_type)
                if not schema:
                    return False, f"Unknown document type: {doc_type}"

                validate(instance=data, schema=schema)
                return True, None

            except ImportError:
                # Fallback to basic validation without jsonschema
                return cls._basic_validate(data, doc_type)

        except Exception as e:
            return False, str(e)

    @classmethod
    def _basic_validate(cls, data: Dict[str, Any], doc_type: str) -> tuple[bool, Optional[str]]:
        """Basic validation without jsonschema library"""

        if doc_type == 'invoice':
            if 'line_items' not in data:
                return False, "Missing 'line_items' field"
            if 'summary' not in data:
                return False, "Missing 'summary' field"
            if not isinstance(data['line_items'], list):
                return False, "'line_items' must be an array"

            # Validate each item has required fields
            for item in data['line_items']:
                required = ['line_number', 'description', 'quantity', 'unit_price', 'total_gross']
                missing = [f for f in required if f not in item]
                if missing:
                    return False, f"Line item missing fields: {missing}"

        elif doc_type == 'bank_statement':
            if 'transactions' not in data:
                return False, "Missing 'transactions' field"
            if 'summary' not in data:
                return False, "Missing 'summary' field"
            if not isinstance(data['transactions'], list):
                return False, "'transactions' must be an array"

            for trans in data['transactions']:
                required = ['date', 'type', 'amount', 'currency']
                missing = [f for f in required if f not in trans]
                if missing:
                    return False, f"Transaction missing fields: {missing}"

        elif doc_type == 'receipt':
            if 'items' not in data:
                return False, "Missing 'items' field"
            if 'summary' not in data:
                return False, "Missing 'summary' field"
            if not isinstance(data['items'], list):
                return False, "'items' must be an array"

            for item in data['items']:
                required = ['line_number', 'description', 'total']
                missing = [f for f in required if f not in item]
                if missing:
                    return False, f"Item missing fields: {missing}"

        else:
            return False, f"Unknown document type: {doc_type}"

        return True, None


# Paperless-NGX Custom Field Mapping
PAPERLESS_CUSTOM_FIELDS = {
    # Basic financial fields
    'amount_total': {
        'id': 1,
        'name': 'Amount Total',
        'data_type': 'monetary'
    },
    'amount_vat': {
        'id': 2,
        'name': 'Amount VAT',
        'data_type': 'monetary'
    },
    'amount_net': {
        'id': 3,
        'name': 'Amount Net',
        'data_type': 'monetary'
    },
    'currency': {
        'id': 4,
        'name': 'Currency',
        'data_type': 'string'
    },

    # Date fields
    'date_issue': {
        'id': 5,
        'name': 'Date Issue',
        'data_type': 'date'
    },
    'date_due': {
        'id': 6,
        'name': 'Date Due',
        'data_type': 'date'
    },
    'date_paid': {
        'id': 7,
        'name': 'Date Paid',
        'data_type': 'date'
    },

    # Document identifiers
    'invoice_number': {
        'id': 8,
        'name': 'Invoice Number',
        'data_type': 'string'
    },
    'variable_symbol': {
        'id': 9,
        'name': 'Variable Symbol',
        'data_type': 'string'
    },
    'constant_symbol': {
        'id': 10,
        'name': 'Constant Symbol',
        'data_type': 'string'
    },

    # Supplier fields
    'supplier_name': {
        'id': 11,
        'name': 'Supplier Name',
        'data_type': 'string'
    },
    'supplier_ico': {
        'id': 12,
        'name': 'Supplier IČO',
        'data_type': 'string'
    },
    'supplier_dic': {
        'id': 13,
        'name': 'Supplier DIČ',
        'data_type': 'string'
    },

    # Bank fields
    'bank_account': {
        'id': 14,
        'name': 'Bank Account',
        'data_type': 'string'
    },
    'iban': {
        'id': 15,
        'name': 'IBAN',
        'data_type': 'string'
    },

    # EET fields
    'eet_fik': {
        'id': 16,
        'name': 'EET FIK',
        'data_type': 'string'
    },
    'eet_bkp': {
        'id': 17,
        'name': 'EET BKP',
        'data_type': 'string'
    },

    # Balance fields
    'opening_balance': {
        'id': 18,
        'name': 'Opening Balance',
        'data_type': 'monetary'
    },
    'closing_balance': {
        'id': 19,
        'name': 'Closing Balance',
        'data_type': 'monetary'
    },

    # Structured data JSON fields
    'line_items': {
        'id': 20,
        'name': 'Line Items (JSON)',
        'data_type': 'string'  # JSON stored as string
    },
    'transactions': {
        'id': 21,
        'name': 'Transactions (JSON)',
        'data_type': 'string'  # JSON stored as string
    },
    'receipt_items': {
        'id': 22,
        'name': 'Receipt Items (JSON)',
        'data_type': 'string'  # JSON stored as string
    }
}


def format_for_paperless(extracted_data: Dict[str, Any], doc_type: str) -> Dict[str, Any]:
    """
    Format extracted data for Paperless-NGX custom fields

    Args:
        extracted_data: Output from data extractors
        doc_type: 'invoice', 'bank_statement', or 'receipt'

    Returns:
        Paperless-NGX custom fields array
    """
    custom_fields = []

    if doc_type == 'invoice':
        # Basic financial fields
        if 'summary' in extracted_data:
            summary = extracted_data['summary']
            custom_fields.extend([
                {'field': PAPERLESS_CUSTOM_FIELDS['amount_total']['id'],
                 'value': str(summary.get('total_gross', 0))},
                {'field': PAPERLESS_CUSTOM_FIELDS['amount_vat']['id'],
                 'value': str(summary.get('total_vat', 0))},
                {'field': PAPERLESS_CUSTOM_FIELDS['amount_net']['id'],
                 'value': str(summary.get('total_net', 0))},
                {'field': PAPERLESS_CUSTOM_FIELDS['currency']['id'],
                 'value': summary.get('currency', 'CZK')}
            ])

        # Structured data as JSON
        if 'line_items' in extracted_data:
            custom_fields.append({
                'field': PAPERLESS_CUSTOM_FIELDS['line_items']['id'],
                'value': json.dumps(extracted_data, ensure_ascii=False)
            })

    elif doc_type == 'bank_statement':
        # Balance fields
        if 'summary' in extracted_data:
            summary = extracted_data['summary']
            custom_fields.extend([
                {'field': PAPERLESS_CUSTOM_FIELDS['opening_balance']['id'],
                 'value': str(summary.get('opening_balance', 0))},
                {'field': PAPERLESS_CUSTOM_FIELDS['closing_balance']['id'],
                 'value': str(summary.get('closing_balance', 0))},
                {'field': PAPERLESS_CUSTOM_FIELDS['currency']['id'],
                 'value': summary.get('currency', 'CZK')}
            ])

        # Structured data as JSON
        if 'transactions' in extracted_data:
            custom_fields.append({
                'field': PAPERLESS_CUSTOM_FIELDS['transactions']['id'],
                'value': json.dumps(extracted_data, ensure_ascii=False)
            })

    elif doc_type == 'receipt':
        # Basic fields
        if 'summary' in extracted_data:
            summary = extracted_data['summary']
            custom_fields.extend([
                {'field': PAPERLESS_CUSTOM_FIELDS['amount_total']['id'],
                 'value': str(summary.get('total', 0))},
                {'field': PAPERLESS_CUSTOM_FIELDS['currency']['id'],
                 'value': summary.get('currency', 'CZK')}
            ])

        # EET fields
        if 'eet' in extracted_data:
            eet = extracted_data['eet']
            if eet.get('fik'):
                custom_fields.append({
                    'field': PAPERLESS_CUSTOM_FIELDS['eet_fik']['id'],
                    'value': eet['fik']
                })
            if eet.get('bkp'):
                custom_fields.append({
                    'field': PAPERLESS_CUSTOM_FIELDS['eet_bkp']['id'],
                    'value': eet['bkp']
                })

        # Structured data as JSON
        if 'items' in extracted_data:
            custom_fields.append({
                'field': PAPERLESS_CUSTOM_FIELDS['receipt_items']['id'],
                'value': json.dumps(extracted_data, ensure_ascii=False)
            })

    return custom_fields


if __name__ == "__main__":
    # Test validation
    print("=" * 70)
    print("SCHEMA VALIDATION TEST")
    print("=" * 70)

    # Test invoice data
    invoice_data = {
        "line_items": [
            {
                "line_number": 1,
                "description": "Test Item",
                "quantity": 1.0,
                "unit": "ks",
                "unit_price": 100.0,
                "vat_rate": 21,
                "vat_amount": 21.0,
                "total_net": 100.0,
                "total_gross": 121.0
            }
        ],
        "summary": {
            "total_net": 100.0,
            "total_vat": 21.0,
            "total_gross": 121.0,
            "currency": "CZK"
        },
        "extraction_confidence": 95.0
    }

    is_valid, error = SchemaValidator.validate(invoice_data, 'invoice')
    print(f"\nInvoice validation: {'✅ PASS' if is_valid else '❌ FAIL'}")
    if error:
        print(f"Error: {error}")

    # Test Paperless formatting
    print("\n" + "=" * 70)
    print("PAPERLESS FORMATTING TEST")
    print("=" * 70)

    custom_fields = format_for_paperless(invoice_data, 'invoice')
    print(f"\nGenerated {len(custom_fields)} custom fields:")
    for field in custom_fields:
        field_name = next((v['name'] for v in PAPERLESS_CUSTOM_FIELDS.values()
                          if v['id'] == field['field']), 'Unknown')
        print(f"  - {field_name}: {field['value'][:50]}...")

    print("\n✅ Schema validation module ready!")
