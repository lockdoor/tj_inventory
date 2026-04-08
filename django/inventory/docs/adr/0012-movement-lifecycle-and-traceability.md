# ADR 0012: Inventory Movement Lifecycle and Strict Traceability

## Status
Accepted / Implemented

## Context
In the Inventory Movement module, we required a robust mechanism to manage the lifecycle of movement documents and ensure stock traceability. Key requirements included:
1. Preventing documents from being entered if the Lot Number does not exist for Outbound transactions.
2. Allowing users to save Drafts before finalizing (Completing) a transaction.
3. Providing a safe "reversion" path to roll back physical stock changes while maintaining an audit trail.
4. Allowing deletion of Draft documents without breaking historical stock card references.

## Decision
We decided to implement a state-machine based lifecycle and a service-layer validation strategy:

### 1. Multi-Stage Document Status
Each document starts in **Draft** status. 
- **Draft**: Modifiable; no impact on physical stock.
- **Completed**: Immutable; updates physical stock and generates `StockCard` audit entries.
- **Discarded (Deleted)**: Draft documents can be soft-deleted.

### 2. Strict Outbound Lot Validation
Before a `Draft` can even be saved, if the type is `Outbound`, the system performs a real-time check against the `Stock` table. If the Lot Number is not found in the selected Warehouse, the form returns a validation error.

### 3. Service-Layer Orchestration (`MovementService`)
All state transitions are handled in a central service layer within an atomic transaction:
- **`complete_movement`**: Validates, saves, updates balances, and creates audit entries.
- **`revert_to_draft`**: Reverses the effects of a completed movement by adding "Reversal" `StockCard` entries and restoring balances.
- **`delete_draft`**: Soft-deletes the document. Related `StockCard` entries (from previous completions/reversions) persist with `SET_NULL` references to ensure the audit ledger remains intact.

### 4. High-Fidelity Feedback UI
Implemented a "Glassmorphism" design for action buttons and error summaries. Action buttons are status-aware and permission-gated.

## Consequences
- **Integrity**: Physically impossible to withdraw non-existent lots.
- **Auditability**: Every stock correction (reversion) is explicitly logged in the audit trail.
- **User Experience**: Draft-first workflow reduces accidental data entry errors.
- **Maintenance**: Business logic is centralized in the service layer, making it easy to extend for new movement types (e.g., transfers).
