from app.services.analysis.parsers import parse_file


def symbols(analysis):
    return {s.qualified_name: s for s in analysis.symbols}


def imports(analysis):
    return [(i.module, i.names, i.line) for i in analysis.imports]


class TestPython:
    SOURCE = '''
import os, sys as system
from . import sibling
from ..pkg.mod import thing, other as alias
import json

@decorator(1, key="v")
class Service(Base, metaclass=Meta):
    """Handles users.

    Longer text that should not appear.
    """

    def create(self, name: str, *, admin: bool = False) -> "User":
        return None

    async def fetch(self): ...

    class Inner:
        def deep(self): ...


def helper(a, *args, **kwargs):
    """Does a thing."""


async def runner(): ...


if __name__ == "__main__":
    helper(1)
'''

    def test_symbols_with_lines_signatures_and_docs(self):
        found = symbols(parse_file("Python", "app.py", self.SOURCE))

        service = found["Service"]
        # Starts at the decorator line, so the range covers what a reader sees.
        assert (service.kind, service.start_line, service.end_line) == ("class", 7, 20)
        assert service.signature == "class Service(Base, metaclass=Meta)"
        assert service.doc == "Handles users."
        assert service.decorators == ["@decorator(1, key='v')"]

        create = found["Service.create"]
        assert create.kind == "method"
        assert create.signature == "def create(self, name: str, *, admin: bool=False) -> 'User'"
        assert found["Service.fetch"].signature == "async def fetch(self)"
        assert found["Service.Inner"].kind == "class"
        assert found["Service.Inner.deep"].kind == "method"

        helper = found["helper"]
        assert (helper.kind, helper.start_line, helper.end_line) == ("function", 23, 24)
        assert helper.signature == "def helper(a, *args, **kwargs)"
        assert helper.doc == "Does a thing."
        assert found["runner"].signature == "async def runner()"

    def test_imports_keep_relative_dots_and_names(self):
        result = parse_file("Python", "app.py", self.SOURCE)

        assert imports(result) == [
            ("os", [], 2),
            ("sys", [], 2),
            (".", ["sibling"], 3),
            ("..pkg.mod", ["thing", "other"], 4),
            ("json", [], 5),
        ]

    def test_main_guard_is_detected(self):
        assert parse_file("Python", "a.py", self.SOURCE).has_main is True
        assert parse_file("Python", "a.py", "def f(): ...").has_main is False
        assert parse_file("Python", "a.py", 'if "__main__" == __name__:\n    pass').has_main is True
        assert parse_file("Python", "a.py", "if __name__ == 'other':\n    pass").has_main is False

    def test_definitions_inside_guards_are_found(self):
        source = (
            "if TYPE_CHECKING:\n    from x import Y\n    class Hint: ...\n"
            "try:\n    def fast(): ...\nexcept ImportError:\n    def fast(): ...\n"
        )

        result = parse_file("Python", "a.py", source)

        assert [s.name for s in result.symbols] == ["Hint", "fast", "fast"]
        assert ("x", ["Y"], 2) in imports(result)

    def test_nested_functions_are_not_listed(self):
        result = parse_file(
            "Python", "a.py", "def outer():\n    def inner(): ...\n    class Local: ...\n"
        )

        assert [s.name for s in result.symbols] == ["outer"]

    def test_imports_inside_functions_are_found(self):
        result = parse_file(
            "Python", "a.py", "def f():\n    import lazy\n    from late import thing\n"
        )

        assert [i.module for i in result.imports] == ["lazy", "late"]

    def test_syntax_errors_are_reported_not_raised(self):
        for bad in ("def broken(:\n", "print 'python two'\n", "class X(\n"):
            result = parse_file("Python", "a.py", bad)
            assert result.parse_error is True and result.symbols == []

    def test_invalid_escape_sequences_do_not_matter(self):
        result = parse_file("Python", "a.py", 'PATTERN = "\\d+"\ndef f(): ...\n')

        assert result.parse_error is False and len(result.symbols) == 1

    def test_pathologically_deep_code_is_survived(self):
        deep = "x = " + "(" * 3000 + "1" + ")" * 3000
        result = parse_file("Python", "a.py", deep)

        assert result.parse_error is True  # too deep to parse, but no crash

    def test_empty_file(self):
        result = parse_file("Python", "a.py", "")

        assert (result.symbols, result.imports, result.parse_error) == ([], [], False)


class TestJavaScript:
    SOURCE = """
import React, { useState } from 'react';
import * as fs from "fs";
import './side-effect.css';
const express = require('express');
export { a } from './a';
export * from "./b";

/** The main component.
 * More text.
 */
export default class App extends React.Component {
  static create() {}
  async render() { return 1; }
  handle = () => { return 2; }
  value = 5;
  #priv() {}
}

function plain(a, b) {}
export async function* gen() {}
const arrow = (x) => x + 1;
export const fnExpr = function named() {};
let notAFunction = 5;
const lazy = () => import('./lazy');
"""

    def test_symbols(self):
        found = symbols(parse_file("JavaScript", "app.js", self.SOURCE))

        assert set(found) == {
            "App", "App.create", "App.render", "App.handle", "App.#priv",
            "plain", "gen", "arrow", "fnExpr", "lazy",
        }  # fmt: skip
        app = found["App"]
        assert (app.kind, app.start_line, app.end_line) == ("class", 12, 18)
        assert app.signature == "class App extends React.Component"
        assert app.doc == "The main component."
        assert found["App.create"].signature == "static create()"
        assert found["App.handle"].kind == "method"  # a class field holding an arrow function
        assert found["plain"].signature == "function plain(a, b)"
        assert found["gen"].signature == "async function* gen()"
        assert found["arrow"].signature == "const arrow = (x)"
        assert found["fnExpr"].kind == "function"

    def test_imports_include_requires_reexports_and_dynamic_imports(self):
        result = parse_file("JavaScript", "app.js", self.SOURCE)

        assert imports(result) == [
            ("react", ["default", "useState"], 2),
            ("fs", ["*"], 3),
            ("./side-effect.css", [], 4),
            ("express", [], 5),
            ("./a", ["a"], 6),
            ("./b", ["*"], 7),
            ("./lazy", [], 25),
        ]

    def test_jsx_is_understood(self):
        source = "export function Button({ label }) {\n  return <button>{label}</button>;\n}\n"

        result = parse_file("JavaScript", "Button.jsx", source)

        assert [s.name for s in result.symbols] == ["Button"]
        assert result.parse_error is False

    def test_syntax_errors_still_yield_what_can_be_read(self):
        result = parse_file("JavaScript", "a.js", "function ok() {}\nfunction broken( {\n")

        assert result.parse_error is True
        assert "ok" in [s.name for s in result.symbols]


class TestTypeScript:
    SOURCE = """
import type { A } from './types';
import { B } from "../b";
import legacy = require('legacy-lib');
export interface Props { x: number }
export type Id = string;
export enum Color { Red, Green }
@Injectable()
export abstract class Base<T> implements Props {
  constructor(private x: number) {}
  public get value(): number { return 1 }
  abstract run(): void;
}
export function typed<T>(a: T): T { return a }
const handler = async (req: Request): Promise<void> => {};
namespace NS { export function inner() {} }
"""

    def test_symbols(self):
        found = symbols(parse_file("TypeScript", "a.ts", self.SOURCE))

        assert found["Props"].kind == "interface"
        assert found["Id"].kind == "type" and found["Id"].signature == "type Id = string"
        assert found["Color"].kind == "enum"
        base = found["Base"]
        assert base.signature == "abstract class Base<T> implements Props"
        assert base.decorators == ["@Injectable()"]
        assert found["Base.constructor"].signature == "constructor(private x: number)"
        assert found["Base.value"].signature == "public get value(): number"
        assert found["Base.run"].signature == "abstract run(): void"
        assert found["typed"].signature == "function typed<T>(a: T): T"
        assert found["handler"].signature == "const handler = async (req: Request): Promise<void>"
        assert "inner" in found  # inside a namespace

    def test_imports(self):
        result = parse_file("TypeScript", "a.ts", self.SOURCE)

        assert [i.module for i in result.imports] == ["./types", "../b", "legacy-lib"]

    def test_tsx_files_use_the_tsx_grammar(self):
        source = (
            "export const App = (): JSX.Element => {\n  return <div className='x'>hi</div>;\n};\n"
        )

        result = parse_file("TypeScript", "App.tsx", source)

        assert result.parse_error is False
        assert [s.name for s in result.symbols] == ["App"]


class TestJava:
    SOURCE = """
package com.example.demo;

import java.util.List;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.*;
import com.example.util.*;

/**
 * The application.
 */
@SpringBootApplication
public class Demo extends Base implements Runnable {
    private int x;

    public Demo(int x) { this.x = x; }

    public static void main(String[] args) { }

    @Override
    public void run() {}

    interface Inner { void go(); }

    enum Kind { A, B; int rank() { return 1; } }
}

interface Service { String name(); }

record Point(int x, int y) {}
"""

    def test_symbols(self):
        found = symbols(parse_file("Java", "Demo.java", self.SOURCE))

        demo = found["Demo"]
        assert (demo.kind, demo.start_line, demo.end_line) == ("class", 12, 26)
        assert demo.signature == "public class Demo extends Base implements Runnable"
        assert demo.decorators == ["@SpringBootApplication"]
        assert demo.doc == "The application."
        assert found["Demo.Demo"].signature == "public Demo(int x)"
        assert found["Demo.main"].signature == "public static void main(String[] args)"
        assert found["Demo.run"].decorators == ["@Override"]
        assert found["Demo.run"].signature == "public void run()"
        assert found["Demo.Inner"].kind == "interface"
        assert found["Demo.Inner.go"].kind == "method"
        assert found["Demo.Kind"].kind == "enum"
        assert found["Demo.Kind.rank"].kind == "method"
        assert found["Service"].kind == "interface"
        assert found["Point"].signature == "record Point(int x, int y)"

    def test_imports(self):
        result = parse_file("Java", "Demo.java", self.SOURCE)

        assert imports(result) == [
            ("java.util.List", [], 4),
            ("org.junit.Assert", ["assertEquals"], 5),  # static: the class, and the member
            ("org.junit.Assert", ["*"], 6),
            ("com.example.util", ["*"], 7),
        ]

    def test_main_method_is_detected(self):
        assert parse_file("Java", "Demo.java", self.SOURCE).has_main is True
        assert parse_file("Java", "A.java", "class A { void main() {} }").has_main is False


def test_languages_without_a_parser_return_none():
    assert parse_file("Ruby", "a.rb", "puts 1") is None
    assert parse_file(None, "README", "text") is None
    assert parse_file("Markdown", "a.md", "# hi") is None
