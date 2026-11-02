from app.services.rag.chunking import (
    MAX_CHARS,
    MAX_LINES,
    Span,
    chunk_file,
    embedding_text,
    keywords,
    should_index,
    split_identifier,
    split_lines,
)

SERVICE = "\n".join(
    [
        "import os",  # 1
        "from app.db import session",  # 2
        "",  # 3
        "",  # 4
        "def connect(url):",  # 5
        "    return session.open(url)",  # 6
        "",  # 7
        "",  # 8
        "def close(conn):",  # 9
        "    conn.close()",  # 10
    ]
)


def lines_of(text: str, chunk) -> str:
    return "\n".join(split_lines(text)[chunk.start_line - 1 : chunk.end_line])


def assert_exact(text: str, chunks) -> None:
    """Every chunk is exactly the lines it claims, so answers can cite them."""
    for chunk in chunks:
        assert chunk.text == lines_of(text, chunk)
        assert chunk.end_line - chunk.start_line + 1 <= MAX_LINES
        assert len(chunk.text) <= MAX_CHARS


def test_each_function_is_its_own_chunk_and_the_code_between_is_kept():
    chunks = chunk_file(
        "app/db.py", SERVICE, [Span("connect", "function", 5, 6), Span("close", "function", 9, 10)]
    )

    assert [(c.symbol, c.start_line, c.end_line) for c in chunks] == [
        (None, 1, 4),  # the imports
        ("connect", 5, 6),
        ("close", 9, 10),
    ]
    assert chunks[1].kind == "function" and chunks[0].kind == "code"
    assert_exact(SERVICE, chunks)


def test_blank_or_trivial_gaps_are_not_chunks():
    text = "def a():\n    return 1\n\n\n\ndef b():\n    return 2\n"

    chunks = chunk_file("m.py", text, [Span("a", "function", 1, 2), Span("b", "function", 6, 7)])

    assert [c.symbol for c in chunks] == ["a", "b"]


def test_a_class_too_big_for_one_chunk_is_split_into_its_methods():
    body = ["class Store:", '    """Keeps orders."""', ""]
    spans = [Span("Store", "class", 1, 0)]
    for index in range(6):
        start = len(body) + 1
        body += (
            [f"    def method_{index}(self):"]
            + [f"        step({index}, {n})" for n in range(14)]
            + [""]
        )
        spans.append(Span(f"Store.method_{index}", "method", start, start + 14))
    text = "\n".join(body)
    spans[0] = Span("Store", "class", 1, len(body))

    chunks = chunk_file("store.py", text, spans)

    assert chunks[0].symbol == "Store" and chunks[0].start_line == 1  # the class header
    assert [c.symbol for c in chunks[1:]] == [f"Store.method_{i}" for i in range(6)]
    assert_exact(text, chunks)


def test_a_small_class_stays_whole():
    text = "class Point:\n    def x(self):\n        return 1\n"

    chunks = chunk_file(
        "p.py", text, [Span("Point", "class", 1, 3), Span("Point.x", "method", 2, 3)]
    )

    assert [(c.symbol, c.start_line, c.end_line) for c in chunks] == [("Point", 1, 3)]


def test_long_code_without_symbols_becomes_overlapping_windows():
    text = "\n".join(f"setting_{n} = {n}" for n in range(1, 151))

    chunks = chunk_file("settings.cfg", text)

    assert len(chunks) > 3
    assert chunks[0].start_line == 1 and chunks[-1].end_line == 150
    for before, after in zip(chunks, chunks[1:], strict=False):
        assert after.start_line <= before.end_line  # windows overlap: nothing falls between
    assert_exact(text, chunks)


def test_very_long_lines_keep_chunks_within_the_size_limit():
    text = "\n".join("x = '" + "a" * 300 + "'" for _ in range(40))

    chunks = chunk_file("data.py", text)

    assert len(chunks) > 1
    assert_exact(text, chunks)


def test_markdown_is_split_at_headings_but_not_inside_code_blocks():
    text = "\n".join(
        [
            "# Shop",
            "Sells things online, with a long enough intro.",
            "",
            "## Install",
            "```bash",
            "# this is a shell comment, not a heading",
            "pip install shop",
            "```",
            "## Payments",
            "Cards are charged through the payment provider.",
        ]
    )

    chunks = chunk_file("README.md", text)

    assert [(c.symbol, c.start_line, c.end_line) for c in chunks] == [
        ("Shop", 1, 3),
        ("Install", 4, 8),
        ("Payments", 9, 10),
    ]
    assert all(c.kind == "doc" for c in chunks)


def test_symbols_outside_the_file_are_ignored():
    text = "def add(a, b):\n    return a + b\n"

    chunks = chunk_file("m.py", text, [Span("ghost", "function", 40, 50)])

    assert [(c.symbol, c.start_line, c.end_line) for c in chunks] == [(None, 1, 2)]


def test_generated_and_data_files_are_not_indexed():
    assert not should_index("package-lock.json", 1000)
    assert not should_index("web/poetry.lock", 1000)
    assert not should_index("static/app.min.js", 1000)
    assert not should_index("data/huge.json", 80_000)
    assert should_index("package.json", 2_000)
    assert should_index("src/app.py", 20_000)
    assert not should_index("src/giant.py", 900_000)


def test_minified_code_is_skipped():
    assert chunk_file("bundle.js", "var a=1;" * 400) == []


def test_identifiers_are_split_into_words():
    assert split_identifier("getUserById") == ["get", "user", "by", "id"]
    assert split_identifier("HTTPServer") == ["http", "server"]
    assert split_identifier("parse_args2") == ["parse", "args", "2"]


def test_keywords_and_embedding_text_include_the_location():
    [chunk] = chunk_file(
        "src/services/UserService.ts",
        "export function getUserById(id) {\n  return db.find(id)\n}",
        [Span("getUserById", "function", 1, 3)],
    )

    assert {"user", "service", "get", "by", "id"} <= set(keywords(chunk).split())
    assert embedding_text(chunk).startswith(
        "File: src/services/UserService.ts\nSymbol: getUserById\n"
    )
