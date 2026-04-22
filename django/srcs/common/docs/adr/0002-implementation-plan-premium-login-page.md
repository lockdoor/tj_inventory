# Implementation Plan - Premium Login Page

The goal is to implement a secure, high-end login experience for the inventory system. We will use the **`common`** app to house the authentication logic and templates.

## User Review Required

> [!IMPORTANT]
> - **Redirection**: After a successful login, users will be redirected to the **Dashboard**.
> - **Aesthetics**: The login page will use a "Full Screen Glassmorphism" style to match the premium theme of the application.
> - **Standard Auth**: We will use Django's built-in `LoginView` and `LogoutView` to ensure maximum security.

## Proposed Changes

### Common App

#### [NEW] [urls.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/common/urls.py)
- Create a dedicated URL configuration for common features, starting with login and logout.
- Paths: `login/` and `logout/`.

#### [NEW] [login.html](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/common/templates/common/login.html)
- A specialized template that does **not** extend `base.html` (to provide a clean, focused login experience).
- UI Features:
    - Frosted glass container.
    - Animated emerald gradient background.
    - Responsive mobile-first design.

### App Configuration

#### [MODIFY] [urls.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/app/urls.py)
- Include `common.urls` in the root URL configuration.
- We will use the prefix `accounts/` to follow standard Django conventions.

#### [MODIFY] [settings.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/app/settings.py)
- Add `LOGIN_REDIRECT_URL = 'dashboard:home'`.
- Add `LOGOUT_REDIRECT_URL = 'common:login'`.
- Add `LOGIN_URL = 'common:login'`.

## Verification Plan

### Automated Tests
- No new automated tests, as we are using Django's built-in, pre-tested auth views.

### Manual Verification
1. Navigate to `/accounts/login/` -> Verify the premium glassmorphism design.
2. Enter valid credentials -> Verify redirection to the dashboard.
3. Enter invalid credentials -> Verify error messages are displayed clearly.
4. Test the logout functionality -> Verify redirection back to the login page.
5. Try to access the dashboard directly without logging in -> Verify redirection to the login page.
