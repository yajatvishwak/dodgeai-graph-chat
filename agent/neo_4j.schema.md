# Neo4j Schema (12 Nodes)

## Nodes & Attributes

| Node              | Attributes                                                                                                                       |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `Address`         | addressId, street, city, region, country, postalCode, validFrom, validTo                                                         |
| `BillingDocument` | billingDocumentId, cancelledBillingDocumentId, billingDate, billingType, companyCode, currency, isCancelled, totalNetAmount      |
| `BillingItem`     | billingDocumentId, billingItemId, billingItemUid, productId, netAmount, quantity                                                 |
| `Customer`        | customerId, companyCode, currency, distributionChannel, division, fullName, grouping, isBlocked, paymentTerms, salesOrganization |
| `Delivery`        | deliveryId, deliveryDate, goodsMovementStatus, shippingPoint                                                                     |
| `DeliveryItem`    | deliveryId, deliveryItemId, deliveryItemUid, plantId, productId                                                                  |
| `JournalEntry`    | journalEntryId, amountTransactionCurrency, companyCode, fiscalYear                                                               |
| `Payment`         | paymentId, amountTransactionCurrency, companyCode                                                                                |
| `Plant`           | plantId, plantName                                                                                                               |
| `Product`         | productId, productName, productType, profitCenter                                                                                |
| `SalesOrder`      | salesOrderId, currency, orderDate, totalNetAmount                                                                                |
| `SalesOrderItem`  | plantId, productId, salesOrderId, salesOrderItemId, salesOrderItemUid, confirmedDeliveryDate, netAmount                          |

## Relationships

```
BillingDocument -[:HAS_BILLING_ITEM]-----> BillingItem
BillingDocument -[:INVOICES]-------------> Product
BillingItem     -[:REFERENCES_PRODUCT]---> Product
Customer        -[:BILLED_TO]------------> BillingDocument
Customer        -[:HAS_ADDRESS]----------> Address
Customer        -[:HAS_JOURNAL_ENTRY]----> JournalEntry
Customer        -[:MADE_PAYMENT]---------> Payment
Customer        -[:PLACED]---------------> SalesOrder
Delivery        -[:DISPATCHED_FROM]------> Plant
Delivery        -[:FULFILLS]-------------> SalesOrder
Delivery        -[:HAS_DELIVERY_ITEM]----> DeliveryItem
Delivery        -[:SHIPS]----------------> Product
DeliveryItem    -[:REFERENCES_PLANT]-----> Plant
DeliveryItem    -[:REFERENCES_PRODUCT]---> Product
JournalEntry    -[:RECORDS]--------------> BillingDocument
Product         -[:STOCKED_AT]-----------> Plant
SalesOrder      -[:HAS_SALE_ITEM]--------> SalesOrderItem
SalesOrder      -[:INCLUDES]-------------> Product
SalesOrder      -[:SOURCED_FROM]---------> Plant
SalesOrderItem  -[:REFERENCES_PLANT]-----> Plant
SalesOrderItem  -[:REFERENCES_PRODUCT]---> Product
```
