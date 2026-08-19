"""
The entry point into the interface: login gate and role dispatch.

Shows the opening menu -- log in, register, quit -- and once auth.py hands back a Session, dispatches on its role to buyer.menu(), seller.menu(), or admin.menu(). main.py calls into here and does nothing else.

This is also where the top-level try/except for AppError lives, so a violated business rule prints one red line and returns to the menu instead of killing the program. Sellers and Admins reach the buyer actions too: the spec lists those as available to every user, with the role privileges layered on top.
"""
