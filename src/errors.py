"""
The application's exception vocabulary.

One class per business rule the system enforces, all inheriting from AppError. They live together in this one file so a menu can catch a specific failure without importing five feature modules, and so the top-level loop in menus/__init__.py can catch AppError as a blanket "the user did something the rules forbid" and print it in red instead of crashing.

Some carry data with them. BidTooLow holds the current highest bid so the menu can say "must exceed $45.00" rather than "bid too low". Feature modules raise these; menu modules catch them. Nothing in here knows anything about terminals or printing.
"""
