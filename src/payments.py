"""
The payment table: paying for a won auction.

A payment is only valid when the auction is Closed and the winner is this buyer, so this module checks both and raises NotWinner otherwise. payment.auction_id is UNIQUE, which means the database itself enforces one payment per auction -- a second attempt raises AlreadyPaid.

Statuses are Pending, Completed, and Failed, fixed by a CHECK in the schema. The amount defaults to the winning bid rather than being freely typed. shipments.py depends on this: nothing ships until its payment reads Completed. Used by menus/buyer.py.
"""
