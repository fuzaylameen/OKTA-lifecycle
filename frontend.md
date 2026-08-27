# Master Prompt: IntelliID Frontend Enhancement (Antigravity)

Copy everything below into Antigravity as your prompt. This is an **enhancement pass on an existing, working frontend** — not a new build. The project has grown since initial scaffolding: the backend now includes JWT auth, RBAC, a 7-policy engine, an approval workflow, lifecycle execution (dry-run/confirm/cancel/verify), and identity timeline tracking. Read every constraint below before touching any file.

---

## Current Frontend Structure (Ground Truth — Verify, Don't Assume)

```
frontend/
├── dist/
├── node_modules/
├── public/
├── src/
│   ├── api/            ← existing API service layer, inspect before adding calls
│   ├── assets/
│   ├── components/     ← existing shared components (incl. the RotateMark brand mark)
│   ├── pages/
│   │   ├── AuditLog.jsx / .css
│   │   ├── Dashboard.jsx / .css
│   │   ├── Governance.jsx / .css
│   │   ├── Groups.jsx / .css
│   │   ├── Login.jsx / .css
│   │   ├── OnboardOffboard.jsx / .css
│   │   └── Users.jsx / .css
│   ├── styles/
│   ├── App.jsx / App.css
│   ├── index.css
│   └── main.jsx
└── .env
```

Note: pages for **User Details, Approvals, and Lifecycle Execution** do not exist yet as separate files, even though they're required below — these are new pages to add, not existing ones to edit. Follow the existing `PageName.jsx` + `PageName.css` pairing convention and existing routing pattern in `App.jsx` when adding them.

---

## Critical Constraints — Non-Negotiable

- **Do NOT rewrite the project from scratch.**
- **Do NOT change or break any existing backend API.** The backend is the source of truth and is already working.
- **Do NOT remove any existing working functionality.**
- **First inspect** the existing frontend structure, components, API calls, routing, and styling — including the design tokens and the `RotateMark` brand component already built — before writing anything new.
- **Reuse the existing design system** (colors, spacing, components, the RotateMark mark) wherever possible. Do not redesign the brand mark or color palette.
- **Make incremental changes only**, page by page.
- **If a required API endpoint does not exist yet, do not invent fake backend behavior or mock data to fill the gap.** Instead, clearly report: *"Frontend requires backend endpoint X for feature Y."* and build the UI shell for that feature in a visibly disabled/pending state rather than faking it.
- **Do not use mock security data anywhere the real backend data is available.** If an existing mock/placeholder is currently shown for something the backend can now actually provide, replace it with the real data and remove any "mock data" disclaimer text tied to it.
- **Do not modify backend files unless absolutely necessary.** If a change is required, explain exactly what and why before making it.

## Backend Context

**Roles**: Auditor, Manager, Admin, RoleManager
**Okta group → role mapping**: Identity-Auditors → Auditor · Identity-Managers → Manager · Identity-Admins → Admin · Identity-Role-Managers → RoleManager

**Policy Engine — 7 policies (use these exact names in the UI):**
1. `PreventSelfDeprovisionPolicy` — users cannot deprovision themselves, including Admins
2. `ManagerCannotModifyAdminPolicy` — Managers cannot perform sensitive operations against Admin accounts
3. `ManagerCannotDeprovisionManagerOrAdminPolicy` — Managers cannot deprovision Managers or Admins
4. `SuspensionRequiresReasonPolicy` — suspending a user requires a non-empty reason
5. `PreventPrivilegeEscalationPolicy` — a requester cannot assign a role higher than their own privilege level
6. `PreventSelfRoleEscalationPolicy` — a user cannot change their own role to a higher privilege role
7. `PrivilegedUserProtectionPolicy` — lower-privileged users cannot modify privileged users; Managers cannot act on peer Managers

**Known existing lifecycle endpoints** (integrate with these — do not create replacements):
```
POST /api/lifecycle/dry-run
GET  /api/lifecycle/{operation_id}
POST /api/lifecycle/{operation_id}/confirm
POST /api/lifecycle/{operation_id}/cancel
GET  /api/lifecycle/{operation_id}/verify
```

**Current user identity/permissions source**: `GET /api/auth/me`

---

## Page-by-Page Requirements

### 1. Dashboard (`Dashboard.jsx` — existing, edit incrementally)
Keep the current layout. Make the metrics real wherever a backend API exists:
- Total Users, Active/Provisioned Users, Deprovisioned Users, Pending Approvals, Policy Violations/Denied Authorization Requests, Audit Events — pull from real endpoints; never show a fake number where a real one is available.
- Add a **Role Distribution** visualization across Admin/Manager/Auditor/RoleManager.
- Add a **High-Risk Requests** section (examples: privilege escalation attempt, Manager modifying Admin, Manager deleting another Manager, self-deprovision attempt, suspension without reason). Columns: Requester, Role, Action, Target, Decision, Policy, Timestamp. Clear ALLOWED/DENIED visual states.
- Remove any "Mock security data — backend integration pending" text for anything the backend now genuinely provides.

### 2. Users (`Users.jsx` — existing, edit incrementally)
Change the table from `Name | Email | Login | Status | Actions` to:
```
Name | Email | Role | Okta Group | Status | Actions
```
Use real roles (Admin/Manager/Auditor/RoleManager) and real Okta groups (Identity-Admins/Identity-Managers/Identity-Auditors/Identity-Role-Managers). Add professional role badges. **Do not invent group membership** — if the current user API doesn't return role/group info, inspect the backend to find the correct existing endpoint that does, rather than hardcoding values. If no such endpoint exists, report it per the constraint above instead of faking it.

### 3. User Details (new page — create following existing page conventions)
On selecting a user, show:
- **Identity**: Name, Email, Login, Okta User ID, Account Status
- **Authorization**: Application Role, Okta Group, Permission list
- **Security**: Password status, last activity if available, account status
- **Actions**: Provision, Suspend, Reactivate, Deactivate, Delete, Role management where permitted

Actions must respect backend RBAC and policy enforcement — **hiding a button is UX, not security**; the backend remains the actual enforcement point, and every action should still handle a 403 gracefully (see Policy Violation UX below) even if the button was visible.

### 4. Governance (`Governance.jsx` — existing, expand into a major feature)
- **Policy Engine section**: show all 7 active policies, each with name, description, status, and violation/decision count if the backend exposes it. Use the exact policy names and descriptions listed above.
- **Recent Policy Decisions table**: Requester, Requester Role, Action, Target, Decision, Policy, Reason, Timestamp — policy names must match the real backend policy identifiers exactly (e.g. `ManagerCannotDeprovisionManagerOrAdminPolicy`), not paraphrased labels.

### 5. Access & Groups (`Groups.jsx` — existing, correct the mapping data)
**Remove any unrelated/fake role-to-group mapping currently shown** (e.g. "Administrator → Okta Admins", "Developer → Engineering", "Data Analyst → Analytics", "HR Manager → Human Resources" — these do not belong to this project's actual role model). Replace with the real mapping table:

| Application Role | Okta Group | Privilege Level | Permissions |
|---|---|---|---|
| Admin | Identity-Admins | 3 | User lifecycle operations |
| Manager | Identity-Managers | 2 | User lifecycle operations, no role management |
| Auditor | Identity-Auditors | 1 | Read-only + audit |
| RoleManager | Identity-Role-Managers | 4 | Role governance + policy management |

Clearly visually distinguish RoleManager from Admin — they are different privilege tiers, not synonyms.

### 6. Audit Log (`AuditLog.jsx` — existing, expand)
Columns: Timestamp, Requester, Role, Action, Target, Decision, Policy, Reason. Filters: Search, Action, Role, Decision, Date. Decision badges: ALLOWED / DENIED. Clicking a row opens a detail panel/modal showing the full authorization decision (requester, role, action, target, decision, policy identifier, reason) using real backend audit data — no placeholder content.

### 7. Approvals (new page — create following existing page conventions)
Show requests grouped or filterable by status: Pending, Approved, Rejected, Escalated. Per request: Request ID, Requester, Target User, Requested Action, Requested Role (if applicable), Created At, Status. Buttons: Approve, Reject, Escalate — these must call the real backend and respect its authorization; **do not allow an unauthorized role to approve just because the button is present in the DOM** — check permissions from `GET /api/auth/me` before rendering the button, and still handle a backend 403 gracefully if it occurs anyway.

### 8. Lifecycle Execution (new page — create following existing page conventions)
Visual workflow: `Dry Run → Preview → Confirmation → Execution → Verification → Completed`. Operation statuses to display: PREVIEW, PENDING, CONFIRMED, EXECUTED, VERIFIED, CANCELLED, FAILED. Wire directly to the existing lifecycle endpoints listed above — do not create new ones.

### 9. Identity Timeline (new component, likely embedded within User Details)
Vertical timeline per user showing events such as: Created, Added to a group, Provisioned, Password changed, Suspended, Reactivated. Each entry: Timestamp, Event, Actor, Action, Result. Use real backend timeline data only.

### 10. Password Expiry (within User Details / Security section)
Show password status, expiry info, days remaining if available. "Expire Password" action gated by permission, with a confirmation dialog before executing.

## RBAC UI Behavior

- Load the authenticated user's role/permissions from `GET /api/auth/me` and use it to conditionally show/hide relevant actions across all pages.
- This is UX convenience only — **the backend RBAC + policy engine is the actual enforcement**. Never treat a hidden button as a security control.
- If the backend returns HTTP 403 for any action, show a clear, specific error — never a crash or a blank state.

## Policy Violation UX

When the backend returns a 403 policy violation, show a structured, readable error — not a generic failure message. Example shape:

```
Action Blocked
Policy: Manager Cannot Deprovision Admin
Reason: Managers cannot deprovision Admin accounts.
```

Pull the policy name and reason directly from the backend's error response — do not hardcode a mapping of error codes to messages if the backend already returns human-readable reasons.

## Design Requirements

- Enterprise identity-governance dashboard — clean, professional, not a generic admin template.
- Keep the existing design system: consistent cards, professional badges, good spacing, clear typography, the existing `RotateMark` brand component and dark theme tokens already built — reuse as-is, do not redesign.
- Subtle animations only. Responsive tables. Confirmation modals for destructive actions. Proper empty, loading, and error states on every page.
- Avoid: excessive gradients, unnecessary animation, oversized charts, decorative elements with no function, fake data, unrelated roles/groups, unnecessary rebranding.

## Implementation Process — Follow This Order

1. Inspect the existing project structure fully (framework, routing, API service layer, existing dashboard components, existing styling/theme).
2. Identify exactly which backend endpoints already exist for each feature above vs. which are missing — produce this list before writing code.
3. Implement improvements incrementally, page by page, reusing existing components wherever possible.
4. Keep all existing routes working throughout.
5. Add the three new pages (User Details, Approvals, Lifecycle Execution) following the existing file-pairing and routing conventions.
6. Run/build the frontend after each page's changes; fix any errors before moving to the next page.
7. Verify real API integration on each page (confirm actual data renders, not placeholders).
8. Before any large architectural change, stop and explain the plan first.
9. At the end, provide a full summary of every file changed or added.

## Final Goal

The finished UI should make this full architecture visibly obvious during a live demo:

```
JWT Authentication → Okta Identity → Okta Groups → RBAC Role → Permissions
→ Policy Engine → Approval Workflow → Lifecycle Execution → Verification
→ Audit Log → Identity Timeline
```

**Above all: do not break existing working functionality.**