# Remove Unique Constraint from InventoryMovement `document_no`

This plan outlines the steps required to remove the `unique=True` constraint from the `document_no` field on the `InventoryMovement` model. Because `document_no` is currently heavily utilized as a unique identifier across the system (URLs, Views, Templates, and Tests), we will need to refactor the entire CRUD pipeline to operate using the model's primary key (`pk` / `id`) instead.

## User Review Required

> [!WARNING]
> By removing the unique constraint on `document_no`, it will be possible to have multiple movement documents with the exact same number. You should confirm if there are any downstream ledger or accounting systems that implicitly rely on `document_no` being globally unique for reconciliation.

## Proposed Changes

### Model Level

#### [MODIFY] movement.py
- **File**: `django/srcs/inventory/models/movement.py`
- **Action**: Remove `unique=True` from the `document_no` field definition. 
- **Action**: Generate and apply the Django migration using `makemigrations`.

### URL Routing

#### [MODIFY] urls.py
- **File**: `django/srcs/inventory/urls.py`
- **Action**: Replace all occurrences of `<str:document_no>` with `<int:pk>` in movement-related paths (e.g., `movements/<int:pk>/`, `movements/<int:pk>/update/`, `movements/<int:pk>/restore/`).

### Views & Controllers

#### [MODIFY] movement_views.py
- **File**: `django/srcs/inventory/views/movement_views.py`
- **Action**: Remove the `slug_field = 'document_no'` and `slug_url_kwarg = 'document_no'` properties from all class-based views (`MovementDetailView`, `MovementUpdateView`, etc.). Django views will default back to resolving by `pk`.
- **Action**: In `post` methods like `MovementRestoreView` and `MovementHardDeleteView`, update arguments from `(self, request, document_no)` to `(self, request, pk)` and query using `pk=pk`.
- **Action**: Update all redirect calls: `redirect('inventory:movement-detail', document_no=movement.document_no)` -> `redirect('inventory:movement-detail', pk=movement.pk)`.

#### [MODIFY] attachment_views.py
- **File**: `django/srcs/inventory/views/attachment_views.py`
- **Action**: Update `MovementAttachmentUploadView.post(self, request, document_no)` to use `pk`.
- **Action**: Update redirects back to `movement-detail` to use `pk`.

### Templates

#### [MODIFY] movement_list.html
- **File**: `django/srcs/inventory/templates/inventory/movement_list.html`
- **Action**: Change URL tag resolution from `{% url 'inventory:movement-detail' movement.document_no %}` to `{% url 'inventory:movement-detail' movement.pk %}`.

#### [MODIFY] movement_trash_list.html
- **File**: `django/srcs/inventory/templates/inventory/movement_trash_list.html`
- **Action**: Update URL tags for `restore` and `hard-delete` to pass `movement.pk`. Update the modal javascript invocation `openDeleteModal(...)` to pass the `pk` for form submission.

#### [MODIFY] stockcard_detail.html
- **File**: `django/srcs/inventory/templates/inventory/stockcard_detail.html`
- **Action**: Change `{% url 'inventory:movement-detail' stockcard.movement_item.movement.document_no %}` to use `movement.pk`.

### Tests

#### [MODIFY] test_movement_views.py
- **File**: `django/srcs/tests/inventory/views/test_movement_views.py`
- **Action**: Update all URL resolving assertions from `kwargs={'document_no': movement.document_no}` to `kwargs={'pk': movement.pk}`.
- **Action**: Update explicit queries like `InventoryMovement.objects.get(document_no='...')` to utilize the movement's tracked `pk` to avoid `MultipleObjectsReturned` exceptions.

#### [MODIFY] Services & Model Tests
- **Files**: `test_movement_service.py`, `test_movement_completion.py`, `test_movement.py`
- **Action**: Adjust any test cases specifically designed to assert `IntegrityError` upon duplicate `document_no` insertions, as this will no longer raise an error.

## Verification Plan

### Automated Tests
- Run `pytest django/srcs/tests/inventory/` to verify all views, endpoints, and services successfully execute without slug/kwargs routing errors.

### Manual Verification
- Manually create two inventory movements and force them to have the exact same `document_no` via the UI or backend.
- Verify that both documents can be accessed individually (via their separate integer IDs in the URL) without collision or 500 errors.
