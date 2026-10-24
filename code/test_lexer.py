"""Focused regression checks for the JACK lexer."""

import unittest

from lexer import KEYWORDS, SYMBOLS, Lexer, LexicalError, TokenType


def scan(source):
    lexer = Lexer(source)
    result = []
    while True:
        token = lexer.GetNextToken()
        if token is None:
            return result
        result.append(token)


class LexerTests(unittest.TestCase):
    def test_all_keywords_and_symbols(self):
        source = " ".join(sorted(KEYWORDS)) + " " + " ".join(sorted(SYMBOLS))
        tokens = scan(source)
        self.assertEqual(
            [(token.kind, token.value) for token in tokens],
            [(TokenType.KEYWORD, word) for word in sorted(KEYWORDS)]
            + [(TokenType.SYMBOL, symbol) for symbol in sorted(SYMBOLS)],
        )

    def test_comments_strings_and_positions(self):
        tokens = scan(
            'class Main { // comment\r\n'
            '  /* across\n lines */ let s = "// not a comment";\n'
            '  /** doc */ let n = 32767; }'
        )
        self.assertEqual(
            [(token.kind, token.value) for token in tokens],
            [
                (TokenType.KEYWORD, "class"),
                (TokenType.IDENTIFIER, "Main"),
                (TokenType.SYMBOL, "{"),
                (TokenType.KEYWORD, "let"),
                (TokenType.IDENTIFIER, "s"),
                (TokenType.SYMBOL, "="),
                (TokenType.STRING_CONSTANT, "// not a comment"),
                (TokenType.SYMBOL, ";"),
                (TokenType.KEYWORD, "let"),
                (TokenType.IDENTIFIER, "n"),
                (TokenType.SYMBOL, "="),
                (TokenType.INTEGER_CONSTANT, "32767"),
                (TokenType.SYMBOL, ";"),
                (TokenType.SYMBOL, "}"),
            ],
        )
        self.assertEqual((tokens[3].line, tokens[3].column), (3, 11))
        self.assertEqual((tokens[8].line, tokens[8].column), (4, 14))
        self.assertEqual(tokens[6].lexeme, '"// not a comment"')

    def test_peek_get_and_end_of_file(self):
        lexer = Lexer("let x")
        first = lexer.PeekNextToken()
        self.assertIs(first, lexer.PeekNextToken())
        self.assertIs(first, lexer.GetNextToken())
        self.assertEqual(lexer.GetNextToken().value, "x")
        self.assertIsNone(lexer.PeekNextToken())
        self.assertIsNone(lexer.PeekNextToken())
        self.assertIsNone(lexer.GetNextToken())

    def test_empty_file_and_line_comment_at_eof(self):
        self.assertEqual(scan(" \r\n// comment"), [])

    def test_errors_stop_scanning_with_location_and_reason(self):
        cases = [
            ('"unfinished', "unterminated string constant"),
            ('"line\nend"', "newline in string constant"),
            ("/* unfinished", "unterminated block comment"),
            ("32768", "exceeds 32767"),
            ("9" * 5000, "exceeds 32767"),
            ("123abc", "cannot start with a digit"),
            ("@", "invalid character"),
        ]
        for source, reason in cases:
            with self.subTest(source=source):
                lexer = Lexer(source, "bad.jack")
                with self.assertRaises(LexicalError) as caught:
                    lexer.PeekNextToken()
                error = caught.exception
                self.assertEqual((error.filename, error.line, error.column),
                                 ("bad.jack", 1, 1))
                self.assertIn(reason, str(error))
                self.assertTrue(error.near)
                with self.assertRaises(LexicalError) as repeated:
                    lexer.GetNextToken()
                self.assertIs(error, repeated.exception)

    def test_error_after_previous_valid_token(self):
        lexer = Lexer("let\r\n@")
        self.assertEqual(lexer.GetNextToken().value, "let")
        with self.assertRaises(LexicalError) as caught:
            lexer.GetNextToken()
        self.assertEqual((caught.exception.line, caught.exception.column), (2, 1))


if __name__ == "__main__":
    unittest.main()
