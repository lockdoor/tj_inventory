# ADR 0005: CRUD Operations for Individuals

**Status:** Accepted  
**Date:** 2026-07-01  

## Context

To support internal payees (custodians, employees) and outer contacts without cluttering authentication user entities, we introduced a centralized `Individual` model. We needed a comprehensive CRUD management registry that supports bilingual identity info (Thai and English names), stores multiple phone numbers cleanly, prevents multiple people profiles from binding to the same system user, and renders with premium glassmorphism layouts.

## Decision

We designed and built the `Individual` CRUD interface using the Service Layer pattern and Django Class-Based Views:

1. **Bilingual Name & Nickname Support**:
   The model supports both local (Thai) and international (English) name attributes:
   - `first_name_th` & `last_name_th` (Required, with fallback defaults).
   - `first_name_en` & `last_name_en` (Optional).
   - `nickname` (Optional, can be in Thai or English).
   - A `@property def full_name(self)` returns the primary Thai full name and nickname in bracket format (e.g., `สมชาย ดีใจ (สม)`), which is displayed in page titles and navigation breadcrumbs instead of raw database IDs.

2. **Cross-Database Array Compatability (phones JSONField)**:
   Instead of using PostgreSQL-specific `ArrayField`, we stored phone lists in a Django `JSONField` initialized to empty lists. This allows the system to run on both SQLite (local development and test suites) and PostgreSQL (production database) without modifications.

3. **User Choice Constraint & Phones Parser**:
   In `IndividualForm` ([individual_form.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/common/forms/individual_form.py)):
   - **Phones Field**: Exposed as a comma-separated TextInput. On save, `clean_phones()` strips whitespace and splits the values into a list of strings.
   - **User Dropdown**: Filters out any authentication users who are already linked to other `Individual` records, protecting database integrity.

4. **Service & View Separation**:
   Encapsulated database operations inside `IndividualService` ([individual_service.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/common/services/individual_service.py)). The views in `individual_views.py` handle HTTP routing and verify Django permissions:
   - `common.view_individual` (List, Detail)
   - `common.add_individual` (Create)
   - `common.change_individual` (Update)
   - `common.delete_individual` (Delete, Trash, Restore)

5. **Navigation & Dashboard Registry Card**:
   Routed views under `/individuals/` and registered the **Individual Registry** card under the Executive Dashboard context.

## Consequences

### Positive
* **Bilingual Compliance**: Profiles support both local Thai layouts and standard English fields.
* **Refined Navigation UX**: User-facing titles, delete prompts, and breadcrumbs display the full formatted name rather than raw integer primary keys.
* **Database Portability**: Use of `JSONField` prevents vendor lock-in, enabling SQLite and Postgres compatibility.
* **Modularity**: Data validations, form normalizations, and business operations are cleanly split into testable layers.
