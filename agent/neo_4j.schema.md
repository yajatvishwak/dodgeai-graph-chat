# Neo4j Graph Schema — SAP Order-to-Cash

## Node Types

| Label               | Key Property                     | Other Properties                                                                                                                                                                                                                    |
| ------------------- | -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Customer            | `id`                             | fullName, name, companyCode, isBlocked, salesOrganization, distributionChannel, currency, paymentTerms, grouping, category, industry, creationDate, reconciliationAccount, customerAccountGroup                                     |
| Address             | `id` (businessPartner:addressId) | businessPartner, addressId, city, country, postalCode, region, street                                                                                                                                                               |
| Product             | `id`                             | name, type, group, baseUnit, division, grossWeight, netWeight, weightUnit, creationDate                                                                                                                                             |
| Plant               | `id`                             | name, salesOrganization, distributionChannel, division                                                                                                                                                                              |
| SalesOrder          | `id`                             | type, salesOrganization, distributionChannel, division, creationDate, totalNetAmount, currency, deliveryStatus, billingStatus, soldToParty, paymentTerms, requestedDeliveryDate, incotermsClassification, incotermsLocation         |
| SalesOrderItem      | `uid` (salesOrder:item)          | salesOrder, item, category, material, quantity, quantityUnit, netAmount, currency, materialGroup, plant, storageLocation, confirmedDeliveryDate, confirmedQuantity                                                                  |
| Delivery            | `id`                             | creationDate, actualGoodsMovementDate, shippingPoint, goodsMovementStatus, pickingStatus, deliveryBlockReason                                                                                                                       |
| DeliveryItem        | `uid` (deliveryDoc:item)         | deliveryDocument, item, quantity, quantityUnit, plant, storageLocation, batch, referenceSalesOrder, referenceSalesOrderItem                                                                                                         |
| BillingDocument     | `id`                             | type, date, creationDate, totalNetAmount, currency, companyCode, isCancelled, cancelledBillingDocument, accountingDocument, fiscalYear, soldToParty                                                                                 |
| BillingDocumentItem | `uid` (billingDoc:item)          | billingDocument, item, material, quantity, quantityUnit, netAmount, currency, referenceDelivery, referenceDeliveryItem                                                                                                              |
| JournalEntry        | `id` (accountingDoc:fiscalYear)  | accountingDocument, fiscalYear, companyCode, documentType, postingDate, documentDate, referenceDocument, customer, profitCenter, currency, glAccount, totalAmount, clearingDate, clearingDocument, clearingDocFiscalYear, itemCount |
| ClearingDocument    | `id` (clearingDoc:fiscalYear)    | accountingDocument, fiscalYear, clearingDate, customer, companyCode                                                                                                                                                                 |

## Relationships

### Document-level OTC flow (use these for tracing)

```
(Customer)-[:PLACED]->(SalesOrder)
(SalesOrder)-[:DELIVERED_VIA]->(Delivery)
(Delivery)-[:BILLED_IN]->(BillingDocument)
(BillingDocument)-[:RECORDED_AS]->(JournalEntry)
(JournalEntry)-[:CLEARED_BY]->(ClearingDocument)
```

### Customer links

```
(BillingDocument)-[:BILLED_TO]->(Customer)
(JournalEntry)-[:FOR_CUSTOMER]->(Customer)
(ClearingDocument)-[:FOR_CUSTOMER]->(Customer)
(Customer)-[:HAS_ADDRESS]->(Address)
```

### Item containment

```
(SalesOrder)-[:HAS_ITEM]->(SalesOrderItem)
(Delivery)-[:HAS_ITEM]->(DeliveryItem)
(BillingDocument)-[:HAS_ITEM]->(BillingDocumentItem)
```

### Item-level flow (for granular tracing)

```
(DeliveryItem)-[:FULFILLS]->(SalesOrderItem)
(BillingDocumentItem)-[:BILLS]->(DeliveryItem)
```

### Product / master data

```
(SalesOrderItem)-[:FOR_PRODUCT]->(Product)
(BillingDocumentItem)-[:FOR_PRODUCT]->(Product)
(SalesOrderItem)-[:FROM_PLANT]->(Plant)
(DeliveryItem)-[:FROM_PLANT]->(Plant)
(Product)-[:AVAILABLE_AT]->(Plant)
(Product)-[:STORED_AT]->(Plant)          // has storageLocation property on relationship
```

### Cancellation

```
(BillingDocument)-[:CANCELS]->(BillingDocument)  // only if cancelledBillingDocument is populated
```

## Document Flow Diagram

```
Customer ─PLACED─► SalesOrder ─DELIVERED_VIA─► Delivery ─BILLED_IN─► BillingDocument ─RECORDED_AS─► JournalEntry ─CLEARED_BY─► ClearingDocument
```

Item-level (reverse direction):

```
SalesOrderItem ◄─FULFILLS─ DeliveryItem ◄─BILLS─ BillingDocumentItem
```

## ID Formats

| Document            | ID Pattern               | Example          |
| ------------------- | ------------------------ | ---------------- |
| Sales Order         | 6-digit 740xxx           | `740506`         |
| Delivery            | 8-digit 807xxxxx         | `80737721`       |
| Billing Document    | 8-digit 905/906/911xxxxx | `90504298`       |
| Accounting Doc (JE) | 10-digit 9400000xxx      | `9400000220`     |
| Clearing Doc        | 10-digit 9400635xxx      | `9400635977`     |
| Customer            | 9-digit 310/320xxxxxx    | `310000108`      |
| Product             | variable S89/B89/numeric | `S8907367001003` |
| Plant               | 4-char                   | `1920`, `KA05`   |

## Key Data Caveats

- All IDs are stored as **strings**.
- Item UIDs use `:` as separator: `740506:10`, `80738076:10`, `9400000220:2025`.
- Item numbers are normalised (leading zeros stripped): `000010` → `10`.
- `isCancelled` boolean on BillingDocument marks cancelled invoices. The `cancelledBillingDocument` field is empty in this dataset so `CANCELS` relationships may not exist.
- Currency is `INR` and company code is `ABCD` for all records.
- Dates are ISO-8601 strings: `2025-04-02T00:00:00Z`.
- `totalNetAmount` on SalesOrder and BillingDocument is a float. `totalAmount` on JournalEntry is a float.
- Use `OPTIONAL MATCH` for flow traversals to handle incomplete chains.
