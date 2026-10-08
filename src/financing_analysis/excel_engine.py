"""Safely recalculate the small Excel grammar used by this thesis.

This is a source-replication tool, not a general-purpose Excel implementation.
Supported features: cell and range references, quoted sheet names, arithmetic,
percentages, comparisons, SUM, and AVERAGE. A parser builds an expression tree;
formula text is never passed to Python's eval or executed as code.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

ERROR_VALUES = frozenset({"#DIV/0!", "#VALUE!", "#REF!", "#NUM!", "#NAME?", "#N/A", "#NULL!"})
_SHEET = r"(?:'(?:[^']|'')+'|[A-Za-z_\u0080-\uffff][A-Za-z0-9_.\u0080-\uffff]*)!"
_REFERENCE = rf"(?:{_SHEET})?\$?[A-Za-z]{{1,3}}\$?[1-9][0-9]*"
_LEXER = re.compile(
    rf"(?P<reference>{_REFERENCE})"
    r'|(?P<string>"(?:[^"]|"")*")'
    r"|(?P<number>(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
    r"|(?P<identifier>[A-Za-z_][A-Za-z0-9_.]*)"
    r"|(?P<operator><=|>=|<>|[+\-*/^%=<>() ,:])"
)
_CELL = re.compile(r"\$?([A-Za-z]{1,3})\$?([1-9][0-9]*)\Z")
_PRECEDENCE = {
    "=": 10,
    "<>": 10,
    "<": 10,
    "<=": 10,
    ">": 10,
    ">=": 10,
    "+": 20,
    "-": 20,
    "*": 30,
    "/": 30,
    "^": 40,
}


class FormulaError(ValueError):
    """The source uses unsupported syntax, references, or circular calculations."""


@dataclass(frozen=True)
class Token:
    kind: str
    text: str


@dataclass(frozen=True)
class RangeValue:
    values: tuple[Any, ...]


def _tokens(formula: str) -> list[Token]:
    if not formula.startswith("="):
        raise FormulaError("A formula must begin with '='")
    result, position = [], 1
    while position < len(formula):
        if formula[position].isspace():
            position += 1
            continue
        match = _LEXER.match(formula, position)
        if match is None:
            raise FormulaError(
                f"Unsupported syntax at position {position}: {formula[position : position + 25]!r}"
            )
        result.append(Token(match.lastgroup, match.group()))
        position = match.end()
    return result


class _Parser:
    def __init__(self, formula: str):
        self.tokens = _tokens(formula)
        self.position = 0

    def peek(self) -> Token | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def take(self) -> Token:
        token = self.peek()
        if token is None:
            raise FormulaError("Unexpected end of formula")
        self.position += 1
        return token

    def expect(self, text: str) -> None:
        token = self.take()
        if token.text != text:
            raise FormulaError(f"Expected {text!r}, found {token.text!r}")

    def parse(self) -> tuple:
        expression = self.expression()
        if self.peek() is not None:
            raise FormulaError(f"Unexpected token: {self.peek().text!r}")
        return expression

    def expression(self, minimum: int = 0) -> tuple:
        token = self.take()
        if token.text in {"+", "-"}:
            # Excel unary signs bind more tightly than exponentiation.
            left = ("unary", token.text, self.expression(50))
        elif token.text == "(":
            left = self.expression()
            self.expect(")")
        elif token.kind == "number":
            left = ("literal", float(token.text))
        elif token.kind == "string":
            left = ("literal", token.text[1:-1].replace('""', '"'))
        elif token.kind == "reference":
            left = ("reference", token.text)
            if self.peek() is not None and self.peek().text == ":":
                self.take()
                end = self.take()
                if end.kind != "reference":
                    raise FormulaError("A range must end with a cell reference")
                left = ("range", token.text, end.text)
        elif token.kind == "identifier":
            name = token.text.upper()
            if name in {"TRUE", "FALSE"} and (self.peek() is None or self.peek().text != "("):
                left = ("literal", name == "TRUE")
            else:
                if name not in {"SUM", "AVERAGE"}:
                    raise FormulaError(f"Unsupported function: {name}")
                self.expect("(")
                arguments = []
                if self.peek() is not None and self.peek().text != ")":
                    while True:
                        arguments.append(self.expression())
                        if self.peek() is None or self.peek().text != ",":
                            break
                        self.take()
                self.expect(")")
                left = ("function", name, tuple(arguments))
        else:
            raise FormulaError(f"Unexpected token: {token.text!r}")

        while self.peek() is not None:
            operator = self.peek().text
            if operator == "%" and 60 >= minimum:
                self.take()
                left = ("percent", left)
                continue
            precedence = _PRECEDENCE.get(operator, -1)
            if precedence < minimum:
                break
            self.take()
            # Excel evaluates repeated powers from left to right.
            right = self.expression(precedence + 1)
            left = ("binary", operator, left, right)
        return left


def _cell_parts(address: str) -> tuple[int, int]:
    match = _CELL.fullmatch(address)
    if match is None:
        raise FormulaError(f"Invalid cell reference: {address!r}")
    column = 0
    for character in match[1].upper():
        column = column * 26 + ord(character) - ord("A") + 1
    row = int(match[2])
    if column > 16384 or row > 1048576:
        raise FormulaError(f"Cell reference is outside Excel limits: {address}")
    return column, row


def _column_name(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _reference(reference: str, current_sheet: str) -> tuple[str, str]:
    if "!" in reference:
        sheet, address = reference.rsplit("!", 1)
        if sheet.startswith("'"):
            sheet = sheet[1:-1].replace("''", "'")
    else:
        sheet, address = current_sheet, reference
    _cell_parts(address)
    return sheet, address.replace("$", "").upper()


def _is_error(value: Any) -> bool:
    return isinstance(value, str) and value in ERROR_VALUES


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (bool, int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            pass
    raise FormulaError(f"Expected a numerical value, found {value!r}")


class WorkbookEngine:
    """Evaluate each formula from source inputs; cached values are only evidence."""

    def __init__(self, snapshot: dict[str, Any]):
        if snapshot.get("schema_version") != 1:
            raise ValueError("WorkbookEngine requires snapshot schema_version 1")
        self.snapshot = snapshot
        self.sheets = {sheet["name"]: sheet["cells"] for sheet in snapshot["sheets"]}
        if len(self.sheets) != len(snapshot["sheets"]):
            raise ValueError("Duplicate sheet names in snapshot")
        self._cache: dict[tuple[str, str], Any] = {}
        self._trees: dict[tuple[str, str], tuple] = {}
        self._active: list[tuple[str, str]] = []

    def value(self, sheet: str, cell: str) -> Any:
        """Calculate one cell. A referenced empty cell remains None until arithmetic."""
        _, address = _reference(cell, sheet)
        key = (sheet, address)
        if key in self._cache:
            return self._cache[key]
        if sheet not in self.sheets:
            raise FormulaError(f"Referenced sheet does not exist: {sheet!r}")
        if key in self._active:
            chain = " -> ".join(f"{s}!{c}" for s, c in self._active + [key])
            raise FormulaError(f"Circular reference: {chain}")
        record = self.sheets[sheet].get(address)
        if record is None:
            return None
        if "formula" not in record:
            return record.get("value")
        self._active.append(key)
        try:
            if key not in self._trees:
                self._trees[key] = _Parser(record["formula"]).parse()
            calculated = self._evaluate(self._trees[key], sheet)
            if isinstance(calculated, RangeValue):
                raise FormulaError("A range cannot be a scalar formula result")
            self._cache[key] = calculated
            return calculated
        except FormulaError as error:
            raise FormulaError(f"{sheet}!{address}: {error}") from error
        finally:
            self._active.pop()

    def _evaluate(self, node: tuple, sheet: str) -> Any:
        kind = node[0]
        if kind == "literal":
            return node[1]
        if kind == "reference":
            target_sheet, target_cell = _reference(node[1], sheet)
            return self.value(target_sheet, target_cell)
        if kind == "range":
            first_sheet, first = _reference(node[1], sheet)
            last_sheet, last = _reference(node[2], first_sheet)
            if first_sheet != last_sheet:
                raise FormulaError("Ranges spanning multiple sheets are unsupported")
            first_column, first_row = _cell_parts(first)
            last_column, last_row = _cell_parts(last)
            if last_column < first_column or last_row < first_row:
                raise FormulaError("Reversed ranges are unsupported")
            if (last_row - first_row + 1) * (last_column - first_column + 1) > 100000:
                raise FormulaError("Range exceeds the supported 100,000-cell limit")
            return RangeValue(
                tuple(
                    self.value(first_sheet, f"{_column_name(column)}{row}")
                    for row in range(first_row, last_row + 1)
                    for column in range(first_column, last_column + 1)
                )
            )
        if kind in {"unary", "percent"}:
            value = self._evaluate(node[2] if kind == "unary" else node[1], sheet)
            if _is_error(value):
                return value
            number = _number(value)
            return number / 100 if kind == "percent" else (-number if node[1] == "-" else number)
        if kind == "function":
            numbers = []
            for argument in node[2]:
                value = self._evaluate(argument, sheet)
                values = value.values if isinstance(value, RangeValue) else (value,)
                for item in values:
                    if _is_error(item):
                        return item
                    if isinstance(item, (int, float)) and not isinstance(item, bool):
                        numbers.append(float(item))
                    elif argument[0] == "literal" and isinstance(item, bool):
                        numbers.append(float(item))
            if node[1] == "SUM":
                return sum(numbers)
            return sum(numbers) / len(numbers) if numbers else "#DIV/0!"
        if kind == "binary":
            operator = node[1]
            left, right = self._evaluate(node[2], sheet), self._evaluate(node[3], sheet)
            if _is_error(left):
                return left
            if _is_error(right):
                return right
            if operator in {"=", "<>", "<", "<=", ">", ">="}:
                # All workbook comparisons are numerical. Preserve text equality too.
                left = 0 if left is None else left
                right = 0 if right is None else right
                if isinstance(left, str) and isinstance(right, str):
                    left, right = left.casefold(), right.casefold()
                comparisons = {
                    "=": lambda: left == right,
                    "<>": lambda: left != right,
                    "<": lambda: left < right,
                    "<=": lambda: left <= right,
                    ">": lambda: left > right,
                    ">=": lambda: left >= right,
                }
                try:
                    return comparisons[operator]()
                except TypeError as error:
                    raise FormulaError("Unsupported comparison of unlike types") from error
            left_number, right_number = _number(left), _number(right)
            if operator == "+":
                return left_number + right_number
            if operator == "-":
                return left_number - right_number
            if operator == "*":
                return left_number * right_number
            if operator == "/":
                return left_number / right_number if right_number else "#DIV/0!"
            if operator == "^":
                try:
                    result = left_number**right_number
                    return (
                        result
                        if isinstance(result, (int, float)) and math.isfinite(result)
                        else "#NUM!"
                    )
                except (OverflowError, ValueError, ZeroDivisionError):
                    return "#NUM!"
        raise FormulaError(f"Unsupported expression node: {kind}")

    def recalculate(self) -> dict[tuple[str, str], Any]:
        """Clear computed results and calculate every formula from its precedents."""
        self._cache.clear()
        return {
            (sheet, address): self.value(sheet, address)
            for sheet, cells in self.sheets.items()
            for address, record in cells.items()
            if "formula" in record
        }

    def verify(self, *, rel_tol: float = 1e-10, abs_tol: float = 1e-6) -> list[dict[str, Any]]:
        """Compare freshly calculated results with Excel's saved results.

        An expected source error is a separate status, never a successful number.
        Unsupported formulas raise FormulaError instead of silently being skipped.
        """
        calculated_values = self.recalculate()
        rows = []
        for (sheet, address), calculated in calculated_values.items():
            record = self.sheets[sheet][address]
            cached = record.get("cached")
            absolute_error = None
            if _is_error(cached) and calculated == cached:
                status = "expected_error"
            elif isinstance(cached, bool) or isinstance(calculated, bool):
                status = (
                    "match"
                    if type(cached) is type(calculated) and cached == calculated
                    else "mismatch"
                )
            elif isinstance(cached, (int, float)) and isinstance(calculated, (int, float)):
                absolute_error = abs(calculated - cached)
                status = (
                    "match"
                    if math.isclose(calculated, cached, rel_tol=rel_tol, abs_tol=abs_tol)
                    else "mismatch"
                )
            elif type(cached) is type(calculated) and cached == calculated:
                status = "match"
            else:
                status = "missing_cache" if cached is None else "mismatch"
            rows.append(
                {
                    "sheet": sheet,
                    "cell": address,
                    "formula": record["formula"],
                    "cached": cached,
                    "calculated": calculated,
                    "status": status,
                    "absolute_error": absolute_error,
                }
            )
        return rows


def summarize_verification(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize parity without combining source errors with valid results."""
    counts = Counter(row["status"] for row in rows)
    return {
        "total": len(rows),
        "formula_count": len(rows),
        "matched": counts["match"],
        "expected_errors": counts["expected_error"],
        "mismatches": counts["mismatch"],
        "missing_cache": counts["missing_cache"],
        "max_absolute_error": max((row["absolute_error"] or 0 for row in rows), default=0),
        "all_accounted_for": counts["mismatch"] == 0 and counts["missing_cache"] == 0,
    }
