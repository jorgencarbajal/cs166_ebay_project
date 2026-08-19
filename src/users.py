"""
The users table: profiles and administration.

Covers a user viewing and editing their own profile -- everything except login and role, which the spec forbids changing -- plus the admin-only work of listing users, inspecting one in detail, and changing someone's role.

The role change is the hardest operation in the project. The schema's composite (login, role) foreign keys cascade a role update into every dependent row and then trip the CHECK that pins it, so changing a role is only safe when the user owns no items, bids, or payments. Read docs/architecture.md before touching it. Used by menus/buyer.py for profiles and menus/admin.py for the rest.
"""
