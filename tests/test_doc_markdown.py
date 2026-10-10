"""Every uploaded file becomes Markdown the model reads well: tables and headings kept, cached, read by section."""
from __future__ import annotations

import io
import zipfile

import pytest

from living_assistant.core import chat_files, doc_markdown


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_files, "data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(doc_markdown, "data_dir", lambda: tmp_path / "data")
    from living_assistant.vision import attachments
    monkeypatch.setattr(attachments, "data_dir", lambda: tmp_path / "data")


def _zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()


def test_word_keeps_headings_lists_and_tables(tmp_path):
    xml = ('<w:document><w:body>'
           '<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr><w:r><w:t>Quarterly report</w:t></w:r></w:p>'
           '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Results</w:t></w:r></w:p>'
           '<w:p><w:pPr><w:numPr/></w:pPr><w:r><w:t>Revenue grew</w:t></w:r></w:p>'
           '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Model</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Accuracy</w:t></w:r></w:p></w:tc></w:tr>'
           '<w:tr><w:tc><w:p><w:r><w:t>Q4</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>71.2</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
           '</w:body></w:document>')
    saved = chat_files.save(_zip({"word/document.xml": xml}), "report.docx")
    md = chat_files.describe(*chat_files.resolve(saved["id"]))
    assert md["format"] == "markdown"
    assert "# Quarterly report" in md["text"] and "## Results" in md["text"] and "- Revenue grew" in md["text"]
    assert "| Model | Accuracy |" in md["text"] and "| Q4 | 71.2 |" in md["text"]


def test_slides_become_sections_with_notes(tmp_path):
    slide = '<p:sld><a:p><a:r><a:t>Roadmap</a:t></a:r></a:p><a:p><a:r><a:t>Ship v2</a:t></a:r></a:p></p:sld>'
    notes = '<p:notes><a:p><a:r><a:t>Mention the delay</a:t></a:r></a:p></p:notes>'
    path = tmp_path / "deck.pptx"
    path.write_bytes(_zip({"ppt/slides/slide1.xml": slide, "ppt/notesSlides/notesSlide1.xml": notes}))
    md, how = doc_markdown.to_markdown(path)
    assert "## Slide 1: Roadmap" in md and "- Ship v2" in md and "Mention the delay" in md


def test_spreadsheets_are_summarised_per_sheet(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.title = "cities"
    wb.active.append(["city", "population"])
    wb.active.append(["Pune", 7])
    wb.active.append(["Delhi", 32])
    wb.create_sheet("empty")
    path = tmp_path / "data.xlsx"
    wb.save(path)
    md, how = doc_markdown.to_markdown(path)
    assert how == "markdown summary" and "## cities" in md and "2 rows x 2 columns" in md
    assert "| city | population |" in md and "| Pune | 7 |" in md and "**Numeric summary**" in md


def test_html_tables_and_headings_survive_and_papers_are_read_by_section():
    html = ("<article><h2>Abstract</h2><p>We quantize.</p><h2>1 Introduction</h2><p>" + "Intro text. " * 400 + "</p>"
            "<h2>4 Experiments</h2><table><caption>Table 2: results</caption><tr><th>Model</th><th>Acc</th></tr>"
            "<tr><td>Q4</td><td>71.2</td></tr></table><h2>5 Limitations</h2><p>Only one GPU.</p>"
            "<h2>References</h2><p>[1] Someone. " + "ref " * 500 + "</p><script>alert(1)</script></article>")
    md = doc_markdown.html_to_markdown(html)
    assert "## 4 Experiments" in md and "| Model | Acc |" in md and "| Q4 | 71.2 |" in md and "alert" not in md
    focused = doc_markdown.focused(md, limit=1500)
    assert "| Q4 | 71.2 |" in focused and "Only one GPU" in focused and "We quantize" in focused
    assert "ref ref" not in focused and len(focused) < 1700


def test_pdf_reads_fast_now_and_as_markdown_once_converted(tmp_path):
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Results: the model reaches 71.2 percent accuracy.")
    path = tmp_path / "paper.pdf"
    path.write_bytes(doc.tobytes())
    first, how = doc_markdown.to_markdown(path)  # not converted yet: fast text, conversion queued
    assert "71.2" in first
    converted = doc_markdown.convert_pdf(path)
    assert "71.2" in converted and doc_markdown.cached(path) == converted
    again, how = doc_markdown.to_markdown(path)
    assert how.startswith("markdown") and again == converted
