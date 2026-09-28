"""Question ingestion: parsing, normalization, source tracking (FE-001, FE-008)."""

from qme.ingestion.ingestor import IngestFailure, Ingestor, IngestResult, ingest_file
from qme.ingestion.normalizer import Normalizer
from qme.ingestion.parsers import detect_format, get_parser
from qme.ingestion.source_tracker import SourceTracker

__all__ = [
    "IngestFailure",
    "IngestResult",
    "Ingestor",
    "Normalizer",
    "SourceTracker",
    "detect_format",
    "get_parser",
    "ingest_file",
]
