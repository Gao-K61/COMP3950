"""Lexer for JACK source files.

The parser can import Lexer and repeatedly call GetNextToken(). End of input
is represented by None. PeekNextToken() returns the same next token without
consuming it, including when called repeatedly. The command line defaults to
the format of the supplied lexer reference files.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Union


class TokenType(str, Enum):
    KEYWORD = "keyword"
    SYMBOL = "symbol"
    IDENTIFIER = "identifier"
    INTEGER_CONSTANT = "integerConstant"
    STRING_CONSTANT = "stringConstant"


KEYWORDS = frozenset(
    {
        "class", "constructor", "function", "method", "field", "static",
        "var", "int", "char", "boolean", "void", "true", "false",
        "null", "this", "let", "do", "if", "else", "while", "return",
    }
)
SYMBOLS = frozenset("{}()[].,;+-*/&|<>=~")
WHITESPACE = frozenset(" \t\r\n\f\v")


@dataclass(frozen=True)
class Token:
    kind: TokenType
    value: str
    lexeme: str
    line: int
    column: int
    reference_line: int


class LexicalError(Exception):
    """A fatal lexical error with a source location and nearby source text."""

    def __init__(self, filename: str, line: int, column: int,
                 near: str, reason: str) -> None:
        self.filename = filename
        self.line = line
        self.column = column
        self.near = near
        self.reason = reason
        super().__init__(
            "{}:{}:{}: lexical error near {!r}: {}".format(
                filename, line, column, near, reason
            )
        )


class Lexer:
    """Scan JACK source text on demand.

    Use Lexer.from_file(path) to read a .jack file.  Direct construction takes
    source *text*, so a path string is never mistaken for JACK source code.
    """

    def __init__(self, source: str, filename: str = "<input>",
                 strict_integer_range: bool = False) -> None:
        self._source = source
        self.filename = filename
        self._index = 0
        self._line = 1
        self._column = 1
        self._reference_line_offset = 0
        self.strict_integer_range = strict_integer_range
        self._lookahead = None  # type: Optional[Token]
        self._failure = None  # type: Optional[LexicalError]

    @classmethod
    def from_file(cls, path: Union[str, Path],
                  strict_integer_range: bool = False) -> "Lexer":
        file_path = Path(path)
        return cls(file_path.read_text(encoding="utf-8"), str(file_path),
                   strict_integer_range)

    @property
    def reference_line(self) -> int:
        """Line number used by the supplied lexer output files."""
        return self._line - self._reference_line_offset

    def PeekNextToken(self) -> Optional[Token]:
        if self._failure is not None:
            raise self._failure
        if self._lookahead is None:
            try:
                self._lookahead = self._scan_token()
            except LexicalError as error:
                self._failure = error
                raise
        return self._lookahead

    def GetNextToken(self) -> Optional[Token]:
        token = self.PeekNextToken()
        self._lookahead = None
        return token

    def _at_end(self) -> bool:
        return self._index >= len(self._source)

    def _current(self) -> str:
        return "" if self._at_end() else self._source[self._index]

    def _advance(self) -> str:
        """Consume one character, treating CRLF as one newline."""
        char = self._source[self._index]
        self._index += 1
        if char == "\r":
            if self._current() == "\n":
                self._index += 1
            self._line += 1
            self._column = 1
            return "\n"
        if char == "\n":
            self._line += 1
            self._column = 1
        else:
            self._column += 1
        return char

    def _error(self, reason: str, line: int, column: int,
               start: int) -> None:
        end = min(len(self._source), max(self._index + 1, start + 1), start + 40)
        near = self._source[start:end]
        if not near:
            near = "<end of file>"
        raise LexicalError(self.filename, line, column, near, reason)

    def _skip_ignored(self) -> None:
        while not self._at_end():
            if self._current() in WHITESPACE:
                self._advance()
            elif self._source.startswith("//", self._index):
                self._advance()
                self._advance()
                while not self._at_end() and self._current() not in "\r\n":
                    self._advance()
            elif self._source.startswith("/*", self._index):
                start = self._index
                first_line = self._line
                documentation_comment = self._source.startswith("/**", start)
                self._advance()
                self._advance()
                while not self._at_end() and not self._source.startswith(
                    "*/", self._index
                ):
                    self._advance()
                if self._at_end():
                    self._error("unterminated block comment", self._line,
                                self._column, start)
                self._advance()
                self._advance()
                # The supplied output omits one line for each multi-line
                # documentation comment. Keep physical locations in Token.line.
                if documentation_comment and self._line > first_line:
                    self._reference_line_offset += 1
            else:
                return

    @staticmethod
    def _is_letter(char: str) -> bool:
        return "a" <= char <= "z" or "A" <= char <= "Z"

    @classmethod
    def _is_identifier_part(cls, char: str) -> bool:
        return cls._is_letter(char) or "0" <= char <= "9" or char == "_"

    def _scan_token(self) -> Optional[Token]:
        self._skip_ignored()
        if self._at_end():
            return None

        start, line, column = self._index, self._line, self._column
        char = self._current()

        if char in SYMBOLS:
            self._advance()
            return Token(TokenType.SYMBOL, char, char, line, column,
                         self.reference_line)

        if char == '"':
            self._advance()
            content_start = self._index
            while not self._at_end() and self._current() != '"':
                if self._current() in "\r\n":
                    self._error("newline in string constant", line, column, start)
                self._advance()
            if self._at_end():
                self._error("unterminated string constant", line, column, start)
            value = self._source[content_start:self._index]
            self._advance()
            return Token(TokenType.STRING_CONSTANT, value,
                         self._source[start:self._index], line, column,
                         self.reference_line)

        if "0" <= char <= "9":
            while "0" <= self._current() <= "9":
                self._advance()
            if self._is_identifier_part(self._current()):
                while self._is_identifier_part(self._current()):
                    self._advance()
                self._error("identifier cannot start with a digit", line,
                            column, start)
            lexeme = self._source[start:self._index]
            significant = lexeme.lstrip("0") or "0"
            if self.strict_integer_range and (len(significant) > 5 or
                    (len(significant) == 5 and significant > "32767")):
                self._error("integer constant exceeds 32767", line,
                            column, start)
            return Token(TokenType.INTEGER_CONSTANT, lexeme, lexeme,
                         line, column, self.reference_line)

        if self._is_letter(char) or char == "_":
            while self._is_identifier_part(self._current()):
                self._advance()
            lexeme = self._source[start:self._index]
            kind = (TokenType.KEYWORD if lexeme in KEYWORDS
                    else TokenType.IDENTIFIER)
            return Token(kind, lexeme, lexeme, line, column,
                         self.reference_line)

        self._error("invalid character in JACK source", line, column, start)
        raise AssertionError("unreachable")


REFERENCE_KINDS = {
    TokenType.KEYWORD: "RESWORD",
    TokenType.SYMBOL: "SYMBOL",
    TokenType.IDENTIFIER: "ID",
    TokenType.INTEGER_CONSTANT: "INT",
    TokenType.STRING_CONSTANT: "STRING",
}
REFERENCE_ERRORS = {
    "unterminated block comment": "Error: unexpected eof in comment",
    "unterminated string constant": "Error: unexpected eof in string constant",
    "newline in string constant": "Error: new line in string constant",
    "invalid character in JACK source": "Error: illegal symbol in source file",
}


def _reference_record(filename: str, line: int, value: str,
                      kind: str) -> str:
    return "< {}, {}, {}, {} >".format(filename, line, value, kind)


def main() -> int:
    parser = argparse.ArgumentParser(description="Print JACK lexer tokens")
    parser.add_argument("path", type=Path, help="a .jack file or a directory of .jack files")
    parser.add_argument("--format", choices=("reference", "json"),
                        default="reference", help="output format (default: reference)")
    parser.add_argument("--strict-integers", action="store_true",
                        help="reject integer constants greater than 32767")
    args = parser.parse_args()
    path = args.path
    if path.is_dir():
        files = sorted(path.glob("*.jack"))
        if not files:
            parser.error("directory contains no .jack files")
    elif path.is_file() and path.suffix.lower() == ".jack":
        files = [path]
    else:
        parser.error("path must be a .jack file or directory")

    try:
        for file_path in files:
            lexer = Lexer.from_file(file_path, args.strict_integers)
            while True:
                try:
                    token = lexer.GetNextToken()
                except LexicalError as error:
                    if args.format == "reference":
                        print(_reference_record(
                            file_path.name,
                            error.line - lexer._reference_line_offset,
                            REFERENCE_ERRORS.get(error.reason, "Error: " + error.reason),
                            "ERR",
                        ))
                    else:
                        print(error, file=sys.stderr)
                    return 1
                if token is None:
                    break
                if args.format == "reference":
                    print(_reference_record(file_path.name, token.reference_line,
                                            token.value, REFERENCE_KINDS[token.kind]))
                else:
                    print(json.dumps({
                        "file": str(file_path),
                        "line": token.line,
                        "column": token.column,
                        "kind": token.kind.value,
                        "value": token.value,
                        "lexeme": token.lexeme,
                    }, ensure_ascii=True))
            if args.format == "reference":
                print(_reference_record(file_path.name, lexer.reference_line,
                                        "End of File", "EOFile"))
    except (OSError, UnicodeError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
