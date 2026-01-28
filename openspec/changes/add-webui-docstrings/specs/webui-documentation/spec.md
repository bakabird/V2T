## ADDED Requirements

### Requirement: Comprehensive English Docstrings

All utility functions in webui.py must have comprehensive English docstrings that include function description, parameter documentation with types, and return value documentation.

#### Scenario: Function docstring includes description

- **WHEN** a developer reads a utility function in webui.py
- **THEN** the docstring must contain a clear English description of what the function does
- **AND** the description must be more detailed than the existing Chinese one-liner

#### Scenario: Function docstring documents all parameters

- **WHEN** a developer reads a utility function's docstring
- **THEN** all parameters must be documented with their expected types
- **AND** each parameter must have a description explaining its purpose
- **AND** optional parameters must be marked as such

#### Scenario: Function docstring documents return value

- **WHEN** a function returns a value
- **THEN** the docstring must document the return type
- **AND** the docstring must describe what the return value represents
- **AND** for generator functions, the yield type and behavior must be documented

#### Scenario: Docstrings follow Python conventions

- **WHEN** a docstring is written
- **THEN** it must follow standard Python docstring format (Google or NumPy style)
- **AND** it must use proper indentation and formatting
- **AND** multi-line descriptions must be properly formatted
