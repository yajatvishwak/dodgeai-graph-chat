# Logical references in schema.dbml
_Exported on 3/27/2026 at 09:09:52 GMT+5:30 from Cursor (2.6.21)_

---

**User**

@data_creation/schema.dbml go through this and tell me what could some logical refrences

---

**Cursor**

I’ll review `data_creation/schema.dbml` and identify the most sensible logical references (foreign-key-style relationships) that should exist between tables based on naming and fields.

Most of your tables look like SAP-style extracts, so “logical references” are mainly document-flow and master-data joins.  
If you want to add `Ref:` lines in DBML, these are the best candidates.

## High-confidence references

- `billing_document_items.billingDocument -> billing_document_headers.billingDocument`
- `billing_document_cancellations.billingDocument -> billing_document_headers.billingDocument`
- `billing_document_cancellations.cancelledBillingDocument -> billing_document_headers.billingDocument`
- `billing_document_headers.soldToParty -> business_partners.businessPartner`
- `billing_document_items.material -> products.product`

- `business_partner_addresses.businessPartner -> business_partners.businessPartner`

- `customer_company_assignments.customer -> business_partners.customer`
- `customer_sales_area_assignments.customer -> business_partners.customer`

- `journal_entry_items_accounts_receivable.customer -> business_partners.customer`
- `journal_entry_items_accounts_receivable.referenceDocument -> billing_document_headers.billingDocument` (likely invoice ref)

- `outbound_delivery_items.deliveryDocument -> outbound_delivery_headers.deliveryDocument`
- `outbound_delivery_items.referenceSdDocument -> sales_order_headers.salesOrder`
- `outbound_delivery_items.referenceSdDocumentItem -> sales_order_items.salesOrderItem` (composite with order)

- `payments_accounts_receivable.customer -> business_partners.customer`
- `payments_accounts_receivable.invoiceReference -> billing_document_headers.billingDocument`
- `payments_accounts_receivable.salesDocument -> sales_order_headers.salesOrder`
- `payments_accounts_receivable.salesDocumentItem -> sales_order_items.salesOrderItem` (composite with salesDocument)

- `plants.addressId -> business_partner_addresses.addressId` (common in SAP, but slightly weaker unless address master is guaranteed unique)

- `product_descriptions.product -> products.product`
- `product_plants.product -> products.product`
- `product_plants.plant -> plants.plant`
- `product_storage_locations.product -> products.product`
- `product_storage_locations.plant -> plants.plant`
- `sales_order_items.material -> products.product`
- `sales_order_items.productionPlant -> plants.plant`

- `sales_order_items.salesOrder -> sales_order_headers.salesOrder`
- `sales_order_headers.soldToParty -> business_partners.businessPartner`
- `sales_order_schedule_lines.salesOrder -> sales_order_headers.salesOrder`
- `sales_order_schedule_lines.(salesOrder, salesOrderItem) -> sales_order_items.(salesOrder, salesOrderItem)`

## References that need composite keys (important)

For correctness, define these table keys first:

- `sales_order_items` key: `(salesOrder, salesOrderItem)`
- `sales_order_schedule_lines` key: `(salesOrder, salesOrderItem, scheduleLine)`
- `billing_document_items` key: `(billingDocument, billingDocumentItem)`
- `outbound_delivery_items` key: `(deliveryDocument, deliveryDocumentItem)`
- AR/payment items usually key on `(companyCode, fiscalYear, accountingDocument, accountingDocumentItem)`

Without composite keys, item-level refs can be ambiguous.

## Weaker / conditional references

- `billing_document_headers.accountingDocument -> journal_entry_items_accounts_receivable.accountingDocument`  
  (often true but may need `fiscalYear + companyCode` too)
- `payments_accounts_receivable.clearingAccountingDocument -> journal_entry_items_accounts_receivable.accountingDocument`  
  (again usually composite)
- `sales_order_headers.(salesOrganization,distributionChannel,organizationDivision) -> customer_sales_area_assignments.(salesOrganization,distributionChannel,division)` with `customer=soldToParty`  
  (business-rule join, not always strict FK)

If you want, I can draft exact DBML `Ref:` statements plus suggested `indexes [pk]` blocks for this file so you can paste directly.

---

**User**

yes please add them to the dbml

---

**Cursor**

I’ll update `data_creation/schema.dbml` by adding primary/composite key indexes and `Ref:` relationships for the high-confidence joins, then I’ll quickly verify the file parses cleanly from a lint/diagnostics perspective.

Added the logical relationships directly into `data_creation/schema.dbml` with:

- Primary/composite keys via `indexes { ... [pk] }` for core header/item/master tables.
- `Ref:` links for the high-confidence joins we discussed (billing, sales, delivery, product, plant, partner, AR/payment flows).
- Composite references where needed (for example order/document item joins).

No diagnostics/lint issues were reported for the updated file.

If you want, next I can tighten this further by marking a few refs as optional (or removing weaker ones like `plants.addressId -> business_partner_addresses.addressId`) depending on how strict you want physical FK enforcement to be.

