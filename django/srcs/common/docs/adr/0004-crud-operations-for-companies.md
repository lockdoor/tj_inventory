# ADR 0004: CRUD Operations for Companies

**Status:** Accepted  
**Date:** 2026-06-30  

## Context

Following the introduction of the centralized `Company` database model (ADR 0003), we need to implement a secure, easy-to-use, and visually consistent management interface (CRUD) for internal corporate entities.

The implementation must maintain code modularity (separating business logic from views), enforce role-based permissions, check references before allowing deletion, and follow the premium glassmorphism styling conventions of the application.

## Decision

We built the CRUD operations using the Service Layer pattern and Django Class-Based Views:

1. **Service Layer Isolation**:
   All database operations and business rules are encapsulated in `CompanyService` ([company_service.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/common/services/company_service.py)). This keeps views clean, thin, and focused solely on HTTP handling and authorization.

2. **Validation on Soft-Delete**:
   In `CompanyService.soft_delete`, we added validation logic preventing the soft-deletion of a company if there are active (non-deleted) warehouses linked to it. This maintains referential integrity:
   ```python
   if company.warehouses.filter(is_deleted=False).exists():
       raise ValidationError("Cannot delete company because it is referenced by active warehouses.")
   ```

3. **Secure Class-Based Views**:
   Views are defined in [company_views.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/common/views/company_views.py) and check standard Django permission codenames:
   - `common.view_company` (List, Detail)
   - `common.add_company` (Create)
   - `common.change_company` (Update)
   - `common.delete_company` (Delete, Trash, Restore)
   `CompanyDeleteView` catches `ValidationError` raised during deletion, displaying a user-facing error toast instead of crashing.

4. **URL Routing and Navigation**:
   - Company views are routed directly at root-level (`/companies/`) in [app/urls.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/app/urls.py).
   - A new **Company Directory** module card was integrated into the Executive Dashboard context.

5. **Form Required Indicators**:
   In [company_form.html](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/common/templates/common/company_form.html), required field labels (Company Name, Code, and Status) display a red asterisk (`*`) for visual cues.

## Consequences

### Positive
* **Decoupled Architecture**: Logic is cleanly separated between models, forms, services, and views, simplifying unit-testing.
* **Referential Integrity**: Companies cannot be deleted if active warehouses remain linked to them.
* **Cleaner Navigation**: Routing is direct at the root domain `/companies/`, matching modules like `/partners/`.
* **Enhanced UX**: Clear required field indicators and user-friendly error toasts for validation failures.
