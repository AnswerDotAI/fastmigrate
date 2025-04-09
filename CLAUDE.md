# CLAUDE.md - Guidelines for fastmigrate

## Build/Test Commands
- Install: `pip install -e .`  
- Run: `python -m fastmigrate`
- Run with args: `python -m fastmigrate --db path/to/db --migrations path/to/migrations`
- Tests: `pytest`
- Single test: `pytest tests/path/to/test.py::test_function`
- Type check: `mypy .`

## Code Style Guidelines
- **Imports**: Sort imports with isort. Standard lib → third party → local.
- **Types**: Use type hints for all function parameters and return values.
- **Naming**: snake_case for variables/functions, PascalCase for classes.
- **Error handling**: Use specific exceptions, document them in docstrings.
- **Comments**: Docstrings for all public functions/classes (Google style).
- **SQL**: Uppercase SQL keywords, use parameterized queries for safety.