from datetime import datetime, timezone

from mom.render_pdf import creation_date


def test_pdf_a_always_gets_a_creation_date_pdfx_can_read():
    line = creation_date(datetime(2026, 9, 27, 0, 30, tzinfo=timezone.utc))
    assert line.startswith("\\ifdefined\\pdfcreationdate\\else\\ifdefined\\creationdate\\let\\pdfcreationdate\\creationdate\\else")
    assert "D:20260927003000+00'00'" in line and line.endswith("\\fi\\fi")
