#!/usr/bin/env python3
"""Compile the frontend and backend documentation into two Arabic PDF books."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageBreak,
    PageTemplate,
    Spacer,
)
from reportlab.platypus.tableofcontents import TableOfContents

from generate_pdfs import (
    FRONTEND_DOC_DIR,
    OUTPUT_DIR,
    PAGE_MARGIN,
    ROOT,
    TOCParagraph,
    add_page_number,
    make_paragraph,
    make_styles,
    render_markdown,
    setup_fonts,
    shape_arabic,
)


BOOK_DIR = OUTPUT_DIR / "الكتب"
FRONTEND_OUTPUT = BOOK_DIR / "AURA-Sepsis-CDSS_كتاب_الواجهة_الأمامية_المهندس_أحمد_ديب.pdf"
BACKEND_OUTPUT = BOOK_DIR / "AURA-Sepsis-CDSS_كتاب_الواجهة_الخلفية_المهندس_أحمد_ديب.pdf"
PROJECT_NAME = "AURA-Sepsis-CDSS"
ENGINEER_NAME = "المهندس أحمد ديب"
class CoverPage(Flowable):
    def __init__(self, book_title: str, subtitle: str, file_count: int, edition: str):
        super().__init__()
        self.book_title = book_title
        self.subtitle = subtitle
        self.file_count = file_count
        self.edition = edition

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        self.width = avail_width
        self.height = avail_height
        return avail_width, avail_height

    def draw(self) -> None:
        canvas = self.canv
        width, height = self.width, self.height
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#f3f7fa"))
        canvas.roundRect(0, 0, width, height, 16, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor("#123b55"))
        canvas.roundRect(0, height * 0.64, width, height * 0.36, 16, stroke=0, fill=1)
        canvas.rect(0, height * 0.64, width, 15, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor("#21a58b"))
        canvas.roundRect(width - 48, height * 0.60, 12, height * 0.37, 5, stroke=0, fill=1)

        self._center_text(canvas, PROJECT_NAME, width / 2, height * 0.91, 17, "#d7e9ef", "ArabicBold")
        self._center_text(canvas, self.book_title, width / 2, height * 0.78, 27, "#ffffff", "ArabicBold")
        self._center_text(canvas, self.subtitle, width / 2, height * 0.70, 12, "#e1edf0", "ArabicFont")

        canvas.setStrokeColor(colors.HexColor("#c7d6de"))
        canvas.setLineWidth(1)
        canvas.line(width * 0.20, height * 0.54, width * 0.80, height * 0.54)
        self._center_text(canvas, "إعداد", width / 2, height * 0.47, 11, "#627785", "ArabicFont")
        self._center_text(canvas, ENGINEER_NAME, width / 2, height * 0.41, 18, "#163f58", "ArabicBold")
        self._center_text(
            canvas,
            f"عدد ملفات التوثيق: {self.file_count}",
            width / 2,
            height * 0.31,
            11,
            "#526875",
            "ArabicFont",
        )
        self._center_text(
            canvas,
            f"{self.edition}  |  {date.today().year}",
            width / 2,
            height * 0.26,
            10,
            "#70818b",
            "ArabicFont",
        )
        self._center_text(
            canvas,
            "مرجع تقني توثيقي — لا يعد بديلاً عن التحقق من المصدر أو المراجعة الطبية المختصة",
            width / 2,
            height * 0.10,
            8,
            "#70818b",
            "ArabicFont",
        )
        canvas.restoreState()

    @staticmethod
    def _center_text(canvas, value: str, x: float, y: float, size: int, color: str, font: str):
        canvas.setFont(font, size)
        canvas.setFillColor(colors.HexColor(color))
        canvas.drawCentredString(x, y, shape_arabic(value))


class BookDocTemplate(BaseDocTemplate):
    def __init__(self, filename: Path, styles: dict[str, ParagraphStyle], book_title: str):
        super().__init__(
            str(filename),
            pagesize=A4,
            rightMargin=PAGE_MARGIN,
            leftMargin=PAGE_MARGIN,
            topMargin=PAGE_MARGIN + 12,
            bottomMargin=PAGE_MARGIN,
            title=f"{PROJECT_NAME} — {book_title}",
            author=ENGINEER_NAME,
            subject="توثيق تقني باللغة العربية للمشروع",
            creator="AURA-Sepsis-CDSS documentation tools",
            pageCompression=1,
        )
        self.book_title = book_title
        self._body_frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="body",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        self.addPageTemplates([
            PageTemplate(id="main", frames=[self._body_frame], onPage=self._draw_page)
        ])

    def _draw_page(self, canvas, document):
        if document.page == 1:
            return
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#d9e2e8"))
        canvas.setLineWidth(0.5)
        canvas.line(
            self.leftMargin,
            A4[1] - self.topMargin + 3,
            A4[0] - self.rightMargin,
            A4[1] - self.topMargin + 3,
        )
        canvas.setFont("ArabicFont", 8)
        canvas.setFillColor(colors.HexColor("#637782"))
        header = shape_arabic(f"{PROJECT_NAME}  |  {self.book_title}")
        canvas.drawRightString(A4[0] - self.rightMargin, A4[1] - self.topMargin + 8, header)
        canvas.restoreState()
        add_page_number(canvas, document)

    def afterFlowable(self, flowable: Flowable) -> None:
        level = getattr(flowable, "toc_level", None)
        if level is None:
            return
        key = f"book-{id(flowable)}"
        label = getattr(flowable, "toc_text", None) or flowable.getPlainText()
        self.canv.bookmarkPage(key)
        self.notify("TOCEntry", (level, label, self.page, key))
        if level == 0:
            self.canv.addOutlineEntry(label, key, level=0, closed=False)


def toc_flowable() -> TableOfContents:
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            "TocChapter",
            fontName="ArabicBold",
            fontSize=11,
            leading=16,
            alignment=TA_RIGHT,
            rightIndent=0,
            leftIndent=2,
            spaceBefore=5,
            spaceAfter=3,
            textColor=colors.HexColor("#153f58"),
        ),
        ParagraphStyle(
            "TocSection",
            fontName="ArabicFont",
            fontSize=9,
            leading=13,
            alignment=TA_RIGHT,
            rightIndent=12,
            leftIndent=2,
            spaceAfter=2,
            textColor=colors.HexColor("#315667"),
        ),
        ParagraphStyle(
            "TocSubsection",
            fontName="ArabicFont",
            fontSize=8,
            leading=11,
            alignment=TA_RIGHT,
            rightIndent=24,
            leftIndent=2,
            spaceAfter=1,
            textColor=colors.HexColor("#566873"),
        ),
        ParagraphStyle(
            "TocMinor",
            fontName="ArabicFont",
            fontSize=7.5,
            leading=10,
            alignment=TA_RIGHT,
            rightIndent=36,
            leftIndent=2,
            spaceAfter=1,
            textColor=colors.HexColor("#65757e"),
        ),
    ]
    return toc


def doc_paths() -> tuple[list[Path], list[Path]]:
    frontend_docs = sorted(
        (
            path for path in FRONTEND_DOC_DIR.rglob("*.md")
            if path.name != "package-lock_json_doc.md"
            and "dist" not in path.relative_to(FRONTEND_DOC_DIR).parts
        ),
        key=lambda path: path.relative_to(FRONTEND_DOC_DIR).as_posix().lower(),
    )

    source_dir = ROOT / "شرح"
    backend_docs = {
        source_dir / "README_md_doc.md",
        source_dir / "requirements_txt_doc.md",
    }
    for folder in ("backend", "tests", "docs"):
        directory = source_dir / folder
        if directory.exists():
            backend_docs.update(
                path for path in directory.rglob("*.md")
                if (
                    "dist" not in path.parts
                    and "PDF" not in path.parts
                    and path.name != "PROJECT_FILES_txt_doc.md"
                )
            )
    backend_docs.add(
        source_dir
        / "الدوال_الرياضية_والاحتمالات_والتوقعات"
        / "الدوال_والاحتمالات_والتوقعات.md"
    )
    normalized_backend = sorted(
        (path for path in backend_docs if path.is_file()),
        key=lambda path: path.relative_to(source_dir).as_posix().lower(),
    )
    if not frontend_docs or not normalized_backend:
        raise FileNotFoundError("Frontend or backend Markdown documentation was not found.")
    return frontend_docs, normalized_backend


def source_label(source: Path, *, frontend: bool) -> str:
    root = FRONTEND_DOC_DIR if frontend else ROOT / "شرح"
    relative = source.relative_to(root).as_posix()
    if relative == "README.md":
        return "دليل الواجهة الأمامية"
    if relative == "README_md_doc.md":
        return "دليل المشروع العام"
    if relative == "requirements_txt_doc.md":
        return "متطلبات Python العامة"
    if relative.endswith("_doc.md"):
        return relative[: -len("_doc.md")].replace("_", ".")
    return relative.removesuffix(".md")


def make_book(
    *,
    sources: list[Path],
    output: Path,
    book_title: str,
    subtitle: str,
    frontend: bool,
    edition: str,
) -> None:
    styles = make_styles()
    output.parent.mkdir(parents=True, exist_ok=True)
    document = BookDocTemplate(output, styles, book_title)
    toc = toc_flowable()
    story: list[Any] = [
        CoverPage(book_title, subtitle, len(sources), edition),
        PageBreak(),
        make_paragraph("بيانات الكتاب", styles["h1"]),
        make_paragraph(f"اسم المشروع: `{PROJECT_NAME}`", styles["body"]),
        make_paragraph(f"عنوان الكتاب: {book_title}", styles["body"]),
        make_paragraph(f"إعداد: {ENGINEER_NAME}", styles["body"]),
        make_paragraph(f"الإصدار: {edition} — {date.today().year}", styles["body"]),
        make_paragraph(f"عدد ملفات الشرح المجمعة: {len(sources)}", styles["body"]),
        make_paragraph(
            "هذا الكتاب يجمع صفحات التوثيق المتاحة في ملف واحد، ويحافظ على "
            "الشيفرة والأمثلة كما وردت في صفحات الشرح. أرقام الصفحات والروابط "
            "داخل الفهرس تشير إلى مواضعها في هذا الكتاب.",
            styles["body"],
        ),
        make_paragraph(
            "تنبيه طبي: المشروع نموذج دعم قرار بحثي. درجاته غير معايرة سريرياً، "
            "ولا تمثل تشخيصاً أو توصية علاجية؛ يجب الرجوع إلى المختصين والبروتوكول المحلي.",
            styles["quote"],
        ),
        PageBreak(),
        make_paragraph("الفهرس", styles["h1"]),
        toc,
        PageBreak(),
    ]

    for chapter_index, source in enumerate(sources, start=1):
        label = source_label(source, frontend=frontend)
        chapter_label = f"الفصل {chapter_index}: {label}"
        chapter_heading = TOCParagraph(
            shape_arabic(chapter_label),
            styles["h1"],
            toc_level=0,
            toc_text=shape_arabic(chapter_label),
        )
        story.extend([
            chapter_heading,
            Spacer(1, 5),
            *render_markdown(source, styles),
        ])
        if chapter_index < len(sources):
            story.append(PageBreak())

    document.multiBuild(story, maxPasses=10)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--book",
        choices=("all", "frontend", "backend"),
        default="all",
        help="Choose which book(s) to create.",
    )
    args = parser.parse_args()
    setup_fonts()
    frontend_docs, backend_docs = doc_paths()

    books = []
    if args.book in {"all", "frontend"}:
        books.append((
            frontend_docs,
            FRONTEND_OUTPUT,
            "كتاب الواجهة الأمامية",
            "شرح مكونات React والتنسيقات وإعدادات الواجهة",
            True,
        ))
    if args.book in {"all", "backend"}:
        books.append((
            backend_docs,
            BACKEND_OUTPUT,
            "كتاب الواجهة الخلفية",
            "شرح الخادم والبيانات والنماذج والاختبارات",
            False,
        ))

    for sources, output, title, subtitle, frontend in books:
        edition = "الطبعة التوثيقية الأولى"
        make_book(
            sources=sources,
            output=output,
            book_title=title,
            subtitle=subtitle,
            frontend=frontend,
            edition=edition,
        )
        print(
            f"Generated {'frontend' if frontend else 'backend'} book "
            f"({len(sources)} documents)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
