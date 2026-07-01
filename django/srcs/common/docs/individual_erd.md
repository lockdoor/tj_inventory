# Entity Relationship Diagram (ERD) - Individual (Person) Model

This document defines the schema for the central `Individual` model located in the `common` app. It represents a physical human being (independent of their business role).

---

## ERD (Mermaid Diagram)

```mermaid
erDiagram
    User |o--o| Individual : "linked_to"

    User {
        int id PK
        string username
    }

    Individual {
        int id PK
        int user_id FK "Optional link to auth User (nullable)"
        string first_name_th "First Name in Thai"
        string last_name_th "Last Name in Thai"
        string first_name_en "First Name in English (optional)"
        string last_name_en "Last Name in English (optional)"
        string nickname "Nickname (optional, Thai or English)"
        string email
        json phones "JSON array of phone numbers (SQLite & Postgres compatible)"
        datetime created_at
        int created_by_id FK
        datetime updated_at
        int updated_by_id FK
    }
```

---

## Entity Definitions

### 1. `Individual`
Represents any single physical human being (such as employees, personal customers, or contact persons). 
* **Role Independence**: This table stores core contact and identification details only. System-wide business roles (e.g. employee, vendor contact) are implemented as separate models pointing to this table via `OneToOneField` or `ForeignKey` references.
* **Authentication**: Optional. If the individual needs credentials to log in, they link to the Django `auth.User`. Otherwise, `user_id` is left `NULL`.
* **Phones**: Stored as a JSON array (`JSONField`) to support multiple phone numbers in a cross-database compatible way (compatible with local SQLite and production PostgreSQL).
* **Audit Fields**: Extends `AuditableMixin` for tracking creation and modification metadata.
