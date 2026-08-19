"""
Everything the user sees.

The only module in the project that imports rich. It holds the shared console, the success/error/warn/info helpers, a table() that renders the dict_row dictionaries feature modules return, a numbered menu(), and prompt helpers that re-ask on bad input instead of crashing.

Money is NUMERIC(10,2) in the schema, so the prompts return Decimal and never float -- that conversion happens here once rather than being reinvented in six modules. Menu modules import this freely; feature modules must not import it at all.
"""
