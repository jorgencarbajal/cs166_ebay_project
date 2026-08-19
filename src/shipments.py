"""
The shipment table: delivery after payment.

Creating a shipment requires a Completed payment for that auction -- the spec defines shipment as delivery after payment completion -- so this module checks payments.py's state first and raises PaymentIncomplete when it is not there yet.

The address defaults to the winning buyer's users.address but can be overridden. Statuses are Pending, Shipped, and Delivered, with an optional tracking number. Only the auction's seller may create or update one, though buyers can read the status of what they bought. Used by menus/seller.py, and read from menus/buyer.py.
"""
