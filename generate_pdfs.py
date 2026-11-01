#!/usr/bin/env python3
"""Convert the Arabic Markdown documentation tree to readable PDF files."""

from __future__ import annotations

import html
import argparse
import re
import textwrap
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "شرح"
OUTPUT_DIR = SOURCE_DIR / "PDF"
FRONTEND_DOC_DIR = SOURCE_DIR / "frontend"
FRONTEND_OUTPUT_DIR = OUTPUT_DIR / "الواجهة الأمامية"
FONT_PATHS = (
    Path(r"C:\Windows\Fonts\tahoma.ttf"),
    Path(r"C:\Windows\Fonts\arial.ttf"),
)
FONT_BOLD_PATHS = (
    Path(r"C:\Windows\Fonts\tahomabd.ttf"),
    Path(r"C:\Windows\Fonts\arialbd.ttf"),
)
PAGE_SIZE = A4
PAGE_MARGIN = 1.65 * 28.3465
CODE_FENCE = re.compile(r"^\s*(```+|~~~+)(.*)$")
TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
INLINE_TOKEN = re.compile(
    r"(\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*|\*([^*]+)\*)"
)
ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")


def shape_arabic(text: str, base_direction: str = "R") -> str:
    if not ARABIC_RE.search(text):
        return text
    return get_display(arabic_reshaper.reshape(text), base_dir=base_direction)


def escape_paragraph_text(text: str) -> str:
    return html.escape(text, quote=False).replace("\n", "<br/>")


def parse_inline(text: str) -> str:
    parts: list[str] = []
    cursor = 0
    for match in INLINE_TOKEN.finditer(text):
        parts.append(escape_paragraph_text(shape_arabic(text[cursor : match.start()])))
        if match.group(2) is not None:
            label = shape_arabic(match.group(2))
            target = match.group(3)
            parts.append(
                f'<font color="#176b87"><u>{escape_paragraph_text(label)}</u></font>'
                f' <font size="7" color="#687581">({html.escape(target)})</font>'
            )
        elif match.group(4) is not None:
            parts.append(
                f'<font name="CodeFont" color="#7a2d55">'
                f'{html.escape(match.group(4))}</font>'
            )
        elif match.group(5) is not None:
            parts.append(
                f"<b>{escape_paragraph_text(shape_arabic(match.group(5)))}</b>"
            )
        else:
            parts.append(
                f"<i>{escape_paragraph_text(shape_arabic(match.group(6)))}</i>"
            )
        cursor = match.end()
    parts.append(escape_paragraph_text(shape_arabic(text[cursor:])))
    return "".join(parts)


def parse_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "body": ParagraphStyle(
            "ArabicBody",
            parent=base["BodyText"],
            fontName="ArabicFont",
            fontSize=9.5,
            leading=15,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#202b36"),
            spaceAfter=6,
            wordWrap="CJK",
        ),
        "h1": ParagraphStyle(
            "ArabicH1",
            parent=base["Heading1"],
            fontName="ArabicBold",
            fontSize=19,
            leading=25,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#123b55"),
            spaceBefore=9,
            spaceAfter=12,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "ArabicH2",
            parent=base["Heading2"],
            fontName="ArabicBold",
            fontSize=14,
            leading=20,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#176b87"),
            spaceBefore=11,
            spaceAfter=7,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "ArabicH3",
            parent=base["Heading3"],
            fontName="ArabicBold",
            fontSize=11,
            leading=16,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#385c70"),
            spaceBefore=8,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "bullet": ParagraphStyle(
            "ArabicBullet",
            parent=base["BodyText"],
            fontName="ArabicFont",
            fontSize=9.2,
            leading=14,
            alignment=TA_RIGHT,
            rightIndent=12,
            firstLineIndent=0,
            spaceAfter=3,
            wordWrap="CJK",
        ),
        "table": ParagraphStyle(
            "ArabicTable",
            parent=base["BodyText"],
            fontName="ArabicFont",
            fontSize=8,
            leading=11,
            alignment=TA_RIGHT,
            wordWrap="CJK",
        ),
        "code": ParagraphStyle(
            "ArabicCode",
            parent=base["Code"],
            fontName="CodeFont",
            fontSize=6.3,
            leading=8,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#243344"),
            backColor=colors.HexColor("#f2f5f8"),
            borderColor=colors.HexColor("#d9e1e8"),
            borderWidth=0.35,
            borderPadding=3,
            leftIndent=5,
            rightIndent=5,
            spaceBefore=1,
            spaceAfter=1,
            splitLongWords=True,
            wordWrap="CJK",
        ),
        "quote": ParagraphStyle(
            "ArabicQuote",
            parent=base["BodyText"],
            fontName="ArabicFont",
            fontSize=9,
            leading=14,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#435363"),
            backColor=colors.HexColor("#f1f6f7"),
            borderColor=colors.HexColor("#66a3a8"),
            borderWidth=1,
            borderPadding=7,
            rightIndent=6,
            leftIndent=6,
            spaceBefore=4,
            spaceAfter=7,
            wordWrap="CJK",
        ),
    }


class TOCParagraph(Paragraph):
    """A heading paragraph that can also appear in the compiled book contents."""

    def __init__(
        self,
        text: str,
        style: ParagraphStyle,
        *,
        toc_level: int | None = None,
        toc_text: str | None = None,
    ) -> None:
        super().__init__(text, style)
        self.toc_level = toc_level
        self.toc_text = toc_text


def make_paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    safe = parse_inline(text.strip())
    if style.name in {"ArabicH1", "ArabicH2", "ArabicH3"}:
        level = {"ArabicH1": 1, "ArabicH2": 2, "ArabicH3": 3}[style.name]
        return TOCParagraph(
            safe if safe else "&#160;",
            style,
            toc_level=level,
            toc_text=shape_arabic(text.strip()),
        )
    return Paragraph(safe if safe else "&#160;", style)


def make_code_block(lines: list[str], code_style: ParagraphStyle) -> list[Preformatted]:
    shaped_lines = []
    max_chars = 140
    for line in lines:
        display_line = shape_arabic(line.expandtabs(4), base_direction="L")
        wrapped = textwrap.wrap(
            display_line,
            width=max_chars,
            break_long_words=True,
            break_on_hyphens=False,
            replace_whitespace=False,
            drop_whitespace=False,
        ) or [""]
        shaped_lines.extend(wrapped)
    escaped = "\n".join(html.escape(line, quote=False) for line in shaped_lines)
    return [Preformatted(escaped, code_style, maxLineLength=max_chars)]


def render_markdown(path: Path, styles: dict[str, ParagraphStyle]) -> list:
    lines = path.read_text(encoding="utf-8").splitlines()
    story: list = []
    index = 0
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            joined = " ".join(part.strip() for part in paragraph_lines).strip()
            if joined:
                is_quote = joined.startswith("> ")
                if is_quote:
                    joined = joined[2:].strip()
                story.append(make_paragraph(joined, styles["quote" if is_quote else "body"]))
            paragraph_lines.clear()

    while index < len(lines):
        line = lines[index]
        fence_match = CODE_FENCE.match(line)
        if fence_match:
            flush_paragraph()
            marker = fence_match.group(1)
            index += 1
            code_lines = []
            while index < len(lines) and not lines[index].strip().startswith(marker):
                code_lines.append(lines[index])
                index += 1
            story.extend(make_code_block(code_lines, styles["code"]))
            index += 1
            story.append(Spacer(1, 4))
            continue

        if line.strip().startswith("|") and index + 1 < len(lines) and TABLE_SEPARATOR.match(lines[index + 1]):
            flush_paragraph()
            raw_rows = [parse_table_row(line)]
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                raw_rows.append(parse_table_row(lines[index]))
                index += 1
            column_count = max(len(row) for row in raw_rows)
            table_data = []
            for row_number, row in enumerate(raw_rows):
                normalized = row + [""] * (column_count - len(row))
                cell_style = ParagraphStyle(
                    f"TableCell{row_number}",
                    parent=styles["table"],
                    fontName="ArabicBold" if row_number == 0 else "ArabicFont",
                    textColor=colors.white if row_number == 0 else colors.HexColor("#263746"),
                )
                table_data.append([
                    make_paragraph(cell, cell_style)
                    for cell in reversed(normalized)
                ])
            widths = [None] * column_count
            table = Table(
                table_data,
                colWidths=widths,
                repeatRows=1,
                hAlign="RIGHT",
                splitByRow=1,
            )
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#176b87")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                    colors.white,
                    colors.HexColor("#f4f7f9"),
                ]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d5dfe5")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.extend([table, Spacer(1, 6)])
            continue

        if line.strip() == "---" or line.strip() == "***":
            flush_paragraph()
            story.extend([Spacer(1, 3), HRFlowable(
                width="100%",
                thickness=0.6,
                color=colors.HexColor("#c9d5dc"),
                spaceBefore=3,
                spaceAfter=7,
            )])
            index += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            style = styles["h1"] if level == 1 else styles["h2"] if level == 2 else styles["h3"]
            story.append(make_paragraph(heading.group(2), style))
            index += 1
            continue

        bullet = re.match(r"^\s*[-*+]\s+(.*)$", line)
        numbered = re.match(r"^\s*\d+[.)]\s+(.*)$", line)
        if bullet or numbered:
            flush_paragraph()
            content = (bullet or numbered).group(1)
            prefix = "• " if bullet else f"{numbered.group(0).strip().split('.')[0]}. "
            story.append(make_paragraph(prefix + content, styles["bullet"]))
            index += 1
            continue

        if line.lstrip().startswith(">"):
            flush_paragraph()
            quoted = line.lstrip()[1:].strip()
            story.append(make_paragraph(quoted, styles["quote"]))
            index += 1
            continue

        if not line.strip():
            flush_paragraph()
            index += 1
            continue

        if line.strip() in {"\\[", "\\]", "$$"}:
            flush_paragraph()
            math_lines = []
            index += 1
            while index < len(lines) and lines[index].strip() not in {"\\]", "\\[", "$$"}:
                math_lines.append(lines[index])
                index += 1
            story.extend(make_code_block(math_lines, styles["code"]))
            story.append(Spacer(1, 4))
            if index < len(lines):
                index += 1
            continue

        paragraph_lines.append(line)
        index += 1

    flush_paragraph()
    return story


def add_page_number(canvas, document) -> None:
    canvas.saveState()
    width, _ = PAGE_SIZE
    canvas.setFont("ArabicFont", 8)
    label = shape_arabic(f"صفحة {document.page}", base_direction="R")
    canvas.setFillColor(colors.HexColor("#71808b"))
    canvas.drawRightString(width - PAGE_MARGIN, 0.85 * 28.3465, label)
    canvas.restoreState()


def setup_fonts() -> None:
    regular = next((path for path in FONT_PATHS if path.is_file()), None)
    bold = next((path for path in FONT_BOLD_PATHS if path.is_file()), None)
    if regular is None or bold is None:
        raise FileNotFoundError(
            "Arabic-capable Tahoma or Arial fonts were not found in C:\\Windows\\Fonts."
        )
    pdfmetrics.registerFont(TTFont("ArabicFont", str(regular)))
    pdfmetrics.registerFont(TTFont("ArabicBold", str(bold)))
    pdfmetrics.registerFont(TTFont("CodeFont", str(regular)))
    pdfmetrics.registerFontFamily(
        "ArabicFont",
        normal="ArabicFont",
        bold="ArabicBold",
        italic="ArabicFont",
        boldItalic="ArabicBold",
    )


def convert_file(source: Path, destination: Path, styles: dict[str, ParagraphStyle]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    story = render_markdown(source, styles)
    document = SimpleDocTemplate(
        str(destination),
        pagesize=PAGE_SIZE,
        rightMargin=PAGE_MARGIN,
        leftMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN,
        bottomMargin=PAGE_MARGIN,
        title=source.stem.replace("_", " "),
        author="Arabic Project Documentation",
        subject="Arabic project documentation",
        pageCompression=1,
    )
    document.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frontend-only",
        action="store_true",
        help="Generate a separate PDF set for frontend source and configuration docs.",
    )
    args = parser.parse_args()
    setup_fonts()
    styles = make_styles()
    output_dir = FRONTEND_OUTPUT_DIR if args.frontend_only else OUTPUT_DIR
    sources = sorted(
        (
            path for path in SOURCE_DIR.rglob("*.md")
            if OUTPUT_DIR not in path.parents
            and (
                not args.frontend_only
                or (
                    FRONTEND_DOC_DIR in path.parents
                    and "dist" not in path.relative_to(FRONTEND_DOC_DIR).parts
                    and path.name != "package-lock_json_doc.md"
                )
            )
        ),
        key=lambda path: (
            path.relative_to(FRONTEND_DOC_DIR).as_posix().lower()
            if args.frontend_only
            else path.relative_to(SOURCE_DIR).as_posix().lower()
        ),
    )
    if not sources:
        search_dir = FRONTEND_DOC_DIR if args.frontend_only else SOURCE_DIR
        raise FileNotFoundError(f"No Markdown documentation found under {search_dir}.")

    generated = []
    for source in sources:
        source_root = FRONTEND_DOC_DIR if args.frontend_only else SOURCE_DIR
        relative = source.relative_to(source_root).with_suffix(".pdf")
        destination = output_dir / relative
        convert_file(source, destination, styles)
        generated.append(destination)
        print(f"Created PDF {len(generated)}/{len(sources)}")

    print(f"Generated {len(generated)} PDF files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
