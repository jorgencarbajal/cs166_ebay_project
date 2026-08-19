"""
Who is currently logged in.

A small dataclass holding the user's login and role, created by auth.py on a successful login or registration and then passed down into the menus. Deliberately not a global -- passing it explicitly makes it obvious which code depends on the current user.

Also home to require_role(), which raises NotAuthorized from errors.py. Feature modules call it directly rather than trusting the menus to hide options, because hiding a menu entry is decoration, not access control.
"""
