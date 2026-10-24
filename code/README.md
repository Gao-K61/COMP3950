# JACK Lexer

`lexer.py` scans JACK source files and exposes the two required operations:

```python
from lexer import Lexer

lexer = Lexer.from_file("Main.jack")
next_token = lexer.PeekNextToken()  # inspect without consuming
next_token = lexer.GetNextToken()   # consume the same token
```

The methods return `None` at the end of the file. Each `Token` provides
`kind`, `value`, `lexeme`, `line`, and `column`. String token values omit the
surrounding quotes; all other values match their source text. A lexical error
raises `LexicalError` with a file name, line, column, nearby source text, and
reason. Once an error occurs, later calls raise that same error.

To inspect a source file or all `.jack` files directly inside a directory:

```text
python code/lexer.py path/to/Main.jack
python code/lexer.py path/to/source_directory
```

The command prints one JSON object per token and exits with status 1 on an
error. The parser can import the module directly, without parsing this output.

Run the local regression checks with:

```text
python -B -m unittest discover -s code -p "test_*.py"
```
