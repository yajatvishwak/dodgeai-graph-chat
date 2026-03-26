# Timestamp Normalization Report

Leaf type paths use dot notation; list branches are named `path[]`. 
Scalar elements inside a list share the path `parent[]` (union of observed types).

- Generated at (UTC): `2026-03-26T05:29:10+00:00`
- Input root: `/Users/yajat/Documents/Code/dodge-assignment/data_creation/sap-o2c-data`
- Output root (cleaned JSONL): `/Users/yajat/Documents/Code/dodge-assignment/data/cleaned`
- Report path: `/Users/yajat/Documents/Code/dodge-assignment/data/preprocess_summary.md`

## Summary by Table

| table | file_count | record_count | malformed_lines | normalized_string_timestamps | flattened_nested_timestamp_objects | nested_path_keys_unique | nested_path_observations | unique_leaf_paths |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| billing_document_cancellations | 1 | 80 | 0 | 240 | 80 | 0 | 0 | 14 |
| billing_document_headers | 2 | 163 | 0 | 489 | 163 | 0 | 0 | 14 |
| billing_document_items | 2 | 245 | 0 | 0 | 0 | 0 | 0 | 9 |
| business_partner_addresses | 1 | 8 | 0 | 16 | 0 | 0 | 0 | 20 |
| business_partners | 1 | 8 | 0 | 16 | 8 | 0 | 0 | 19 |
| customer_company_assignments | 1 | 8 | 0 | 0 | 0 | 0 | 0 | 13 |
| customer_sales_area_assignments | 1 | 28 | 0 | 0 | 0 | 0 | 0 | 19 |
| journal_entry_items_accounts_receivable | 4 | 123 | 0 | 489 | 0 | 0 | 0 | 22 |
| outbound_delivery_headers | 1 | 86 | 0 | 172 | 172 | 0 | 0 | 13 |
| outbound_delivery_items | 2 | 137 | 0 | 0 | 0 | 0 | 0 | 11 |
| payments_accounts_receivable | 1 | 120 | 0 | 360 | 0 | 0 | 0 | 23 |
| plants | 1 | 44 | 0 | 0 | 0 | 0 | 0 | 14 |
| product_descriptions | 2 | 69 | 0 | 0 | 0 | 0 | 0 | 3 |
| product_plants | 4 | 3036 | 0 | 0 | 0 | 0 | 0 | 9 |
| product_storage_locations | 18 | 16723 | 0 | 0 | 0 | 0 | 0 | 5 |
| products | 2 | 69 | 0 | 207 | 0 | 0 | 0 | 17 |
| sales_order_headers | 1 | 100 | 0 | 400 | 0 | 0 | 0 | 24 |
| sales_order_items | 2 | 167 | 0 | 0 | 0 | 0 | 0 | 13 |
| sales_order_schedule_lines | 2 | 179 | 0 | 167 | 0 | 0 | 0 | 6 |

## Per-Table Details

### billing_document_cancellations

#### Leaf Paths and Types

- `accountingDocument`: `str`
- `billingDocument`: `str`
- `billingDocumentDate`: `str`
- `billingDocumentIsCancelled`: `bool`
- `billingDocumentType`: `str`
- `cancelledBillingDocument`: `str`
- `companyCode`: `str`
- `creationDate`: `str`
- `creationTime`: `str`
- `fiscalYear`: `str`
- `lastChangeDateTime`: `str`
- `soldToParty`: `str`
- `totalNetAmount`: `str`
- `transactionCurrency`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### billing_document_headers

#### Leaf Paths and Types

- `accountingDocument`: `str`
- `billingDocument`: `str`
- `billingDocumentDate`: `str`
- `billingDocumentIsCancelled`: `bool`
- `billingDocumentType`: `str`
- `cancelledBillingDocument`: `str`
- `companyCode`: `str`
- `creationDate`: `str`
- `creationTime`: `str`
- `fiscalYear`: `str`
- `lastChangeDateTime`: `str`
- `soldToParty`: `str`
- `totalNetAmount`: `str`
- `transactionCurrency`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### billing_document_items

#### Leaf Paths and Types

- `billingDocument`: `str`
- `billingDocumentItem`: `str`
- `billingQuantity`: `str`
- `billingQuantityUnit`: `str`
- `material`: `str`
- `netAmount`: `str`
- `referenceSdDocument`: `str`
- `referenceSdDocumentItem`: `str`
- `transactionCurrency`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### business_partner_addresses

#### Leaf Paths and Types

- `addressId`: `str`
- `addressTimeZone`: `str`
- `addressUuid`: `str`
- `businessPartner`: `str`
- `cityName`: `str`
- `country`: `str`
- `poBox`: `str`
- `poBoxDeviatingCityName`: `str`
- `poBoxDeviatingCountry`: `str`
- `poBoxDeviatingRegion`: `str`
- `poBoxIsWithoutNumber`: `bool`
- `poBoxLobbyName`: `str`
- `poBoxPostalCode`: `str`
- `postalCode`: `str`
- `region`: `str`
- `streetName`: `str`
- `taxJurisdiction`: `str`
- `transportZone`: `str`
- `validityEndDate`: `str`
- `validityStartDate`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### business_partners

#### Leaf Paths and Types

- `businessPartner`: `str`
- `businessPartnerCategory`: `str`
- `businessPartnerFullName`: `str`
- `businessPartnerGrouping`: `str`
- `businessPartnerIsBlocked`: `bool`
- `businessPartnerName`: `str`
- `correspondenceLanguage`: `str`
- `createdByUser`: `str`
- `creationDate`: `str`
- `creationTime`: `str`
- `customer`: `str`
- `firstName`: `str`
- `formOfAddress`: `str`
- `industry`: `str`
- `isMarkedForArchiving`: `bool`
- `lastChangeDate`: `str`
- `lastName`: `str`
- `organizationBpName1`: `str`
- `organizationBpName2`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### customer_company_assignments

#### Leaf Paths and Types

- `accountingClerk`: `str`
- `accountingClerkFaxNumber`: `str`
- `accountingClerkInternetAddress`: `str`
- `accountingClerkPhoneNumber`: `str`
- `alternativePayerAccount`: `str`
- `companyCode`: `str`
- `customer`: `str`
- `customerAccountGroup`: `str`
- `deletionIndicator`: `bool`
- `paymentBlockingReason`: `str`
- `paymentMethodsList`: `str`
- `paymentTerms`: `str`
- `reconciliationAccount`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### customer_sales_area_assignments

#### Leaf Paths and Types

- `billingIsBlockedForCustomer`: `str`
- `completeDeliveryIsDefined`: `bool`
- `creditControlArea`: `str`
- `currency`: `str`
- `customer`: `str`
- `customerPaymentTerms`: `str`
- `deliveryPriority`: `str`
- `distributionChannel`: `str`
- `division`: `str`
- `exchangeRateType`: `str`
- `incotermsClassification`: `str`
- `incotermsLocation1`: `str`
- `salesDistrict`: `str`
- `salesGroup`: `str`
- `salesOffice`: `str`
- `salesOrganization`: `str`
- `shippingCondition`: `str`
- `slsUnlmtdOvrdelivIsAllwd`: `bool`
- `supplyingPlant`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### journal_entry_items_accounts_receivable

#### Leaf Paths and Types

- `accountingDocument`: `str`
- `accountingDocumentItem`: `str`
- `accountingDocumentType`: `str`
- `amountInCompanyCodeCurrency`: `str`
- `amountInTransactionCurrency`: `str`
- `assignmentReference`: `str`
- `clearingAccountingDocument`: `str`
- `clearingDate`: `null|str`
- `clearingDocFiscalYear`: `str`
- `companyCode`: `str`
- `companyCodeCurrency`: `str`
- `costCenter`: `str`
- `customer`: `str`
- `documentDate`: `str`
- `financialAccountType`: `str`
- `fiscalYear`: `str`
- `glAccount`: `str`
- `lastChangeDateTime`: `str`
- `postingDate`: `str`
- `profitCenter`: `str`
- `referenceDocument`: `str`
- `transactionCurrency`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### outbound_delivery_headers

#### Leaf Paths and Types

- `actualGoodsMovementDate`: `null|str`
- `actualGoodsMovementTime`: `null|str`
- `creationDate`: `str`
- `creationTime`: `str`
- `deliveryBlockReason`: `str`
- `deliveryDocument`: `str`
- `hdrGeneralIncompletionStatus`: `str`
- `headerBillingBlockReason`: `str`
- `lastChangeDate`: `null|str`
- `overallGoodsMovementStatus`: `str`
- `overallPickingStatus`: `str`
- `overallProofOfDeliveryStatus`: `str`
- `shippingPoint`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### outbound_delivery_items

#### Leaf Paths and Types

- `actualDeliveryQuantity`: `str`
- `batch`: `str`
- `deliveryDocument`: `str`
- `deliveryDocumentItem`: `str`
- `deliveryQuantityUnit`: `str`
- `itemBillingBlockReason`: `str`
- `lastChangeDate`: `null`
- `plant`: `str`
- `referenceSdDocument`: `str`
- `referenceSdDocumentItem`: `str`
- `storageLocation`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### payments_accounts_receivable

#### Leaf Paths and Types

- `accountingDocument`: `str`
- `accountingDocumentItem`: `str`
- `amountInCompanyCodeCurrency`: `str`
- `amountInTransactionCurrency`: `str`
- `assignmentReference`: `null`
- `clearingAccountingDocument`: `str`
- `clearingDate`: `str`
- `clearingDocFiscalYear`: `str`
- `companyCode`: `str`
- `companyCodeCurrency`: `str`
- `costCenter`: `null`
- `customer`: `str`
- `documentDate`: `str`
- `financialAccountType`: `str`
- `fiscalYear`: `str`
- `glAccount`: `str`
- `invoiceReference`: `null`
- `invoiceReferenceFiscalYear`: `null`
- `postingDate`: `str`
- `profitCenter`: `str`
- `salesDocument`: `null`
- `salesDocumentItem`: `null`
- `transactionCurrency`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### plants

#### Leaf Paths and Types

- `addressId`: `str`
- `defaultPurchasingOrganization`: `str`
- `distributionChannel`: `str`
- `division`: `str`
- `factoryCalendar`: `str`
- `isMarkedForArchiving`: `bool`
- `language`: `str`
- `plant`: `str`
- `plantCategory`: `str`
- `plantCustomer`: `str`
- `plantName`: `str`
- `plantSupplier`: `str`
- `salesOrganization`: `str`
- `valuationArea`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### product_descriptions

#### Leaf Paths and Types

- `language`: `str`
- `product`: `str`
- `productDescription`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### product_plants

#### Leaf Paths and Types

- `availabilityCheckType`: `str`
- `countryOfOrigin`: `str`
- `fiscalYearVariant`: `str`
- `mrpType`: `str`
- `plant`: `str`
- `product`: `str`
- `productionInvtryManagedLoc`: `str`
- `profitCenter`: `str`
- `regionOfOrigin`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### product_storage_locations

#### Leaf Paths and Types

- `dateOfLastPostedCntUnRstrcdStk`: `null`
- `physicalInventoryBlockInd`: `str`
- `plant`: `str`
- `product`: `str`
- `storageLocation`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### products

#### Leaf Paths and Types

- `baseUnit`: `str`
- `createdByUser`: `str`
- `creationDate`: `str`
- `crossPlantStatus`: `str`
- `crossPlantStatusValidityDate`: `null`
- `division`: `str`
- `grossWeight`: `str`
- `industrySector`: `str`
- `isMarkedForDeletion`: `bool`
- `lastChangeDate`: `str`
- `lastChangeDateTime`: `str`
- `netWeight`: `str`
- `product`: `str`
- `productGroup`: `str`
- `productOldId`: `str`
- `productType`: `str`
- `weightUnit`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### sales_order_headers

#### Leaf Paths and Types

- `createdByUser`: `str`
- `creationDate`: `str`
- `customerPaymentTerms`: `str`
- `deliveryBlockReason`: `str`
- `distributionChannel`: `str`
- `headerBillingBlockReason`: `str`
- `incotermsClassification`: `str`
- `incotermsLocation1`: `str`
- `lastChangeDateTime`: `str`
- `organizationDivision`: `str`
- `overallDeliveryStatus`: `str`
- `overallOrdReltdBillgStatus`: `str`
- `overallSdDocReferenceStatus`: `str`
- `pricingDate`: `str`
- `requestedDeliveryDate`: `str`
- `salesGroup`: `str`
- `salesOffice`: `str`
- `salesOrder`: `str`
- `salesOrderType`: `str`
- `salesOrganization`: `str`
- `soldToParty`: `str`
- `totalCreditCheckStatus`: `str`
- `totalNetAmount`: `str`
- `transactionCurrency`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### sales_order_items

#### Leaf Paths and Types

- `itemBillingBlockReason`: `str`
- `material`: `str`
- `materialGroup`: `str`
- `netAmount`: `str`
- `productionPlant`: `str`
- `requestedQuantity`: `str`
- `requestedQuantityUnit`: `str`
- `salesDocumentRjcnReason`: `str`
- `salesOrder`: `str`
- `salesOrderItem`: `str`
- `salesOrderItemCategory`: `str`
- `storageLocation`: `str`
- `transactionCurrency`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_

### sales_order_schedule_lines

#### Leaf Paths and Types

- `confdOrderQtyByMatlAvailCheck`: `str`
- `confirmedDeliveryDate`: `null|str`
- `orderQuantityUnit`: `str`
- `salesOrder`: `str`
- `salesOrderItem`: `str`
- `scheduleLine`: `str`

#### Nested Structure Visits (non-timestamp dict/list during normalization)

- _No nested visits recorded_
