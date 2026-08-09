## ADDED Requirements

### Requirement: Searchable catalog documents exist per discoverable entity
The system SHALL persist searchable catalog documents that represent customer-discoverable entities. Each document MUST include a stable `public_id`, a `document_type` from the allowlist `package`, `instant_meal`, `food`, and `category`, English and Bangla display titles (`title_en`, `title_bn` where Bangla may be blank until curated), an active flag, and a link or typed reference to the underlying source entity when applicable.

#### Scenario: Package document for a monthly meal package
- **WHEN** an active Student/Regular/Professional/Family (or equivalent) meal package is indexed
- **THEN** a `SearchDocument` with `document_type` `package` exists and is eligible for customer search when `is_active` is true

#### Scenario: Food document for a customer-visible item
- **WHEN** a customer-visible food item (for example rice / chicken dish) is indexed
- **THEN** a `SearchDocument` with `document_type` `food` exists with titles suitable for customer display

### Requirement: Documents support keyword synonyms including Banglish
The system SHALL allow each document to own zero or more keywords used for matching. Keywords MUST support Bangla, English, and Banglish/latinized variants (for example `ভাত`, `vat`, `bhat`, `rice` for rice). Stored matching forms MUST be normalized consistently with the search normalization rules.

#### Scenario: Kacchi synonyms match the same document
- **WHEN** a document for Kacchi Biryani has keywords `কাচ্চি`, `kacchi`, `kachchi`, `kachi`, `kacci`, and `biryani`
- **THEN** those keywords are associated with that document and available to the matching layer

#### Scenario: Duplicate keyword on same document rejected
- **WHEN** an admin attempts to add a keyword whose normalized form already exists on the same document
- **THEN** the system rejects the duplicate and does not create a second row

### Requirement: Inactive documents are excluded from customer discovery
The system MUST NOT return inactive documents from customer search or suggestion endpoints. Admin APIs MAY still list inactive documents for management.

#### Scenario: Inactive document hidden from customers
- **WHEN** a document’s `is_active` is false
- **THEN** customer search and suggestions omit that document even if keywords would otherwise match

### Requirement: Catalog can be bootstrapped from meals and food sources
The system SHALL provide a sync/bootstrap path that upserts documents from active meal packages and customer-visible food sources without deleting admin-curated keywords for existing documents.

#### Scenario: Sync upserts titles without wiping keywords
- **WHEN** bootstrap sync runs after a meal package title changes
- **THEN** the linked document titles update and existing keywords on that document remain unless explicitly removed by admin
