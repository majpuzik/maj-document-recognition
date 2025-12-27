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
        # NEW v1.1: Invoice subject (předmět faktury)
        "subject": {
            "type": "string",
            "description": "Předmět faktury - souhrn fakturovaných položek"
        },
        # NEW v1.1: Item type classification
        "item_type": {
            "type": "string",
            "enum": ["service", "goods", "mixed"],
            "description": "Typ položek: služba, zboží, nebo mix"
        },
        # NEW v1.1: ISDOC metadata
        "isdoc": {
            "type": "object",
            "properties": {
                "is_isdoc": {"type": "boolean"},
                "version": {"type": "string"},
                "uuid": {"type": "string"}
            }
        },
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
                    "total_gross": {"type": "number", "minimum": 0},
                    # NEW v1.1: Per-item type classification
                    "item_type": {
                        "type": "string",
                        "enum": ["service", "goods"],
                        "description": "Typ položky: služba nebo zboží"
                    }
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
# Field IDs are loaded at runtime from Paperless API - no hardcoded instance-specific IDs

_field_cache: Dict[str, int] = {}


def load_field_ids(api_url: str, api_token: str) -> Dict[str, int]:
    """
    Load custom field name->ID mappings from Paperless API.
    Call once at startup, result is cached.

    Args:
        api_url: Paperless API URL (e.g., "http://localhost:8000/api")
        api_token: Paperless API token

    Returns:
        Dict mapping field names to IDs
    """
    global _field_cache
    if _field_cache:
        return _field_cache

    try:
        import requests
        resp = requests.get(
            f"{api_url}/custom_fields/",
            headers={"Authorization": f"Token {api_token}"},
            timeout=10
        )
        if resp.status_code == 200:
            for field in resp.json().get('results', []):
                _field_cache[field['name']] = field['id']
    except Exception as e:
        print(f"Warning: Failed to load Paperless fields: {e}")

    return _field_cache


def get_field_id(field_name: str) -> Optional[int]:
    """Get field ID by name from cache. Call load_field_ids() first."""
    return _field_cache.get(field_name)


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
    },

    # === NEW FIELDS v1.1 (2025-12-27) ===
    # Invoice subject/description (předmět faktury)
    'invoice_subject': {
        'id': 23,
        'name': 'Invoice Subject',
        'data_type': 'string',
        'description': 'Předmět faktury - souhrn fakturovaných položek'
    },

    # Item type classification (služba/zboží)
    'item_type': {
        'id': 24,
        'name': 'Item Type',
        'data_type': 'select',
        'choices': ['service', 'goods', 'mixed'],
        'description': 'Typ položek: služba (service), zboží (goods), nebo mix (mixed)'
    },

    # ISDOC detection and content
    'is_isdoc': {
        'id': 25,
        'name': 'Is ISDOC',
        'data_type': 'boolean',
        'description': 'Dokument obsahuje nebo je ISDOC XML'
    },
    'isdoc_version': {
        'id': 26,
        'name': 'ISDOC Version',
        'data_type': 'string',
        'description': 'Verze ISDOC formátu (např. 6.0.2)'
    },
    'isdoc_uuid': {
        'id': 27,
        'name': 'ISDOC UUID',
        'data_type': 'string',
        'description': 'Unikátní identifikátor ISDOC dokumentu'
    }
}


def format_for_paperless(extracted_data: Dict[str, Any], doc_type: str) -> Dict[str, Any]:
    """
    Format extracted data for Paperless-NGX custom fields.

    NOTE: Call load_field_ids(api_url, token) once before using this function!

    Args:
        extracted_data: Output from data extractors
        doc_type: 'invoice', 'bank_statement', or 'receipt'

    Returns:
        Paperless-NGX custom fields array
    """
    custom_fields = []

    def _id(key: str) -> Optional[int]:
        return get_field_id(key)

    if doc_type == 'invoice':
        # Basic financial fields
        if 'summary' in extracted_data:
            summary = extracted_data['summary']
            custom_fields.extend([
                {'field': _id('amount_total'), 'value': str(summary.get('total_gross', 0))},
                {'field': _id('amount_vat'), 'value': str(summary.get('total_vat', 0))},
                {'field': _id('amount_net'), 'value': str(summary.get('total_net', 0))},
                {'field': _id('currency'), 'value': summary.get('currency', 'CZK')}
            ])

        # v1.1: Invoice subject (předmět faktury)
        if 'subject' in extracted_data and _id('invoice_subject'):
            custom_fields.append({'field': _id('invoice_subject'), 'value': extracted_data['subject']})

        # v1.1: Item type (služba/zboží)
        if 'item_type' in extracted_data and _id('item_type'):
            custom_fields.append({'field': _id('item_type'), 'value': extracted_data['item_type']})

        # v1.1: ISDOC metadata
        if 'isdoc' in extracted_data:
            isdoc = extracted_data['isdoc']
            if isdoc.get('is_isdoc') and _id('is_isdoc'):
                custom_fields.append({'field': _id('is_isdoc'), 'value': 'true'})
            if isdoc.get('version') and _id('isdoc_version'):
                custom_fields.append({'field': _id('isdoc_version'), 'value': isdoc['version']})
            if isdoc.get('uuid') and _id('isdoc_uuid'):
                custom_fields.append({'field': _id('isdoc_uuid'), 'value': isdoc['uuid']})

        # Structured data as JSON
        if 'line_items' in extracted_data:
            custom_fields.append({'field': _id('line_items'), 'value': json.dumps(extracted_data, ensure_ascii=False)})

    elif doc_type == 'bank_statement':
        if 'summary' in extracted_data:
            summary = extracted_data['summary']
            custom_fields.extend([
                {'field': _id('opening_balance'), 'value': str(summary.get('opening_balance', 0))},
                {'field': _id('closing_balance'), 'value': str(summary.get('closing_balance', 0))},
                {'field': _id('currency'), 'value': summary.get('currency', 'CZK')}
            ])
        if 'transactions' in extracted_data:
            custom_fields.append({'field': _id('transactions'), 'value': json.dumps(extracted_data, ensure_ascii=False)})

    elif doc_type == 'receipt':
        if 'summary' in extracted_data:
            summary = extracted_data['summary']
            custom_fields.extend([
                {'field': _id('amount_total'), 'value': str(summary.get('total', 0))},
                {'field': _id('currency'), 'value': summary.get('currency', 'CZK')}
            ])
        if 'eet' in extracted_data:
            eet = extracted_data['eet']
            if eet.get('fik'):
                custom_fields.append({'field': _id('eet_fik'), 'value': eet['fik']})
            if eet.get('bkp'):
                custom_fields.append({'field': _id('eet_bkp'), 'value': eet['bkp']})
        if 'items' in extracted_data:
            custom_fields.append({'field': _id('receipt_items'), 'value': json.dumps(extracted_data, ensure_ascii=False)})

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
