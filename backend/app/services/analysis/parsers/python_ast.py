"""Python analysis with the standard library's `ast` module.

`ast.parse` builds a syntax tree from text. It does not import or execute anything.
"""

import ast
import warnings

from app.services.analysis.models import (
    CLASS,
    FUNCTION,
    METHOD,
    FileAnalysis,
    ImportRef,
    Symbol,
)

MAX_DOC_CHARS = 200
MAX_SIGNATURE_CHARS = 300


def parse(source: str) -> FileAnalysis:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # e.g. invalid escape sequences in old code
            tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        # Python 2 code, templates with a .py name, or absurdly deep nesting.
        return FileAnalysis(parse_error=True)

    result = FileAnalysis()
    _collect_imports(tree, result)
    _collect_symbols(tree.body, [], result)
    result.has_main = any(_is_main_guard(node) for node in tree.body)
    return result


def _collect_imports(tree: ast.AST, result: FileAnalysis) -> None:
    # Walk everything, so imports inside functions and try/except blocks count too.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.imports.append(ImportRef(module=alias.name, line=node.lineno))
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            names = [alias.name for alias in node.names]
            result.imports.append(ImportRef(module=module, line=node.lineno, names=names))
    result.imports.sort(key=lambda ref: ref.line)


def _collect_symbols(body: list[ast.stmt], parents: list[str], result: FileAnalysis) -> None:
    for node in body:
        if isinstance(node, ast.ClassDef):
            qualified = ".".join([*parents, node.name])
            result.symbols.append(
                Symbol(
                    kind=CLASS,
                    name=node.name,
                    qualified_name=qualified,
                    start_line=_start_line(node),
                    end_line=node.end_lineno or node.lineno,
                    signature=_class_signature(node),
                    doc=_doc(node),
                    decorators=_decorators(node),
                )
            )
            _collect_symbols(node.body, [*parents, node.name], result)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            qualified = ".".join([*parents, node.name])
            result.symbols.append(
                Symbol(
                    # `parents` only ever holds classes: function bodies are not entered.
                    kind=METHOD if parents else FUNCTION,
                    name=node.name,
                    qualified_name=qualified,
                    start_line=_start_line(node),
                    end_line=node.end_lineno or node.lineno,
                    signature=_function_signature(node),
                    doc=_doc(node),
                    decorators=_decorators(node),
                )
            )
        elif isinstance(node, ast.If | ast.Try | ast.With):
            # Definitions guarded by `if TYPE_CHECKING:` or `try: ... except ImportError:`.
            blocks = [node.body, getattr(node, "orelse", []), getattr(node, "finalbody", [])]
            blocks += [handler.body for handler in getattr(node, "handlers", [])]
            for block in blocks:
                _collect_symbols(block, parents, result)


def _start_line(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """First line including decorators, so the range covers what a reader sees."""
    return min([node.lineno, *(d.lineno for d in node.decorator_list)])


def _decorators(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    return [f"@{_unparse(d)}" for d in node.decorator_list]


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    returns = f" -> {_unparse(node.returns)}" if node.returns else ""
    signature = f"{prefix} {node.name}({_unparse(node.args)}){returns}"
    return signature[:MAX_SIGNATURE_CHARS]


def _class_signature(node: ast.ClassDef) -> str:
    arguments = [_unparse(base) for base in node.bases]
    arguments += [
        f"{kw.arg}={_unparse(kw.value)}" if kw.arg else f"**{_unparse(kw.value)}"
        for kw in node.keywords
    ]
    suffix = f"({', '.join(arguments)})" if arguments else ""
    return f"class {node.name}{suffix}"[:MAX_SIGNATURE_CHARS]


def _doc(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    text = ast.get_docstring(node)
    if not text:
        return None
    return text.strip().splitlines()[0][:MAX_DOC_CHARS]


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except (ValueError, RecursionError):
        return "..."


def _is_main_guard(node: ast.stmt) -> bool:
    """True for `if __name__ == "__main__":` (in either operand order)."""
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    test = node.test
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    operands = [test.left, *test.comparators]
    names = {o.id for o in operands if isinstance(o, ast.Name)}
    constants = {o.value for o in operands if isinstance(o, ast.Constant)}
    return "__name__" in names and "__main__" in constants
