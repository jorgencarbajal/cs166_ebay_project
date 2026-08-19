"""
Registration and login.

register() inserts a new row into users and returns a Session; login() checks credentials and returns a Session. Both raise from errors.py on failure -- LoginTaken and BadCredentials respectively.

New accounts are always Buyer. The schema defaults the column and only an Admin can change a role afterwards, so register() deliberately accepts no role argument. Called only from menus/__init__.py, before any role menu exists to dispatch to.
"""
