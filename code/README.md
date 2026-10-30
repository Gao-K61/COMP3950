# JACK Lexer

`lexer.py` scans JACK source files and exposes the two required operations:

```python
from lexer import Lexer

lexer = Lexer.from_file("Main.jack")
next_token = lexer.PeekNextToken()  # inspect without consuming
next_token = lexer.GetNextToken()   # consume the same token
```

The methods return `None` at the end of the file. Each `Token` provides
`kind`, `value`, `lexeme`, `line`, `column`, and `reference_line`. String token values omit the
surrounding quotes; all other values match their source text. A lexical error
raises `LexicalError` with a file name, line, column, nearby source text, and
reason. Once an error occurs, later calls raise that same error.

`line` is the physical source line. `reference_line` reproduces the supplied
lexer output files, which count one fewer line after a multi-line `/** ... */`
comment. By default, digit sequences such as `78658996` are classified as
integer tokens to match those files. Pass `strict_integer_range=True` to the
constructor or `from_file` to reject values greater than 32767.

To inspect a source file or all `.jack` files directly inside a directory:

```text
python code/lexer.py path/to/Main.jack
python code/lexer.py path/to/source_directory
python code/lexer.py path/to/Main.jack --format json
```

The default command prints the supplied reference format, including `EOFile`
or `ERR`. `--format json` retains one JSON object per token. The command exits
with status 1 on an error. The parser can import the module directly.

Run the local regression checks with:

```text
python -B -m unittest discover -s code -p "test_*.py"
```
