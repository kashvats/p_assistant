from __future__ import annotations

import hashlib
from html.parser import HTMLParser
from pathlib import Path
import re
from typing import Any


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts: list[str] = []

    def handle_data(self, data: str):
        if data.strip():
            self.text_parts.append(data.strip())

    def get_text(self) -> str:
        return " ".join(self.text_parts)


class DocumentExtractor:
    """Document parsing engine supporting Docling with documented native fallback for text, HTML, and PDF."""

    DATE_PATTERNS = [
        re.compile(r"\b(20\d{2}[-/](?:0[1-9]|1[0-2])[-/](?:0[1-9]|[12]\d|3[01]))\b"),  # YYYY-MM-DD
        re.compile(r"\b((?:0[1-9]|[12]\d|3[01])[-/](?:0[1-9]|1[0-2])[-/](?:20\d{2}))\b"),  # DD-MM-YYYY
        re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+20\d{2}\b", re.IGNORECASE),
    ]

    TOTAL_PATTERNS = [
        re.compile(r"(?:grand\s+total|total\s+amount|amount\s+due|balance\s+due|\btotal\b)\s*[:=]?\s*([$€£¥])?\s*([\d,]+\.\d{2})", re.IGNORECASE),
        re.compile(r"([$€£¥])\s*([\d,]+\.\d{2})"),
        re.compile(r"\b([\d,]+\.\d{2})\s*(?:USD|EUR|GBP|CAD|AUD)\b", re.IGNORECASE),
    ]

    SUBTOTAL_PATTERNS = [
        re.compile(r"(?:subtotal|sub-total|sub\s+total|net\s+amount)\s*[:=]?\s*([$€£¥])?\s*([\d,]+\.\d{2})", re.IGNORECASE),
    ]

    TAX_PATTERNS = [
        re.compile(r"(?:sales\s+tax|tax|vat|gst)\s*[:=]?\s*([$€£¥])?\s*([\d,]+\.\d{2})", re.IGNORECASE),
    ]

    INVOICE_NUM_PATTERNS = [
        re.compile(r"(?:invoice\s*(?:#|no|number|num)?)\s*[:=]?\s*([A-Za-z0-9-_]{3,30})", re.IGNORECASE),
    ]

    VENDOR_PATTERNS = [
        re.compile(r"(?:from|vendor|biller|supplier|company)\s*[:=]?\s*([A-Za-z0-9 &.,'-]{2,50})", re.IGNORECASE),
    ]

    @staticmethod
    def sanitize_for_path(value: str | None, default: str = "Unknown") -> str:
        """Sanitize an extracted string for safe cross-platform folder/path usage."""
        if not value or not str(value).strip():
            return default
        clean = re.sub(r'[\/\\:*?"<>|]', "_", str(value).strip())
        clean = re.sub(r"\s+", " ", clean).strip(". ")
        return clean[:50] or default

    @classmethod
    def extract_text(cls, file_path: Path) -> str:
        """Extract text from file. Tries Docling first for binary/rich formats; falls back to native parsers."""
        suffix = file_path.suffix.lower()

        # Plain text formats do not require heavy document conversion
        if suffix in {".txt", ".text", ".md", ".log", ".csv", ".tsv", ".json"}:
            try:
                return file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return file_path.read_bytes().decode("utf-8", errors="ignore")

        # 1. Attempt Docling integration for rich document types (PDF, DOCX, etc.)
        try:
            from docling.document_converter import DocumentConverter
            converter = DocumentConverter()
            res = converter.convert(str(file_path))
            text = res.document.export_to_markdown()
            if text and text.strip():
                return text
        except Exception:
            # Documented fallback: native format-specific parsers
            pass

        # PDF extraction fallback
        if suffix == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(str(file_path))
                pages = [page.extract_text() or "" for page in reader.pages]
                return "\n".join(pages)
            except Exception as exc:
                try:
                    return file_path.read_bytes().decode("latin1", errors="ignore")[:20000]
                except Exception:
                    return f"[Error reading PDF: {exc}]"

        # HTML extraction using Trafilatura with parser fallback
        if suffix in {".html", ".htm"}:
            raw = file_path.read_text(encoding="utf-8", errors="replace")
            try:
                import trafilatura
                clean_text = trafilatura.extract(raw)
                if clean_text and clean_text.strip():
                    return clean_text
            except Exception:
                pass
            parser = _HTMLTextExtractor()
            parser.feed(raw)
            return parser.get_text()

        # Plain text, CSV, markdown, etc.
        try:
            return file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return file_path.read_bytes().decode("utf-8", errors="ignore")

    @classmethod
    def extract_invoice_fields(cls, file_path: Path) -> dict[str, Any]:
        """Extract structured invoice fields: vendor, date, subtotal, tax, total, currency, invoice_number.

        Returns validation breakdown, ambiguity flags, review reasons, and sanitized path values.
        """
        if not file_path or not file_path.is_file():
            return {
                "ok": False,
                "error": f"Target path '{file_path}' is not a regular file.",
                "source_reference": str(file_path) if file_path else "",
                "source_text_snippet": "",
                "vendor": "Unknown",
                "vendor_clean": "Unknown",
                "date": None,
                "year_month": "unknown-date",
                "subtotal": None,
                "tax": None,
                "total": None,
                "amount": None,
                "currency": "USD",
                "invoice_number": None,
                "missing_or_ambiguous": ["File does not exist or is a directory"],
                "needs_review": True,
                "review_reasons": ["File does not exist or is a directory"],
                "validation_results": {"file_accessible": False},
            }

        # Check disk cache by file content hash
        file_sha256 = None
        cache = None
        try:
            from living_assistant.system.disk_cache import get_disk_cache
            cache = get_disk_cache()
            file_sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()
            cached_res = cache.get("doc_parsing", f"invoice:{file_sha256}")
            if cached_res is not None and isinstance(cached_res, dict):
                return dict(cached_res)
        except Exception:
            cache = None

        text = cls.extract_text(file_path)
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        vendor = None
        date_str = None
        subtotal = None
        tax = None
        total = None
        currency = None
        invoice_number = None
        missing_or_ambiguous: list[str] = []
        review_reasons: list[str] = []

        # 1. Invoice Number
        for pat in cls.INVOICE_NUM_PATTERNS:
            m = pat.search(text)
            if m:
                invoice_number = m.group(1).strip()
                break
        if not invoice_number:
            missing_or_ambiguous.append("Missing invoice number")

        # 2. Date
        for pat in cls.DATE_PATTERNS:
            m = pat.search(text)
            if m:
                date_str = m.group(0).strip()
                break
        if not date_str:
            missing_or_ambiguous.append("Missing or unparseable invoice date")
            review_reasons.append("Could not determine invoice date")

        # 3. Subtotal & Tax
        for pat in cls.SUBTOTAL_PATTERNS:
            m = pat.search(text)
            if m:
                groups = m.groups()
                curr_sym = groups[0]
                val = groups[1]
                if curr_sym and not currency:
                    currency = curr_sym
                subtotal = float(val.replace(",", ""))
                break

        for pat in cls.TAX_PATTERNS:
            m = pat.search(text)
            if m:
                groups = m.groups()
                curr_sym = groups[0]
                val = groups[1]
                if curr_sym and not currency:
                    currency = curr_sym
                tax = float(val.replace(",", ""))
                break

        # 4. Total Amount
        for pat in cls.TOTAL_PATTERNS:
            m = pat.search(text)
            if m:
                groups = m.groups()
                if len(groups) == 2:
                    curr_sym, val = groups
                    if curr_sym and not currency:
                        currency = curr_sym
                    total = float(val.replace(",", ""))
                elif len(groups) == 1:
                    total = float(groups[0].replace(",", ""))
                break

        if total is None and subtotal is not None and tax is not None:
            total = round(subtotal + tax, 2)
        elif total is None:
            missing_or_ambiguous.append("Missing total amount")
            review_reasons.append("Could not extract total amount")

        # 5. Currency
        if not currency:
            if "$" in text:
                currency = "$"
            elif "€" in text or "EUR" in text:
                currency = "€"
            elif "£" in text or "GBP" in text:
                currency = "£"
            elif "¥" in text or "JPY" in text:
                currency = "¥"
            else:
                currency = "USD"
                missing_or_ambiguous.append("Defaulted currency to USD (not explicitly specified)")

        # 6. Vendor
        for pat in cls.VENDOR_PATTERNS:
            m = pat.search(text)
            if m:
                vendor = m.group(1).strip()
                break

        if not vendor and lines:
            for l in lines[:4]:
                if not any(k in l.lower() for k in ["invoice", "receipt", "bill to", "date", "total", "amount"]):
                    vendor = l[:40].strip()
                    break

        if not vendor:
            vendor = "Unknown Vendor"
            missing_or_ambiguous.append("Missing vendor name")
            review_reasons.append("Could not extract vendor name")

        # 7. Year-Month calculation
        year_month = "unknown-date"
        if date_str:
            ym_match = re.search(r"\b(20\d{2})[-/](0[1-9]|1[0-2])\b", date_str)
            if ym_match:
                year_month = f"{ym_match.group(1)}-{ym_match.group(2)}"
            else:
                y_match = re.search(r"\b(20\d{2})\b", date_str)
                if y_match:
                    year_month = y_match.group(1)

        # 8. Validation checks
        math_valid = None
        if subtotal is not None and tax is not None and total is not None:
            expected = round(subtotal + tax, 2)
            math_valid = abs(expected - total) <= 0.05
            if not math_valid:
                missing_or_ambiguous.append(f"Subtotal ({subtotal}) + Tax ({tax}) does not equal Total ({total})")
                review_reasons.append("Total does not match subtotal + tax")

        vendor_clean = cls.sanitize_for_path(vendor, default="Unknown_Vendor")
        year_month_clean = cls.sanitize_for_path(year_month, default="unknown-date")

        needs_review = bool(review_reasons) or math_valid is False

        validation_results = {
            "vendor_extracted": vendor != "Unknown Vendor",
            "date_extracted": date_str is not None,
            "total_extracted": total is not None,
            "subtotal_extracted": subtotal is not None,
            "tax_extracted": tax is not None,
            "math_verified": math_valid,
            "all_required_present": vendor != "Unknown Vendor" and date_str is not None and total is not None,
        }

        score = 0.0
        if vendor and vendor != "Unknown Vendor":
            score += 0.35
        if date_str:
            score += 0.30
        if total is not None:
            score += 0.25
        if invoice_number:
            score += 0.10
        confidence = round(score, 2)

        res = {
            "ok": True,
            "source_reference": file_path.name,
            "source_text_snippet": text[:300].strip(),
            "vendor": vendor,
            "vendor_clean": vendor_clean,
            "date": date_str,
            "year_month": year_month_clean,
            "subtotal": subtotal,
            "tax": tax,
            "total": total,
            "amount": total,  # Backward compatibility alias
            "currency": currency,
            "invoice_number": invoice_number,
            "confidence": confidence,
            "missing_or_ambiguous": missing_or_ambiguous,
            "needs_review": needs_review,
            "review_reasons": review_reasons,
            "validation_results": validation_results,
        }

        if cache is not None and file_sha256 is not None:
            try:
                cache.set("doc_parsing", f"invoice:{file_sha256}", res)
            except Exception:
                pass

        return res

