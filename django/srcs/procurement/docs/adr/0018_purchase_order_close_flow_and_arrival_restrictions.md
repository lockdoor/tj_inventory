# ADR 0018: Purchase Order Close Flow and Arrival Reference Restrictions

## Status
Accepted (2026-06-12)

## Context
A Purchase Order (PO) represents an agreement with a supplier. When goods are delivered, they are logged as Arrivals.
* **Terminal Closure**: Once a PO is fully fulfilled (all arrivals have arrived and quantities match) or is administratively concluded (supplier is out of stock, PO is partially received but must be closed), it needs to transition to a terminal `CLOSED` state.
* **Prevent Stale Shipments**: A closed PO must not accept any new Arrivals. Linking new arrivals to closed POs leads to data inconsistencies and inventory tracking issues.
* **Accidental Close Actions**: Because closing a PO is a terminal state that blocks further shipments, it is a high-risk operation. The UI must explicitly warn the user and require verification before allowing closure, with visual indications of whether the closure is expected (fully fulfilled) or forced (partially fulfilled).

## Decision
We implemented a terminal status close flow for Purchase Orders, combined with validation constraints on the Arrival model to prevent linking shipments to closed POs.

### 1. Purchase Order Closed Status and Sufficiency
* **Terminal Status**: Added `CLOSED` (`'closed'`) to `PurchaseOrder.Status`. Once a PO is closed, it cannot transition to any other status.
* **Fulfillment Sufficiency**: Added an `is_sufficient` property to the `PurchaseOrder` model:
  ```python
  @property
  def is_sufficient(self):
      for item in self.items.all():
          if item.arrival_pieces < item.order_pieces:
              return False
      return True
  ```
  This returns `True` only if all items have active arrival pieces meeting or exceeding ordered pieces.

### 2. Action Button and Verification Modal
* **Fulfillment-Aware Actions**: The "Close Order" button is shown on the PO detail page if its status is `submitted`. The button styling adapts:
  - **Sufficient (Green)**: Emerald background (`#10b981`) and check icon indicating a successful close.
  - **Insufficient (Red)**: Rose background (`#ef4444`) and warning icon indicating a force-close.
* **Centered Verification Modal**: Clicking "Close Order" opens a custom centered glassmorphic modal (`#close-po-modal`).
* **Document Number Verification**: The modal requires the user to type the PO's exact `document_no` into a text field to enable the "Close PO" submit button, mitigating accidental clicks.

### 3. Arrival Reference Gating
* **Model Validation**: Overrode `clean()` on the `Arrival` model to validate that the referenced PO status is not `CLOSED`:
  ```python
  def clean(self):
      super().clean()
      if self.purchase_order and self.purchase_order.status == self.purchase_order.Status.CLOSED:
          is_new = self.pk is None
          if is_new:
              raise ValidationError({'purchase_order': "Cannot reference a Closed Purchase Order."})
          else:
              orig = Arrival.objects.filter(pk=self.pk).first()
              if orig and orig.purchase_order_id != self.purchase_order_id:
                  raise ValidationError({'purchase_order': "Cannot reference a Closed Purchase Order."})
  ```
* **Form Filter**: The `ArrivalForm`'s `purchase_order` field queryset is filtered to only include `SUBMITTED` POs, naturally hiding closed ones from selection lists.

## Consequences
* **Positive**: Enforces a strict procurement lifecycle where closed POs are locked.
* **Positive**: Adaptable UI color-coding clearly distinguishes between expected fulfillment and force-closures.
* **Positive**: Input verification prevents accidental terminal operations.
* **Positive**: Double-layered validation (form and model layer) secures database integrity against incorrect links.
