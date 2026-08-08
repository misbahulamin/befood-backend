## Why

BeFood today has a customer wallet ledger for meal charges and funding, but no central platform cash wallet for admin financial control. Without a ledger-based Admin Wallet, successful customer payments, manual deposits, withdrawals, and operational expenses cannot be tracked in one auditable place—blocking transparent platform finance and future settlement workflows.

## What Changes

- Introduce a **single central BeFood Admin Wallet** (platform business wallet) with denormalized balance plus an **append-only ledger** as the source of truth.
- Automatically **credit** the Admin Wallet when BeFood receives a successful customer payment that represents platform cash/revenue recognition (initially meal-delivery wallet charges; gateway/order payments when wired).
- Record rich **source tracking** on every ledger entry (source type, order/customer/admin refs, payment method, note, timestamps, status).
- Allow authorized `is_verified` admins to **manual deposit**, **withdraw** (with balance checks), and post **approved expenses** (restaurant settlement, rider payment, refund, promotional, operational, Onahar-related, platform expense).
- Expose a **web Admin Wallet dashboard API**: summary cards, recent transactions, filter/search, role-gated mutations, and **audit logs** for sensitive actions.
- Enforce **idempotency** so the same payment/order reference cannot credit the Admin Wallet twice.
- Ship backend + frontend integration docs for the Admin Panel Wallet section.

## Capabilities

### New Capabilities
- `admin-wallet-ledger`: Central platform wallet, append-only ledger, balance aggregates, idempotent credit/debit primitives, and ledger reconcilability.
- `admin-wallet-payment-ingestion`: Automatic Admin Wallet credit from successful customer/platform payment events with source tracking and duplicate prevention.
- `admin-wallet-operations`: Manual deposit, withdrawal, expense posting, adjustments, and balance-guarded debit rules.
- `admin-wallet-admin-api`: Verified-admin web APIs for dashboard summaries, transaction history (filter/search), permissions, and audit log exposure.
- `admin-wallet-frontend-docs`: Frontend contract for Admin Panel Wallet UI (summary cards, tables, deposit/withdraw flows, filters).

### Modified Capabilities
- `meal-delivery-wallet-payment`: After a successful customer meal-delivery wallet charge, the system MUST also create an idempotent Admin Wallet credit with order/delivery/customer source references (best-effort isolation rules defined in design—customer charge remains authoritative for delivery mark).

## Impact

- **New app or package** under something like `admin_wallet/` (models, services, web APIs, tests, docs)—separate from customer `wallet/` to avoid mixing customer liability with platform cash.
- **Hooks** from `orders.services.meal_payment.charge_delivered_meal` (and future payment success paths) into Admin Wallet credit services.
- **APIs** under `/api/v1/web/admin-wallet/` (or equivalent) gated by `IsVerifiedAdmin`; optional finer permission codenames for deposit/withdraw.
- **Dependencies**: reuse Decimal money patterns, `PublicIdMixin`, `select_for_update` ledger style from `wallet.services.ledger` and Onahar fund ledger; no floating-point money.
- **Non-goals for this change**: full restaurant/rider settlement product, payment gateway integration itself, editing completed ledger rows, mobile operator Admin Wallet APIs, treating customer wallet recharge as platform income (custody/liability tracking deferred unless explicitly added later).
