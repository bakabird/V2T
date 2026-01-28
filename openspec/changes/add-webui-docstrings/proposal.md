## Why

The webui.py module contains utility functions with only brief Chinese docstrings. English docstrings with parameter descriptions and return type documentation would improve code maintainability and make the codebase more accessible to international contributors.

## What Changes

- Replace minimal Chinese docstrings with comprehensive English docstrings
- Document all parameters with types and descriptions
- Document return values and their types
- Follow Python docstring conventions (Google/NumPy style)

## Capabilities

### New Capabilities
<!-- No new capabilities - this is documentation improvement only -->

### Modified Capabilities
- `webui-documentation`: Update documentation for 6 utility functions (generate_command, parse_urls, parse_hotwords, run_v2t_batch, scan_local_folder, generate_local_command) to include English descriptions, parameter specs, and return value documentation

## Impact

- `webui.py`: Update docstrings for 6 functions (lines ~14-300)
