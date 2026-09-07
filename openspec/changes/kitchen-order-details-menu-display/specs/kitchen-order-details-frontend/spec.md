## ADDED Requirements

### Requirement: Order Details preview shows Menu instead of Package

The Admin Kitchen Today Order Details flow (`/admin/kitchen/today` → Order Details) SHALL display a customer table whose food column is **Menu**, showing that day’s published ingredients for each row (prefer `menu_items_label`, else join `ingredient_names` with ` + `). The primary food column MUST NOT be package name. When menu fields are empty, the cell MUST show a clear empty placeholder such as `—`.

#### Scenario: Preview renders joined ingredients

- **WHEN** the Order Details response includes a customer with `menu_items_label` `mach + dhal + vat`
- **THEN** the preview modal Menu cell shows `mach + dhal + vat`

#### Scenario: Missing menu shows placeholder

- **WHEN** a customer row has empty `ingredient_names` and no `menu_items_label`
- **THEN** the Menu cell shows `—` and does not fall back to `package_name`

### Requirement: Order Details print and PDF use the same Menu column

The Order Details print sheet and downloaded PDF MUST use the same columns as the preview for food identity: SL, Name, Phone, Menu (ingredients), Address — not Package as the food column. Layout MUST remain kitchen-readable and professionally spaced for A4 handoff.

#### Scenario: Download PDF Menu matches preview

- **WHEN** an admin downloads the Order Details PDF for a loaded response
- **THEN** the PDF customer table shows Menu ingredient labels consistent with the on-screen preview for those rows
