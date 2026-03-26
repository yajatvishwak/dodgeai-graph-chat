# Neo4j Schema Summary (neo_4j.schema.json)

Total nodes: **12**

## Nodes

### `Address`

**Attributes**
- `country`
- `city`
- `street`
- `postalCode`
- `validFrom`
- `region`
- `validTo`
- `addressId`

**Relations**
- `(Address) -[:HAS_ADDRESS]- <-- (Customer)`

### `BillingDocument`

**Attributes**
- `companyCode`
- `billingDate`
- `isCancelled`
- `billingDocumentId`
- `totalNetAmount`
- `billingType`
- `currency`
- `cancelledBillingDocumentId`

**Relations**
- `(BillingDocument) -[:RECORDS]- <-- (JournalEntry)`
- `(BillingDocument) -[:HAS_BILLING_ITEM]- --> (BillingItem)`
- `(BillingDocument) -[:BILLED_TO]- <-- (Customer)`
- `(BillingDocument) -[:INVOICES]- --> (Product)`

### `BillingItem`

**Attributes**
- `quantity`
- `billingDocumentId`
- `billingItemId`
- `productId`
- `netAmount`
- `billingItemUid`

**Relations**
- `(BillingItem) -[:REFERENCES_PRODUCT]- --> (Product)`
- `(BillingItem) -[:HAS_BILLING_ITEM]- <-- (BillingDocument)`

### `Customer`

**Attributes**
- `companyCode`
- `division`
- `isBlocked`
- `customerId`
- `fullName`
- `currency`
- `distributionChannel`
- `grouping`
- `salesOrganization`
- `paymentTerms`

**Relations**
- `(Customer) -[:HAS_JOURNAL_ENTRY]- --> (JournalEntry)`
- `(Customer) -[:BILLED_TO]- --> (BillingDocument)`
- `(Customer) -[:PLACED]- --> (SalesOrder)`
- `(Customer) -[:HAS_ADDRESS]- --> (Address)`
- `(Customer) -[:MADE_PAYMENT]- --> (Payment)`

### `Delivery`

**Attributes**
- `goodsMovementStatus`
- `deliveryId`
- `deliveryDate`
- `shippingPoint`

**Relations**
- `(Delivery) -[:DISPATCHED_FROM]- --> (Plant)`
- `(Delivery) -[:HAS_DELIVERY_ITEM]- --> (DeliveryItem)`
- `(Delivery) -[:FULFILLS]- --> (SalesOrder)`
- `(Delivery) -[:SHIPS]- --> (Product)`

### `DeliveryItem`

**Attributes**
- `deliveryItemUid`
- `plantId`
- `deliveryId`
- `deliveryItemId`
- `productId`

**Relations**
- `(DeliveryItem) -[:REFERENCES_PRODUCT]- --> (Product)`
- `(DeliveryItem) -[:REFERENCES_PLANT]- --> (Plant)`
- `(DeliveryItem) -[:HAS_DELIVERY_ITEM]- <-- (Delivery)`

### `JournalEntry`

**Attributes**
- `companyCode`
- `amountTransactionCurrency`
- `journalEntryId`
- `fiscalYear`

**Relations**
- `(JournalEntry) -[:RECORDS]- --> (BillingDocument)`
- `(JournalEntry) -[:HAS_JOURNAL_ENTRY]- <-- (Customer)`

### `Payment`

**Attributes**
- `companyCode`
- `amountTransactionCurrency`
- `paymentId`

**Relations**
- `(Payment) -[:MADE_PAYMENT]- <-- (Customer)`

### `Plant`

**Attributes**
- `plantId`
- `plantName`

**Relations**
- `(Plant) -[:REFERENCES_PLANT]- <-- (SalesOrderItem, DeliveryItem)`
- `(Plant) -[:DISPATCHED_FROM]- <-- (Delivery)`
- `(Plant) -[:SOURCED_FROM]- <-- (SalesOrder)`
- `(Plant) -[:STOCKED_AT]- <-- (Product)`

### `Product`

**Attributes**
- `profitCenter`
- `productId`
- `productName`
- `productType`

**Relations**
- `(Product) -[:INCLUDES]- <-- (SalesOrder)`
- `(Product) -[:REFERENCES_PRODUCT]- <-- (SalesOrderItem, DeliveryItem, BillingItem)`
- `(Product) -[:SHIPS]- <-- (Delivery)`
- `(Product) -[:INVOICES]- <-- (BillingDocument)`
- `(Product) -[:STOCKED_AT]- --> (Plant)`

### `SalesOrder`

**Attributes**
- `salesOrderId`
- `currency`
- `orderDate`
- `totalNetAmount`

**Relations**
- `(SalesOrder) -[:FULFILLS]- <-- (Delivery)`
- `(SalesOrder) -[:HAS_SALE_ITEM]- --> (SalesOrderItem)`
- `(SalesOrder) -[:SOURCED_FROM]- --> (Plant)`
- `(SalesOrder) -[:INCLUDES]- --> (Product)`
- `(SalesOrder) -[:PLACED]- <-- (Customer)`

### `SalesOrderItem`

**Attributes**
- `salesOrderItemUid`
- `salesOrderId`
- `productId`
- `netAmount`
- `plantId`
- `salesOrderItemId`
- `confirmedDeliveryDate`

**Relations**
- `(SalesOrderItem) -[:REFERENCES_PRODUCT]- --> (Product)`
- `(SalesOrderItem) -[:REFERENCES_PLANT]- --> (Plant)`
- `(SalesOrderItem) -[:HAS_SALE_ITEM]- <-- (SalesOrder)`
