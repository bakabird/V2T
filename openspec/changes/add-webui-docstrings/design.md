## Context

The webui.py module has 6 utility functions that currently have minimal Chinese docstrings:
- `generate_command()` - builds CLI commands from UI inputs
- `parse_urls()` - extracts and deduplicates URLs from text/file
- `parse_hotwords()` - converts hotword input to comma-separated format
- `run_v2t_batch()` - main batch processor with progress updates
- `scan_local_folder()` - finds media files in folders
- `generate_local_command()` - builds CLI commands for local files

## Goals / Non-Goals

**Goals:**
- Add comprehensive English docstrings to all 6 utility functions
- Document parameters with types and descriptions
- Document return values with types
- Follow Python docstring conventions (Google style)

**Non-Goals:**
- Changing function logic or implementation
- Adding type hints to function signatures (only in docstrings)
- Translating other comments in the codebase
- Adding docstrings to non-utility functions or classes

## Decisions

### Decision 1: Use Google-style docstrings

**Rationale:** Google-style docstrings are widely used, readable, and well-supported by documentation tools like Sphinx. They provide clear structure for Args, Returns, and Yields sections.

**Format:**
```python
def function(param1, param2):
    """Brief description.

    Longer description if needed.

    Args:
        param1 (type): Description
        param2 (type): Description

    Returns:
        type: Description
    """
```

### Decision 2: Keep existing Chinese docstrings as additional context

**Rationale:** While replacing with English, the Chinese descriptions provide useful context. We'll keep them as comments above the English docstring where helpful.

### Decision 3: Document generator functions with Yields section

**Rationale:** `run_v2t_batch()` is a generator function. Google-style docstrings have a specific `Yields:` section for documenting generator behavior.
