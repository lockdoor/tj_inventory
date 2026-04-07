# ADR 0009: Inventory Movement Creation Pattern

## Status
Accepted

## Context
Following the implementation of the Movement List and Detail views (ADR 0007, 0008), we require a robust and consistent method for users to create new Inbound and Outbound transactions. These transactions are complex, requiring a header document and multiple line items.

## Decision
We will implement the **Movement Creation** module using a unified Header + Line-Item FormSet approach.

### 1. View Architecture
- Use `django.views.generic.CreateView` (documented as `MovementCreateView`).
- Permission: `inventory.add_inventorymovement`.
- Integration with `MovementService` to ensure consistency with the business logic.

### 2. Transaction Integrity Rules
- **No Empty Movements**: A document cannot be saved without at least one transaction item. This will be enforced at the FormSet validation level.
- **Draft-First Workflow**: All newly created movements will default to `Draft` status. This allows users to double-check their entry before "Completing" the movement (which triggers stock balance impacts and immutable ledger entries).

### 3. UI/UX Consistency
- All naming conventions must use the word **"Create"** (e.g., "Create Movement", `movement_create.html`).
- **Premium Interface**: Use the project's Emerald Green glassmorphism tokens.
- **Dynamic Items**: Use Vanilla JavaScript to manage formset rows (Add/Remove) on the client side for a seamless experience.

## Consequences
- **Positive**: High data integrity; users cannot accidentally impact stock without a draft review.
- **Positive**: Clean, modern interface consistent with the rest of the Inventory module.
- **Negative**: Increased complexity in the form handling layer (parent/child relationships).
- **Negative**: Requires careful management of Django FormSet logic for dynamic row addition.

## Alternatives Considered
- **Step-by-Step Creation**: Create header first, then redirect to an item addition page.
  - *Rejected*: Slower user experience for standard operations.
- **Modals for Items**: Use modals to add items to a draft.
  - *Rejected*: Breaks the visual flow of a "document" entry.
