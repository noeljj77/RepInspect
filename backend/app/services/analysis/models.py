"""Plain data produced by static analysis. No database or framework dependencies,
so every analyzer can be tested on its own."""

from dataclasses import dataclass, field

# Symbol kinds, shared by every language parser.
FUNCTION = "function"
CLASS = "class"
METHOD = "method"
INTERFACE = "interface"
ENUM = "enum"
TYPE = "type"


@dataclass
class Symbol:
    kind: str
    name: str
    # Includes the enclosing class, e.g. "UserService.create".
    qualified_name: str
    start_line: int
    end_line: int
    signature: str
    doc: str | None = None
    # Decorators / annotations as written, e.g. '@router.post("/login")'.
    decorators: list[str] = field(default_factory=list)


@dataclass
class ImportRef:
    """One import statement. `module` is exactly what the source says.

    Python relative imports keep their leading dots (".utils", "..models"), and
    JavaScript/TypeScript module specifiers keep their path ("./api/client").
    """

    module: str
    line: int
    names: list[str] = field(default_factory=list)


@dataclass
class FileAnalysis:
    symbols: list[Symbol] = field(default_factory=list)
    imports: list[ImportRef] = field(default_factory=list)
    # Python `if __name__ == "__main__"`, or a Java `public static void main`.
    has_main: bool = False
    # The file could not be fully parsed; the symbols found so far are still kept.
    parse_error: bool = False
