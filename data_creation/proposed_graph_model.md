Graph Model Design

Nodes (11 types)

Node Label

Source Dataset

Primary Key

Customer

business_partners

id (= customer field)

Product

products + product_descriptions

id (= product field)

Plant

plants

id (= plant field)

SalesOrder

sales_order_headers

id (= salesOrder)

SalesOrderItem

sales_order_items

uid (salesOrder:item)

Delivery

outbound_delivery_headers

id (= deliveryDocument)

DeliveryItem

outbound_delivery_items

uid (deliveryDoc:item normalized)

BillingDocument

billing_document_headers + cancellations

id (= billingDocument)

BillingDocumentItem

billing_document_items

uid (billingDoc:item)

JournalEntry

journal_entry_items (aggregated by doc)

id (accountingDoc:fiscalYear)

ClearingDocument

clearing refs from journal_entry_items

id (clearingDoc:fiscalYear)

Relationships (17 types)

Document-level flow (1-2 hop traversal):

(Customer)-[:PLACED]->(SalesOrder) -- via soldToParty

(SalesOrder)-[:DELIVERED_VIA]->(Delivery) -- derived from delivery items

(Delivery)-[:BILLED_IN]->(BillingDocument) -- derived from billing items

(BillingDocument)-[:RECORDED_AS]->(JournalEntry) -- via accountingDocument/referenceDocument

(BillingDocument)-[:BILLED_TO]->(Customer) -- via soldToParty

(JournalEntry)-[:CLEARED_BY]->(ClearingDocument) -- via clearingAccountingDocument

Item containment:

(SalesOrder)-[:HAS_ITEM]->(SalesOrderItem)

(Delivery)-[:HAS_ITEM]->(DeliveryItem)

(BillingDocument)-[:HAS_ITEM]->(BillingDocumentItem)

Item-level flow (precise tracing):

(DeliveryItem)-[:FULFILLS]->(SalesOrderItem) -- via referenceSdDocument + item (normalized)

(BillingDocumentItem)-[:BILLS]->(DeliveryItem) -- via referenceSdDocument + item (normalized)

Product/Master data:

(SalesOrderItem)-[:FOR_PRODUCT]->(Product)

(BillingDocumentItem)-[:FOR_PRODUCT]->(Product)

(SalesOrderItem)-[:FROM_PLANT]->(Plant)

(DeliveryItem)-[:FROM_PLANT]->(Plant)

(Product)-[:AVAILABLE_AT]->(Plant) -- from product_plants

(Customer)-[:HAS_ADDRESS]->(Address) -- optional, from business_partner_addresses
