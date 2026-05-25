# ADR 0003: Interactive Sales Order Creation and Alternative Packaging

## Status
Accepted (2026-05-25)

## Context
Creating sales orders in traditional ERPs is often tedious and error-prone. Users have to manually research inventory availability, lots, and calculate multi-unit conversions (e.g., converting Cartons or Boxes to individual pieces) before keying in data.
* **Shopping Cart Metaphor**: We require a modern, high-fidelity experience featuring:
  1. **Header Form (Step 1)**: Basic metadata (Customer, Date, Doc No, Note).
  2. **Catalog & Cart Workspace (Step 2)**: An elegant sidebar interface with a searchable product catalog on the left and a sticky, live-calculated shopping cart on the right.
* **Alternative Packaging (Catalog Integration)**: Products may have alternative packaging configurations (defined in `catalog.ItemPackaging`) mapping packaging names (e.g., Carton, Box, Dozen) to base unit multipliers (e.g., 12 pcs).
* **Database & Schema Constraints**: The backend core data models (`SalesOrderItem`) must store raw quantities and unit prices only in base pieces. Migrating database tables or changing this schema introduces high risk and breaks backward compatibility with other fulfillment services.
* **Type Safety**: Float arithmetic introduces rounding errors in financial and inventory accounting. The system must enforce strict Decimal type safety across the database and service boundaries, avoiding fatal Python operand exceptions during allocation runs.

## Decision
We implement a fully client-side quantized **Interactive Sales Order Creator** supporting alternative item packagings, unified by robust Decimal type safety and failure-recovery rehydration.

### 1. Dynamic Client-Side Conversion Architecture
To maintain a clean, flat database schema, all packaging calculations are resolved in the browser before data reaches the backend:
* **Base Normalization**: When adding an item to the cart, the frontend translates entered quantities and prices into base pieces:
  * $\text{requested\_qty} = \text{entered\_qty} \times \text{package\_multiplier}$
  * $\text{unit\_price} = \text{entered\_price} \div \text{package\_multiplier}$
* **Dynamic Price Scaling**: Selecting a packaging dropdown proportionally updates the price input field. For example, if pieces are $10.00 each, switching to a Box (12 pcs) automatically sets the price input to $120.00, keeping the piece-level value consistent while letting users think in package-level numbers.
* **Micro-Conversion Explanations**: A live calculation label (`pkg-calc-${itemId}`) updates in real-time as users type (e.g., `2 Box = 24 pcs at $10.00 / pcs`), giving sales reps visual confidence.

### 2. Premium Sidebar Cart Experience
The cart sidebar updates dynamically without page reloads using vanilla JS event delegation:
* **Package Stepping**: Plus/Minus buttons in the cart detect if an item was added as a package. If so, they increment or decrement by the package's multiplier (e.g., clicking `+` on a Box of 12 increases the base quantity by 12 and the package quantity by 1) for a premium checkout experience.
* **Parallel Price Indicators**: Renders the packaging details (e.g. `Packaged: 2 Box (24 pcs)`) next to the SKU, and lists the calculated package price (e.g. `($120.00 / Box)`) under the editable unit price field.

### 3. Failure Recovery & Automatic Rehydration
If a `POST` request fails validation (e.g., missing header field), the system must preserve the user's cart state upon reload:
* The raw cart array is serialized into a hidden script block and reload-parsed in the frontend.
* **Multi-Unit Scanning**: The rehydration engine scans the item's configured packagings descending by multiplier size. If the cart's base quantity divides perfectly by a packaging multiplier, it automatically reconstructs the packaging name, package quantity, and package indicators.

### 4. Coercion for Decimal Type Safety
To avoid fatal Python operand exceptions (`unsupported operand type(s) for -=: 'float' and 'decimal.Decimal'`) when the smart allocation engine runs lot calculations:
* **View Layer**: The JSON parser inside `SalesOrderCreateView` in `sales_order_views.py` coerces parsed quantities and prices to `decimal.Decimal` objects instead of `float`.
* **Service Layer Boundary**: `SalesService.add_item` in `sales_service.py` explicitly casts parameters using `Decimal(str(val))` before creating the `SalesOrderItem` record, locking in type safety across all system modules.

## Consequences
* **Positive**: Zero database migrations or schema alterations required, preserving full backward compatibility.
* **Positive**: Exceptional checkout-style user experience with real-time conversions and micro-animations.
* **Positive**: Zero floating-point arithmetic drift or type safety conflicts in inventory allocation runs.
* **Negative**: Requires loading raw catalog variables into the HTML context for client-side calculations, slightly increasing initial GET response sizes.
