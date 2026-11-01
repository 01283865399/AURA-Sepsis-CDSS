#!/usr/bin/env python3
"""Generate Arabic, per-file documentation for the project workspace."""

from __future__ import annotations

import ast
import os
import re
import tokenize
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "شرح"
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "شرح",
    "Documentation",
}
SENSITIVE_NAME_PARTS = (
    ".env",
    "secret",
    "credential",
    "password",
    "id_rsa",
    "id_ed25519",
)
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
DATA_DIRS = {"data", "datasets", "dataset"}
NON_TEXT_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".csv",
    ".joblib",
    ".pkl",
    ".pickle",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".mp4",
    ".mp3",
}
LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "jsx",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".css": "css",
    ".html": "html",
    ".htm": "html",
    ".sql": "sql",
    ".json": "json",
    ".md": "markdown",
    ".txt": "text",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".ini": "ini",
    ".gitignore": "gitignore",
    ".sh": "bash",
    ".bat": "bat",
    ".ps1": "powershell",
}
SECRET_ASSIGNMENT = re.compile(
    r"""(?i)(["']?(?:password|passwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key)["']?\s*[:=]\s*)"""
    r"""(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s,;]+)"""
)
URI_PASSWORD = re.compile(r"(?i)(://[^:/\s]+:)[^@/\s]+(@)")
PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
    re.DOTALL,
)
PYTHON_DEF_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

PROJECT_PURPOSES = {
    "main.py": "نقطة دخول خدمة FastAPI؛ تجمع المسارات وواجهات المرضى وربط التخزين والنماذج.",
    "sepsis_service.py": "خدمة تحميل نموذج الإنتان والتحقق من أهليته وتشغيل الاستدلال.",
    "train_sepsis.py": "مسار تدريب نموذج التنبؤ بالإنتان وتجهيز أثره للاستخدام البحثي.",
    "train_model.py": "أداة تدريب نموذج/نماذج تعلم آلي مساندة للمشروع.",
    "preprocess.py": "خطوات تنظيف وتحويل وتجهيز البيانات قبل التدريب أو التقييم.",
    "load_data.py": "تحميل بيانات المشروع أو قراءتها من مصدرها إلى البنية التي يستهلكها النظام.",
    "explain_model.py": "تحليل أو تفسير مخرجات النموذج وخصائصه.",
    "App.jsx": "المكوّن الجذري لتطبيق React وتجميع واجهاته ومساراته.",
    "main.jsx": "نقطة تشغيل الواجهة؛ تهيئة React وربط المكوّن الجذري بعنصر الصفحة.",
    "ClinicalDashboard.jsx": "واجهة لوحة المتابعة السريرية وعرض بيانات المرضى/المخاطر.",
    "PatientsDirectory.jsx": "واجهة دليل المرضى وإجراءات استعراض السجلات.",
    "PatientFormModal.jsx": "نافذة إدخال أو تعديل بيانات المريض والتحقق من حقول النموذج.",
    "HomePage.jsx": "الصفحة الرئيسية لواجهة المستخدم.",
    "dashboard.css": "تنسيقات لوحة المتابعة ومكوّناتها.",
    "index.css": "تنسيقات عامة/أساسية لواجهة المستخدم.",
    "pages.css": "تنسيقات صفحات التطبيق.",
    "test_patient_directory.py": "اختبارات سلوك دليل المرضى وواجهات التخزين المرتبطة به.",
    "test_pdf_export.py": "اختبارات إنشاء أو تصدير ملفات PDF.",
    "test_sepsis_pipeline.py": "اختبارات مسار تجهيز بيانات الإنتان والتنبؤ بها.",
}


def is_sensitive(path: Path) -> bool:
    name = path.name.lower()
    return (
        any(part in name for part in SENSITIVE_NAME_PARTS)
        or path.suffix.lower() in SENSITIVE_SUFFIXES
    )


def is_data_file(relative_path: Path) -> bool:
    return any(part.lower() in DATA_DIRS for part in relative_path.parts[:-1])


def read_text(path: Path) -> str | None:
    try:
        with tokenize.open(path) as file:
            text = file.read()
    except (OSError, UnicodeError, SyntaxError):
        return None
    if "\x00" in text:
        return None
    return text


def redact(text: str) -> tuple[str, bool]:
    redacted = PRIVATE_KEY_BLOCK.sub("[محتوى مفتاح خاص محجوب]", text)
    redacted = SECRET_ASSIGNMENT.sub(r"\1[قيمة سرية محجوبة]", redacted)
    redacted = URI_PASSWORD.sub(r"\1[قيمة سرية محجوبة]\2", redacted)
    return redacted, redacted != text


def code_fence(language: str, text: str) -> str:
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{language}\n{text.rstrip()}\n{fence}"


def purpose_for(relative_path: Path, suffix: str) -> str:
    name = relative_path.name
    extension = suffix.lower()
    known = {
        ".py": "ملف Python قد يحتوي منطقاً تنفيذياً أو أدوات أو اختبارات.",
        ".jsx": "مكوّن أو واجهة React مكتوبة بصيغة JSX.",
        ".js": "شفرة JavaScript أو إعدادات تشغيل الواجهة.",
        ".css": "قواعد تنسيق ومظهر الواجهة.",
        ".html": "هيكل صفحة ويب أو نقطة دخول للواجهة.",
        ".sql": "تعريفات أو تعديلات لمخطط قاعدة البيانات.",
        ".json": "بيانات منظّمة أو إعدادات بصيغة JSON.",
        ".md": "وثيقة أو دليل مكتوب بصيغة Markdown.",
        ".txt": "ملف نصي، أو قائمة/بيانات مساعدة.",
        ".csv": "جدول بيانات؛ لم تُنسخ صفوفه إلى التوثيق.",
        ".sqlite": "قاعدة بيانات ثنائية؛ لم تُنسخ سجلاتها إلى التوثيق.",
        ".sqlite3": "قاعدة بيانات ثنائية؛ لم تُنسخ سجلاتها إلى التوثيق.",
        ".png": "صورة أو مخرج رسومي ثنائي.",
        ".jpg": "صورة ثنائية.",
        ".jpeg": "صورة ثنائية.",
        ".joblib": "أثر نموذج أو بيانات تسلسلية ثنائية.",
        ".pkl": "أثر Python تسلسلي ثنائي.",
    }
    purpose = PROJECT_PURPOSES.get(
        name,
        known.get(extension, "ملف من نوع " + (extension or "غير محدد") + "."),
    )
    return f"{purpose} موقعه ضمن `{relative_path.parent.as_posix() or 'جذر المشروع'}`."


def direct_descendants(node: ast.AST) -> list[ast.AST]:
    descendants = []
    pending = list(ast.iter_child_nodes(node))
    while pending:
        child = pending.pop()
        if isinstance(child, PYTHON_DEF_TYPES):
            continue
        descendants.append(child)
        pending.extend(ast.iter_child_nodes(child))
    return descendants


def annotation_text(annotation: ast.expr | None) -> str:
    return ast.unparse(annotation) if annotation is not None else "غير مصرّح به"


def signature_inputs(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = node.args
    positional = args.posonlyargs + args.args
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    fields = [
        f"`{arg.arg}: {annotation_text(arg.annotation)}`"
        + (f" (افتراضي `{ast.unparse(default)}`)" if default is not None else "")
        for arg, default in zip(positional, defaults)
    ]
    if args.vararg:
        fields.append(f"`*{args.vararg.arg}: {annotation_text(args.vararg.annotation)}`")
    fields.extend(
        f"`{arg.arg}: {annotation_text(arg.annotation)}` (وسيط مسمى)"
        for arg in args.kwonlyargs
    )
    if args.kwarg:
        fields.append(f"`**{args.kwarg.arg}: {annotation_text(args.kwarg.annotation)}`")
    return ", ".join(fields) or "لا توجد معاملات معلنة"


def python_sections(text: str) -> list[tuple[str, str, str]]:
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        return [("تحليل المصدر", text, f"تعذر تحليل الملف نحوياً: {error.msg}.")]

    lines = text.splitlines()
    nodes: list[ast.AST] = []
    for node in tree.body:
        if isinstance(node, (PYTHON_DEF_TYPES, ast.Import, ast.ImportFrom)):
            nodes.append(node)
        else:
            nodes.append(node)

    sections = []
    for node in nodes:
        start = getattr(node, "lineno", 1)
        if isinstance(node, PYTHON_DEF_TYPES) and node.decorator_list:
            start = min(start, *(decorator.lineno for decorator in node.decorator_list))
        end = getattr(node, "end_lineno", start)
        snippet = "\n".join(lines[start - 1 : end])
        if isinstance(node, ast.ClassDef):
            title = f"الصنف `{node.name}`"
            methods = [
                child.name for child in node.body
                if isinstance(child, PYTHON_DEF_TYPES)
            ]
            bases = [ast.unparse(base) for base in node.bases]
            detail = "يجمع هذا التعريف الحالة والسلوك في صنف."
            if bases:
                detail += " الأصناف/الأنواع الأساسية: " + "، ".join(f"`{base}`" for base in bases) + "."
            if methods:
                method_details = [
                    f"`{child.name}({signature_inputs(child)})`"
                    for child in node.body
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                detail += " أعضاؤه الإجرائية: " + "؛ ".join(method_details) + "."
            detail += " مدخلاته ومخرجاته تظهر عبر بانيه وأعضائه؛ راجع التواقيع أعلاه."
        elif isinstance(node, PYTHON_DEF_TYPES):
            title = f"الدالة `{node.name}`"
            output = annotation_text(node.returns)
            detail = (
                f"المدخلات المعلنة: {signature_inputs(node)}. "
                f"نوع الإرجاع المعلن: {output}. "
                "يوضح التوقيع شكل الواجهة؛ وقد لا يصف كل القيود وقت التشغيل."
            )
            docstring = ast.get_docstring(node)
            if docstring:
                detail += f" توثيق الدالة في المصدر: «{docstring.splitlines()[0]}»."
            descendants = direct_descendants(node)
            constructs = []
            if any(isinstance(item, ast.If) for item in descendants):
                constructs.append("تفرّع شرطي")
            if any(isinstance(item, (ast.For, ast.AsyncFor, ast.While)) for item in descendants):
                constructs.append("تكرار")
            if any(isinstance(item, (ast.Try, ast.Raise)) for item in descendants):
                constructs.append("معالجة/رفع استثناءات")
            if any(isinstance(item, ast.Await) for item in descendants):
                constructs.append("تنفيذ غير متزامن")
            if constructs:
                detail += " تظهر في الجسم بنى: " + "، ".join(constructs) + "."
            returns = [
                ast.unparse(item.value)
                for item in descendants
                if isinstance(item, ast.Return) and item.value is not None
            ]
            if returns:
                detail += " تعبيرات الإرجاع المرصودة: " + "؛ ".join(
                    f"`{value[:100]}`" for value in returns[:3]
                ) + "."
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            title = "استيراد الاعتماديات"
            detail = (
                "يحمّل هذا الجزء الوحدات أو الأسماء التي يعتمد عليها الملف. "
                "قد يؤدي الاستيراد إلى تنفيذ تهيئة الوحدة المستوردة."
            )
        else:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = getattr(node, "targets", [getattr(node, "target", None)])
                names = [ast.unparse(target) for target in targets if target is not None]
                title = "تعريف قيمة على مستوى الوحدة"
                detail = (
                    f"يعرّف/يحدّث الاسم `{', '.join(names)}` عند تقييم الوحدة. "
                    "قد تتأثر قيمته بترتيب التنفيذ أو الإعدادات المحيطة."
                )
            elif isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try)):
                title = "كتلة تنفيذ على مستوى الوحدة"
                detail = (
                    "تتحكم هذه الكتلة في التهيئة أو التنفيذ عبر شرط/تكرار/معالجة استثناءات؛ "
                    "تُقيّم عند تنفيذ الوحدة ما لم تكن داخل مسار مؤجل."
                )
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                title = "توثيق الوحدة"
                detail = "هذا نص توثيقي يصف الوحدة ولا ينفذ عادةً منطقاً تشغيلياً."
            else:
                title = "تعريف أو تهيئة على مستوى الوحدة"
                detail = (
                    "ينفذ هذا الجزء عند تقييم الوحدة أو يعرّف قيمة/نوعاً على مستواها؛ "
                    "قد تتأثر آثاره بترتيب الاستيراد."
                )
        sections.append((title, snippet, detail))
    return sections


def generic_sections(text: str, suffix: str) -> list[tuple[str, str, str]]:
    patterns = {
        ".js": re.compile(r"(?m)^\s*(?:export\s+)?(?:async\s+)?function\s+\w+|^\s*(?:export\s+)?class\s+\w+|^\s*(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"),
        ".jsx": re.compile(r"(?m)^\s*(?:export\s+)?(?:async\s+)?function\s+\w+|^\s*(?:export\s+)?class\s+\w+|^\s*(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"),
        ".css": re.compile(r"(?m)^[^{\n][^{]*\{"),
        ".sql": re.compile(r"(?im)^\s*(?:CREATE|ALTER|DROP|INSERT|UPDATE|DELETE|SELECT|WITH)\b"),
        ".html": re.compile(r"(?i)<(?:!doctype|html|head|body|main|header|footer|section|form|script|style)\b"),
        ".md": re.compile(r"(?m)^#{1,6}\s+.+$"),
    }
    pattern = patterns.get(suffix.lower())
    if pattern is None:
        chunks = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        return [
            (
                f"كتلة نصية {index}",
                chunk,
                "تعرض هذه الكتلة تعريفات أو إعدادات/نصوصاً متجاورة. "
                "تفسير القيم يعتمد على الأداة أو الملف الذي يستهلكها.",
            )
            for index, chunk in enumerate(chunks, 1)
        ]

    matches = list(pattern.finditer(text))
    if not matches:
        return [("محتوى الملف", text, "يعرض هذا الجزء المحتوى؛ لم تُكتشف حدود دوال أو أقسام واضحة آلياً.")]

    lines = text.splitlines()
    sections = []
    prefix = text[: matches[0].start()].strip()
    if prefix:
        sections.append((
            "تمهيد أو تعريفات أولية",
            prefix,
            "يتضمن عادةً تعليقات أو استيرادات أو إعدادات تسبق الأقسام الرئيسة.",
        ))
    for index, match in enumerate(matches):
        start = text.count("\n", 0, match.start())
        end_offset = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        end = text.count("\n", 0, end_offset)
        snippet = "\n".join(lines[start:end]).strip()
        marker = match.group(0).strip().replace("\n", " ")
        if suffix.lower() == ".sql":
            keyword = marker.split()[0].upper()
            sql_explanations = {
                "CREATE": "ينشئ هذا الأمر كياناً/جدولاً أو فهرساً وفق الأعمدة والقيود الظاهرة؛ "
                "مخرجه تغيير بنية المخطط أو تحسين الاستعلامات.",
                "ALTER": "يعدّل هذا الأمر بنية كيان موجود، ولا يعيد عادةً صفوف بيانات.",
                "DROP": "يحذف هذا الأمر كياناً من المخطط؛ أثره يعتمد على نوع الكيان وخيارات الحذف.",
                "INSERT": "يضيف سجلات إلى الجدول المحدد؛ القيم المطلوبة والقيود يحددها المخطط.",
                "UPDATE": "يعدّل سجلات مطابقة لشرط الأمر؛ نطاق التعديل يعتمد على WHERE.",
                "DELETE": "يحذف سجلات مطابقة لشرط الأمر؛ نطاق الحذف يعتمد على WHERE.",
                "SELECT": "يقرأ أعمدة/صفوفاً من المصادر المحددة، مع التصفية والترتيب المعرّفين.",
                "WITH": "يعرّف استعلاماً فرعياً مسمى ثم يستخدمه الاستعلام اللاحق.",
            }
            detail = sql_explanations.get(
                keyword,
                "تعليمة SQL؛ مدخلاتها ومخرجاتها وأثرها تتحدد بجدولها وقيودها ونص الأمر.",
            )
        elif suffix.lower() == ".css":
            detail = (
                "يحدد هذا الجزء خصائص العرض لعناصر تطابق المحدد؛ لا يغيّر بيانات التطبيق. "
                "الأولوية النهائية تتأثر بخصوصية المحدد وترتيب تحميل ملفات CSS."
            )
        elif suffix.lower() == ".md":
            detail = (
                "قسم توثيقي عنوانه منقول من المصدر؛ محتواه نص إرشادي وليس شيفرة تنفيذية."
            )
        elif suffix.lower() in {".js", ".jsx"} and "function" in marker:
            detail = (
                "تعريف دالة JavaScript؛ المدخلات هي المعاملات في التوقيع، "
                "أما القيمة المرجعة والآثار فتتحدد بجسم الدالة."
            )
        elif suffix.lower() in {".js", ".jsx"} and "class" in marker:
            detail = (
                "تعريف صنف JavaScript يجمع الحالة والسلوك؛ واجهته تتحدد بالمنشئ والأعضاء."
            )
        elif suffix.lower() in {".js", ".jsx"} and "=>" in marker:
            detail = (
                "تعريف دالة سهمية؛ مدخلاتها من المعاملات الظاهرة، وسلوكها/قيمتها "
                "المرجعة تحددها عبارة الجسم."
            )
        elif suffix.lower() == ".html":
            detail = (
                "جزء من هيكل الصفحة؛ العناصر والسمات تحدد المحتوى أو الموارد المرتبطة، "
                "والسلوك التفاعلي قد يأتي من JavaScript."
            )
        else:
            detail = (
                "يعرض هذا الجزء كتلة من إعدادات أو محتوى منظم. "
                "تفسير القيم يعتمد على الأداة أو الملف الذي يستهلكها."
            )
        sections.append((
            f"قسم يبدأ بـ `{marker[:100]}`",
            snippet,
            detail,
        ))
    return sections


def imports_and_paths(text: str, relative_path: Path) -> list[str]:
    candidates = set()
    for match in re.finditer(
        r"""(?m)^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+)|import\s+.*?from\s+['"]([^'"]+)['"]|(?:href|src)\s*=\s*['"]([^'"]+)['"])""",
        text,
    ):
        target = next((value for value in match.groups() if value), "")
        if target.startswith("."):
            candidate = (relative_path.parent / target).as_posix()
            candidates.add(candidate)
        elif target.startswith(("backend.", "frontend.", "tests.")):
            candidates.add(target.replace(".", "/"))
    return sorted(candidates)


def documentation_for(path: Path, relative_path: Path) -> str:
    stat = path.stat()
    suffix = ".gitignore" if path.name == ".gitignore" else path.suffix.lower()
    lines = [
        f"# توثيق الملف: `{relative_path.as_posix()}`",
        "",
        "## المقدمة والهدف",
        "",
        purpose_for(relative_path, suffix),
        "",
        f"- المسار النسبي: `{relative_path.as_posix()}`",
        f"- الحجم: {stat.st_size:,} بايت.",
        f"- آخر تعديل مسجل: {datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()}.",
        "",
        "## الكود أو المحتوى المصدري الكامل",
        "",
    ]

    if is_sensitive(path):
        lines += [
            "لم يُدرج المحتوى لأن اسم الملف يشير إلى بيانات اعتماد أو مادة سرية. "
            "هذا الحجب متعمد لتجنب نسخ الأسرار إلى ملفات التوثيق.",
            "",
        ]
        text = None
    elif is_data_file(relative_path) or suffix in NON_TEXT_SUFFIXES:
        lines += [
            "المحتوى غير مضمّن: صُنّف هذا المسار على أنه بيانات أو ملف ثنائي/أثر مولّد. "
            "لا تُنسخ صفوف البيانات أو سجلات قواعد البيانات أو أوزان النماذج أو محتويات الصور "
            "إلى التوثيق حفاظاً على الخصوصية والحجم.",
            "",
        ]
        text = None
    else:
        text = read_text(path)
        if text is None:
            lines += [
                "تعذر تمثيل الملف كنص قابل للقراءة (غالباً ملف ثنائي أو بترميز غير معروف)، "
                "لذلك لم يُنسخ محتواه.",
                "",
            ]
        else:
            safe_text, did_redact = redact(text)
            if did_redact:
                lines += [
                    "حُجبت تلقائياً بعض القيم التي تطابق أنماط كلمات المرور/المفاتيح/الرموز "
                    "ومفاتيح PEM. النسخة أدناه ليست نسخة حرفية من المواضع المحجوبة.",
                    "",
                ]
            lines += [code_fence(LANGUAGES.get(suffix, "text"), safe_text), ""]

    lines += ["## الشرح التفصيلي جزءاً بجزء", ""]
    if text is None or is_sensitive(path) or is_data_file(relative_path) or suffix in NON_TEXT_SUFFIXES:
        lines += [
            "لا يعرض هذا الملف شيفرة نصية قابلة للتقسيم. يحدد قسم المقدمة نوعه ووظيفته "
            "ومساره وحجمه؛ أما البيانات الداخلية فتُقرأ عبر الأداة أو الخدمة المالكة لها.",
            "",
        ]
    else:
        safe_text, _ = redact(text)
        sections = python_sections(safe_text) if suffix == ".py" else generic_sections(safe_text, suffix)
        if not sections:
            lines += ["لم تُكتشف مقاطع بنيوية؛ راجع المحتوى الكامل أعلاه.", ""]
        for title, snippet, detail in sections:
            lines += [f"### {title}", "", code_fence(LANGUAGES.get(suffix, "text"), snippet), "", detail, ""]

    lines += ["## آلية العمل والربط", ""]
    if text is None:
        lines += [
            "هذا الملف مورد ثابت أو بيانات؛ لا يمكن استنتاج مسار تدفقها من محتواها "
            "لأنه لم يُدرج في التوثيق.",
            "",
        ]
    else:
        references = imports_and_paths(text, relative_path)
        if references:
            lines += [
                "استدلال ساكن من الاستيرادات أو المسارات النصية التي أمكن اكتشافها:",
                "",
                *[f"- `{reference}`" for reference in references],
                "",
                "قد لا تظهر هنا الروابط الديناميكية أو التي تُبنى أثناء التشغيل.",
                "",
            ]
        else:
            lines += [
                "لم تُكتشف استيرادات محلية أو مراجع مسارات مباشرة وفق الأنماط النصية المستخدمة. "
                "قد يعتمد الملف على إعدادات أو استدعاءات ديناميكية غير قابلة للاكتشاف بهذه الطريقة.",
                "",
            ]
    lines += [
        "---",
        "",
        "هذا الشرح مولّد آلياً من اسم الملف وامتداده وبنيته النصية؛ يلزم الرجوع إلى "
        "سياق التشغيل والاختبارات للتحقق من السلوك السريري/التشغيلي الفعلي.",
        "",
    ]
    return "\n".join(lines)


def collect_files() -> list[Path]:
    collected = []
    for current, directories, filenames in os.walk(ROOT):
        current_path = Path(current)
        directories[:] = sorted(
            directory for directory in directories if directory not in EXCLUDED_DIRS
        )
        for filename in sorted(filenames):
            path = current_path / filename
            if path.is_file():
                collected.append(path)
    return sorted(collected, key=lambda item: item.relative_to(ROOT).as_posix().lower())


def output_path_for(relative_path: Path) -> Path:
    doc_name = relative_path.name.replace(".", "_") + "_doc.md"
    return OUTPUT_DIR / relative_path.parent / doc_name


def main() -> int:
    files = collect_files()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated = []
    for path in files:
        relative_path = path.relative_to(ROOT)
        destination = output_path_for(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            documentation_for(path, relative_path),
            encoding="utf-8",
            newline="\n",
        )
        generated.append(destination.relative_to(OUTPUT_DIR).as_posix())

    index = [
        "# فهرس التوثيق",
        "",
        "أنشأ هذا الفهرس `generate_docs.py`. لكل ملف في مساحة العمل صفحة مقابلة "
        "مع الحفاظ على هيكل المجلدات.",
        "",
        f"- عدد الملفات الموثقة: {len(generated)}",
        "- تُستثنى مجلدات الأدوات والبيئات الافتراضية ومجلد التوثيق نفسه.",
        "- لا تُنسخ محتويات البيانات الثنائية أو مجلدات البيانات، وتحجب الملفات السرية.",
        "",
        "## الملفات",
        "",
        *[
            f"- [`{relative}`](./{relative.replace(' ', '%20')})"
            for relative in generated
        ],
        "",
    ]
    (OUTPUT_DIR / "README.md").write_text("\n".join(index), encoding="utf-8", newline="\n")
    print(f"Generated {len(generated)} documentation files and the index.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
