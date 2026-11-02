"""JavaScript, TypeScript and Java analysis with Tree-sitter.

Tree-sitter turns source text into a concrete syntax tree and keeps working on code with
syntax errors, which is why it is used for languages without a parser in the standard
library. The grammars only read text; nothing is executed.

Symbols are collected from the top level and from class bodies, which is what a reader
wants in an outline. Imports are collected from the whole file.
"""

import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from app.services.analysis.models import (
    CLASS,
    ENUM,
    FUNCTION,
    INTERFACE,
    METHOD,
    TYPE,
    FileAnalysis,
    ImportRef,
    Symbol,
)

_LANGUAGES = {
    "JavaScript": Language(tree_sitter_javascript.language()),
    "TypeScript": Language(tree_sitter_typescript.language_typescript()),
    "TSX": Language(tree_sitter_typescript.language_tsx()),
    "Java": Language(tree_sitter_java.language()),
}

MAX_SIGNATURE_CHARS = 300
MAX_DOC_CHARS = 200


def parse(language: str, path: str, source: str) -> FileAnalysis:
    grammar = "TSX" if language == "TypeScript" and path.lower().endswith(".tsx") else language
    data = source.encode("utf-8")
    root = Parser(_LANGUAGES[grammar]).parse(data).root_node

    result = FileAnalysis(parse_error=root.has_error)
    if language == "Java":
        _java(root, data, result)
    else:
        _ecmascript(root, data, result)
    result.imports.sort(key=lambda ref: ref.line)
    return result


# --- helpers ------------------------------------------------------------------------


def _text(node: Node | None) -> str:
    return node.text.decode("utf-8", errors="replace") if node is not None and node.text else ""


def _squash(text: str, limit: int = MAX_SIGNATURE_CHARS) -> str:
    return " ".join(text.split())[:limit]


def _slice(data: bytes, start: int, end: int) -> str:
    return data[start:end].decode("utf-8", errors="replace")


def _string_value(node: Node | None) -> str | None:
    """Contents of a plain string literal node, or None for anything else."""
    if node is None or node.type != "string":
        return None
    return _text(node)[1:-1]


def _leading_doc(node: Node) -> str | None:
    """First line of a /** ... */ comment sitting directly above the node."""
    previous = node.prev_named_sibling
    if previous is None or previous.type not in ("comment", "block_comment"):
        return None
    if previous.end_point[0] < node.start_point[0] - 1:
        return None  # there is a gap, so the comment belongs to something else
    text = _text(previous)
    if not text.startswith("/**"):
        return None
    for line in text.strip("/*").splitlines():
        cleaned = line.strip().lstrip("*").strip()
        if cleaned and not cleaned.startswith("@"):
            return cleaned[:MAX_DOC_CHARS]
    return None


def _symbol(
    kind: str,
    name: str,
    parents: list[str],
    span: Node,
    signature: str,
    doc: str | None,
    decorators: list[str],
) -> Symbol:
    return Symbol(
        kind=kind,
        name=name,
        qualified_name=".".join([*parents, name]),
        start_line=span.start_point[0] + 1,
        end_line=span.end_point[0] + 1,
        signature=_squash(signature),
        doc=doc,
        decorators=decorators,
    )


# --- JavaScript and TypeScript ----------------------------------------------------------

_ES_FUNCTIONS = {"function_declaration", "generator_function_declaration"}
_ES_CLASSES = {"class_declaration", "abstract_class_declaration"}
_ES_FUNCTION_VALUES = {"arrow_function", "function_expression", "function", "generator_function"}
_ES_MEMBERS = {"method_definition", "abstract_method_signature"}
_ES_FIELDS = {"public_field_definition", "field_definition"}


def _ecmascript(root: Node, data: bytes, result: FileAnalysis) -> None:
    for node in root.children:
        _es_statement(node, data, result, [], None)
    _es_imports(root, result)


def _trim_header(text: str) -> str:
    """Drop the trailing "=>", "{", ";" or "=" that sits between a header and its body."""
    text = text.rstrip()
    while True:
        if text.endswith("=>"):
            text = text[:-2].rstrip()
        elif text.endswith(("{", ";", "=")):
            text = text[:-1].rstrip()
        else:
            return text


def _header(node: Node, data: bytes, start: Node | None = None) -> str:
    """Source text from the start of a declaration to the start of its body."""
    body = node.child_by_field_name("body")
    end = body.start_byte if body is not None else node.end_byte
    return _trim_header(_slice(data, (start or node).start_byte, end))


def _es_decorators(*nodes: Node | None) -> list[str]:
    found: list[str] = []
    for node in nodes:
        if node is not None:
            found += [_squash(_text(c)) for c in node.children if c.type == "decorator"]
    return found


def _es_statement(
    node: Node, data: bytes, result: FileAnalysis, parents: list[str], outer: Node | None
) -> None:
    kind = node.type
    if kind == "export_statement":
        declaration = node.child_by_field_name("declaration")
        if declaration is not None:
            _es_statement(declaration, data, result, parents, node)
    elif kind == "ambient_declaration":  # declare module "x" { ... }
        for child in node.named_children:
            _es_statement(child, data, result, parents, outer)
    elif kind in ("module", "internal_module"):  # namespace Name { ... }
        body = node.child_by_field_name("body")
        for child in body.named_children if body is not None else []:
            _es_statement(child, data, result, parents, None)
    elif kind == "expression_statement" and node.named_children:
        _es_statement(node.named_children[0], data, result, parents, outer)
    elif kind in _ES_FUNCTIONS:
        name = _text(node.child_by_field_name("name")) or "default"
        result.symbols.append(
            _symbol(
                FUNCTION,
                name,
                parents,
                node,
                _header(node, data),
                _leading_doc(outer or node),
                _es_decorators(node, outer),
            )
        )
    elif kind in _ES_CLASSES:
        _es_class(node, data, result, parents, outer)
    elif kind == "interface_declaration":
        _es_simple(INTERFACE, node, data, result, parents, outer)
    elif kind == "enum_declaration":
        _es_simple(ENUM, node, data, result, parents, outer)
    elif kind == "type_alias_declaration":
        _es_simple(TYPE, node, data, result, parents, outer)
    elif kind in ("lexical_declaration", "variable_declaration"):
        _es_variables(node, data, result, parents, outer)


def _es_simple(
    kind: str, node: Node, data: bytes, result: FileAnalysis, parents: list[str], outer: Node | None
) -> None:
    name = _text(node.child_by_field_name("name"))
    if name:
        header = _header(node, data).split("\n")[0]
        result.symbols.append(
            _symbol(kind, name, parents, node, header, _leading_doc(outer or node), [])
        )


def _es_variables(
    node: Node, data: bytes, result: FileAnalysis, parents: list[str], outer: Node | None
) -> None:
    """`const handler = () => {}` and `const f = function () {}` count as functions."""
    for declarator in node.named_children:
        if declarator.type != "variable_declarator":
            continue
        value = declarator.child_by_field_name("value")
        name = _text(declarator.child_by_field_name("name"))
        if value is None or value.type not in _ES_FUNCTION_VALUES or not name:
            continue
        result.symbols.append(
            _symbol(
                FUNCTION,
                name,
                parents,
                node,
                _header(value, data, start=node),
                _leading_doc(outer or node),
                [],
            )
        )


def _es_class(
    node: Node, data: bytes, result: FileAnalysis, parents: list[str], outer: Node | None
) -> None:
    name = _text(node.child_by_field_name("name"))
    if not name:
        return
    result.symbols.append(
        _symbol(
            CLASS,
            name,
            parents,
            node,
            _header(node, data),
            _leading_doc(outer or node),
            _es_decorators(node, outer),
        )
    )
    body = node.child_by_field_name("body")
    for member in body.named_children if body is not None else []:
        member_name = _member_name(member)
        if not member_name:
            continue
        if member.type in _ES_MEMBERS:
            signature = _header(member, data)
        elif member.type in _ES_FIELDS:
            value = member.child_by_field_name("value")
            if value is None or value.type not in _ES_FUNCTION_VALUES:
                continue  # plain properties are not symbols
            signature = _header(value, data, start=member)
        else:
            continue
        result.symbols.append(
            _symbol(
                METHOD,
                member_name,
                [*parents, name],
                member,
                signature,
                _leading_doc(member),
                _es_decorators(member),
            )
        )


def _member_name(member: Node) -> str:
    name_node = member.child_by_field_name("name") or member.child_by_field_name("property")
    if name_node is None:
        return ""
    text = _text(name_node)
    return text[1:-1] if name_node.type == "string" else text


def _es_imports(root: Node, result: FileAnalysis) -> None:
    stack = [root]
    while stack:  # an explicit stack, because deep trees would overflow recursion
        node = stack.pop()
        stack.extend(reversed(node.children))
        line = node.start_point[0] + 1

        if node.type == "import_statement":
            source = node.child_by_field_name("source")
            if source is None:  # import x = require("y")
                clause = next((c for c in node.children if c.type == "import_require_clause"), None)
                source = clause.child_by_field_name("source") if clause is not None else None
            module = _string_value(source)
            if module is not None:
                result.imports.append(ImportRef(module, line, _import_names(node)))
        elif node.type == "export_statement":
            module = _string_value(node.child_by_field_name("source"))
            if module is not None:  # export { a } from "./a"  /  export * from "./b"
                result.imports.append(ImportRef(module, line, _export_names(node)))
        elif node.type == "call_expression":
            function = _text(node.child_by_field_name("function"))
            if function in ("require", "import"):
                arguments = node.child_by_field_name("arguments")
                first = (
                    arguments.named_children[0] if arguments and arguments.named_children else None
                )
                module = _string_value(first)
                if module is not None:
                    result.imports.append(ImportRef(module, line))


def _import_names(statement: Node) -> list[str]:
    names: list[str] = []
    for clause in (c for c in statement.children if c.type == "import_clause"):
        for part in clause.named_children:
            if part.type == "identifier":
                names.append("default")
            elif part.type == "namespace_import":
                names.append("*")
            elif part.type == "named_imports":
                names += [
                    _text(s.child_by_field_name("name"))
                    for s in part.named_children
                    if s.type == "import_specifier"
                ]
    return names


def _export_names(statement: Node) -> list[str]:
    clause = next((c for c in statement.children if c.type == "export_clause"), None)
    if clause is None:
        return ["*"]
    return [
        _text(s.child_by_field_name("name"))
        for s in clause.named_children
        if s.type == "export_specifier"
    ]


# --- Java -----------------------------------------------------------------------------

_JAVA_TYPES = {
    "class_declaration": CLASS,
    "record_declaration": CLASS,
    "interface_declaration": INTERFACE,
    "annotation_type_declaration": INTERFACE,
    "enum_declaration": ENUM,
}
_JAVA_BODIES = {
    "class_body",
    "interface_body",
    "enum_body",
    "annotation_type_body",
    "enum_body_declarations",
}


def _java(root: Node, data: bytes, result: FileAnalysis) -> None:
    for node in root.children:
        if node.type == "import_declaration":
            _java_import(node, result)
        elif node.type in _JAVA_TYPES:
            _java_type(node, data, result, [])


def _java_import(node: Node, result: FileAnalysis) -> None:
    identifier = next((c for c in node.children if c.type == "scoped_identifier"), None)
    if identifier is None:
        return
    qualified = _text(identifier)
    wildcard = any(c.type == "asterisk" for c in node.children)
    is_static = _text(node).lstrip().startswith("import static")
    line = node.start_point[0] + 1

    if wildcard:  # import a.b.*;  or  import static a.b.Class.*;
        result.imports.append(ImportRef(qualified, line, ["*"]))
    elif is_static:  # import static a.b.Class.member;  ->  the class, plus the member used
        module, _, member = qualified.rpartition(".")
        result.imports.append(ImportRef(module, line, [member]))
    else:
        result.imports.append(ImportRef(qualified, line))


def _java_modifiers(node: Node) -> tuple[list[str], list[str], Node | None]:
    """(keywords like "public static", annotations like "@Override", modifiers node)."""
    modifiers = next((c for c in node.children if c.type == "modifiers"), None)
    keywords: list[str] = []
    annotations: list[str] = []
    for child in modifiers.children if modifiers is not None else []:
        if child.type in ("marker_annotation", "annotation"):
            annotations.append(_squash(_text(child)))
        else:
            keywords.append(_text(child))
    return keywords, annotations, modifiers


def _java_signature(node: Node, data: bytes, keywords: list[str], modifiers: Node | None) -> str:
    body = node.child_by_field_name("body")
    end = body.start_byte if body is not None else node.end_byte
    start = modifiers.end_byte if modifiers is not None else node.start_byte
    header = _slice(data, start, end).strip().rstrip(";").strip()
    return " ".join([*keywords, header])


def _java_type(node: Node, data: bytes, result: FileAnalysis, parents: list[str]) -> None:
    name = _text(node.child_by_field_name("name"))
    if not name:
        return
    keywords, annotations, modifiers = _java_modifiers(node)
    result.symbols.append(
        _symbol(
            _JAVA_TYPES[node.type],
            name,
            parents,
            node,
            _java_signature(node, data, keywords, modifiers),
            _leading_doc(node),
            annotations,
        )
    )
    body = node.child_by_field_name("body")
    if body is not None:
        _java_members(body, data, result, [*parents, name])


def _java_members(body: Node, data: bytes, result: FileAnalysis, parents: list[str]) -> None:
    for member in body.named_children:
        if member.type in ("method_declaration", "constructor_declaration"):
            name = _text(member.child_by_field_name("name"))
            keywords, annotations, modifiers = _java_modifiers(member)
            if member.type == "method_declaration" and name == "main" and "static" in keywords:
                result.has_main = True
            result.symbols.append(
                _symbol(
                    METHOD,
                    name,
                    parents,
                    member,
                    _java_signature(member, data, keywords, modifiers),
                    _leading_doc(member),
                    annotations,
                )
            )
        elif member.type in _JAVA_TYPES:
            _java_type(member, data, result, parents)
        elif member.type in _JAVA_BODIES:  # methods declared after enum constants
            _java_members(member, data, result, parents)
