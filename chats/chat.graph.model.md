Three hard structural errors before I get to the field-level gaps:

1. **`StorageLocation` node** references a `product_storage_locations` table that flat out doesn't exist in your schema. The whole node and its edges need to go.
2. **`(Payment)-[:SETTLES]->(JournalEntry)`** has no FK backing. `payments_accounts_receivable.invoiceReference` points to `billing_document_headers.billingDocument`, not to any journal entry. The correct edge is `(Payment)-[:SETTLES]->(BillingDocument)`.
3. **Payment PK** is wrong. `payments_accounts_receivable` has no `fiscalYear` column, so the `accountingDocument + fiscalYear` composite doesn't hold. PK is just `accountingDocument`.

Beyond those, a significant chunk of fields listed across Product, Plant, SalesOrder, Delivery, JournalEntry, and Payment have no source column in the provided schema. They're standard SAP fields that almost certainly exist in your real system, but since you asked me to check against the schema, I've stripped them and called them out in the design notes. Re-add from your full table definitions.

One more: `Delivery items.productId` doesn't come directly from `outbound_delivery_items`. That table only carries `referenceSdDocument/Item`. You need to denormalize `material` from `sales_order_items` at ETL time.

Here's the corrected model:

---

# Corrected Graph Model

## Nodes

### Customer

Merged from: `business_partners`, `customer_company_assignments`, `customer_sales_area_assignments`

| Field               | Type      |
| ------------------- | --------- |
| customerId          | bigint PK |
| fullName            | text      |
| grouping            | text      |
| industry            | text      |
| isBlocked           | boolean   |
| companyCode         | text      |
| salesOrganization   | text      |
| distributionChannel | text      |
| division            | bigint    |
| paymentTerms        | text      |
| currency            | text      |

---

### Address

Source: `business_partner_addresses`

| Field      | Type        |
| ---------- | ----------- |
| addressId  | bigint PK   |
| city       | text        |
| country    | text        |
| postalCode | bigint      |
| region     | text        |
| street     | text        |
| validFrom  | timestamptz |
| validTo    | timestamptz |

---

### Product

Merged from: `products`, `product_descriptions` (EN filtered), `product_plants`

| Field        | Type    |
| ------------ | ------- |
| productId    | text PK |
| productName  | text    |
| productType  | text    |
| profitCenter | text    |

> `productName` is flattened from `product_descriptions` filtered to English. `profitCenter` comes from `product_plants`. Fields `productGroup`, `baseUnit`, `grossWeight`, `netWeight`, `weightUnit` are not present in the provided schema — add them once verified against your full SAP tables.

---

### Plant

Source: `plants`

| Field     | Type    |
| --------- | ------- |
| plantId   | text PK |
| plantName | text    |

> `salesOrganization`, `distributionChannel`, and `country` are not present in the provided `plants` table. Add them if your full schema carries them elsewhere (e.g. a plant master extension table).

---

### SalesOrder

Merged from: `sales_order_headers`, `sales_order_items`, `sales_order_schedule_lines`

| Field          | Type        |
| -------------- | ----------- |
| salesOrderId   | bigint PK   |
| orderDate      | timestamptz |
| totalNetAmount | numeric     |
| currency       | text        |

**Embedded items array:**

```
items: [
  {
    salesOrderItemId      bigint
    productId             text        -- from sales_order_items.material
    plantId               text        -- from sales_order_items.productionPlant
    netAmount             text
    confirmedDeliveryDate timestamptz -- from sales_order_schedule_lines
  }
]
```

> `requestedDeliveryDate`, `overallDeliveryStatus`, `overallBillingStatus` are not in the provided schema. Item-level `quantity`, `quantityUnit`, and `rejectionReason` are also absent — standard SAP fields, verify and add from your full schema.

---

### Delivery

Merged from: `outbound_delivery_headers`, `outbound_delivery_items`

| Field               | Type        |
| ------------------- | ----------- |
| deliveryId          | bigint PK   |
| deliveryDate        | timestamptz |
| shippingPoint       | text        |
| goodsMovementStatus | text        |

**Embedded items array:**

```
items: [
  {
    deliveryItemId  bigint
    productId       text    -- denormalized from sales_order_items.material at ETL time
    plantId         text    -- from outbound_delivery_items.plant
  }
]
```

> `pickingStatus` is not in the provided schema. `quantity`, `quantityUnit`, and `storageLocation` on items are also absent. `productId` has no direct column in `outbound_delivery_items` — it must be resolved via `referenceSdDocument/Item` → `sales_order_items.material` during ingestion.

---

### BillingDocument

Merged from: `billing_document_headers`, `billing_document_items`, `billing_document_cancellations`

| Field                      | Type                                |
| -------------------------- | ----------------------------------- |
| billingDocumentId          | bigint PK                           |
| billingDate                | timestamptz                         |
| billingType                | text                                |
| companyCode                | text                                |
| currency                   | text                                |
| totalNetAmount             | numeric                             |
| isCancelled                | boolean                             |
| cancelledBillingDocumentId | bigint (null if not a cancellation) |

**Embedded items array:**

```
items: [
  {
    billingItemId  bigint
    productId      text
    quantity       text
    netAmount      text
  }
]
```

---

### JournalEntry

Source: `journal_entry_items_accounts_receivable`

| Field                     | Type                                                   |
| ------------------------- | ------------------------------------------------------ |
| journalEntryId            | bigint PK (composite: accountingDocument + fiscalYear) |
| companyCode               | text                                                   |
| fiscalYear                | bigint                                                 |
| amountTransactionCurrency | numeric                                                |

> `postingDate`, `documentDate`, `amountCompanyCurrency`, `isCleared`, and `clearingDate` are not present in the provided schema. Add from your full FI table definition.

---

### Payment

Source: `payments_accounts_receivable`

| Field                     | Type      |
| ------------------------- | --------- |
| paymentId                 | bigint PK |
| companyCode               | text      |
| amountTransactionCurrency | numeric   |

> PK is `accountingDocument` alone — `payments_accounts_receivable` has no `fiscalYear` column, so the composite used in the original proposal was incorrect. `postingDate`, `documentDate`, `amountCompanyCurrency`, and `clearingDate` are not in the provided schema.

---

## Relationships

### Customer layer

```
(Customer)-[:HAS_ADDRESS]->(Address)
(Customer)-[:PLACED]->(SalesOrder)
(Customer)-[:BILLED_TO]->(BillingDocument)
(Customer)-[:HAS_JOURNAL_ENTRY]->(JournalEntry)
(Customer)-[:MADE_PAYMENT]->(Payment)
```

### Sales backbone

```
(SalesOrder)-[:INCLUDES]->(Product)       -- via items[].productId
(SalesOrder)-[:SOURCED_FROM]->(Plant)     -- via items[].plantId
```

### Delivery

```
(Delivery)-[:FULFILLS]->(SalesOrder)
(Delivery)-[:SHIPS]->(Product)            -- via items[].productId (denormalized at ETL)
(Delivery)-[:DISPATCHED_FROM]->(Plant)    -- via items[].plantId
```

### Billing

```
(BillingDocument)-[:BILLS_FOR]->(SalesOrder)
(BillingDocument)-[:INVOICES]->(Product)          -- via items[].productId
(BillingDocument)-[:CANCELS]->(BillingDocument)   -- self-referential, nullable
```

### Finance

```
(JournalEntry)-[:RECORDS]->(BillingDocument)
(Payment)-[:SETTLES]->(BillingDocument)           -- via payments_accounts_receivable.invoiceReference
```

### Inventory

```
(Product)-[:STOCKED_AT]->(Plant)    -- via product_plants
```

> `StorageLocation` node has been removed entirely. The source table `product_storage_locations` does not exist in the provided schema. `(Plant)-[:HAS_STORAGE]->` and `(StorageLocation)-[:STORES]->` edges are dropped with it.

---

## Hop Count Verification

| Query                                        | Path                                                   | Hops |
| -------------------------------------------- | ------------------------------------------------------ | ---- |
| What did customer X order?                   | Customer → SalesOrder                                  | 1    |
| Which products on order X?                   | SalesOrder → Product                                   | 1    |
| Is order X billed?                           | SalesOrder ← BillingDocument                           | 1    |
| What is the invoice amount for customer X?   | Customer → BillingDocument                             | 1    |
| Is invoice X paid?                           | BillingDocument ← Payment                              | 1    |
| Which plant ships product Y to customer X?   | Customer → SalesOrder → Plant                          | 2    |
| Where is product Y stocked?                  | Product → Plant (via STOCKED_AT)                       | 1    |
| Is a delivery dispatched for order X?        | SalesOrder ← Delivery                                  | 1    |
| Which products were delivered to customer X? | Customer → SalesOrder ← Delivery → Product             | 3    |
| Full order-to-cash trace                     | Customer → SalesOrder → BillingDocument → JournalEntry | 3    |

> The O2C trace is now 3 hops, not 4. Fixing the Payment→BillingDocument edge collapses it. "Is invoice X paid?" also drops from 2 hops to 1 for the same reason.

---

## Design Notes

- **Header/item merging** on SalesOrder, Delivery, and BillingDocument eliminates the most common join hops in SAP-style schemas.
- **Embedded items arrays** are denormalized read-only payloads for RAG and display. Do not traverse from them — use edges for that.
- **No arrays of foreign key IDs** on nodes. Relationships like `Product ↔ Plant` are edges, not `plantIds: []` properties.
- **Finance is kept as two separate nodes** (JournalEntry and Payment) to preserve AR lifecycle visibility. JournalEntry exists at billing time; Payment clears it later. Merging loses open AR.
- **BillingDocument self-reference** via `[:CANCELS]` supports cancellation chain traversal and double-cancellation detection.
- **Payment settles BillingDocument directly** via `invoiceReference`. There is no explicit FK from `payments_accounts_receivable` to `journal_entry_items_accounts_receivable` in the provided schema, so the original `(Payment)-[:SETTLES]->(JournalEntry)` edge had no backing. If your full schema includes an `accountingDocument` cross-reference between the two tables, you can add that edge back.
- **JournalEntry PK** uses `accountingDocument + fiscalYear` composite (both columns present in source). **Payment PK** is `accountingDocument` alone — `fiscalYear` is not in `payments_accounts_receivable`.
- **StorageLocation** is dropped. Re-introduce it once `product_storage_locations` is confirmed in your schema, and wire `(Plant)-[:HAS_STORAGE]->(StorageLocation)-[:STORES]->(Product)` at that point.
- **Delivery items.productId** requires ETL denormalization — resolve `referenceSdDocument/Item` through `sales_order_items.material` during ingestion. It is not a direct column in `outbound_delivery_items`.
- **Schema gap fields** — several fields expected in a full SAP system are absent from the provided schema. Verify and add: extended product master fields (productGroup, baseUnit, weights), plant master extensions (salesOrg, distChannel, country), sales order status fields, delivery picking status, and full FI document timestamps and clearing fields.
