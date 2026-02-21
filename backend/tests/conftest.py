import sys
from pathlib import Path
import pytest

# Ensure repository root is importable so `backend` package resolves in tests
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


FIXTURES = ROOT / "backend" / "tests" / "fixtures"


@pytest.fixture
def sample_pdf_file() -> Path:
    return FIXTURES / "sample.pdf"


@pytest.fixture
def sample_html_file() -> Path:
    return FIXTURES / "sample.html"


@pytest.fixture
def sample_docx_file() -> Path:
    return FIXTURES / "sample.docx"


@pytest.fixture
def sample_xlsx_file() -> Path:
    return FIXTURES / "sample.xlsx"
