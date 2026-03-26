graph model

customer
(from bp + company assign + sales area)
customerid pk
fullname
grouping
industry
isblocked
companycode
salesorg
distributionchannel
division
paymentterms
currency

address
addressid pk
city
country
postalcode
region
street
validfrom
validto

product
(products + desc en + plants)
productid pk
productname (flattened)
producttype
profitcenter

plant
plantid pk
plantname

sales order

salesorderid pk
orderdate
totalnetamount
currency

items
salesorderitemid
productid
plantid
netamount
confirmeddeliverydate

delivery

deliveryid pk
deliverydate
shippingpoint
goodsmovementstatus

items
deliveryitemid
productid
plantid

billing document

billingdocumentid pk
billingdate
billingtype
companycode
currency
totalnetamount
iscancelled
cancelledbillingdocumentid

items
billingitemid
productid
quantity
netamount

journal entry

journalentryid (doc + fiscalyear)
companycode
fiscalyear
amounttransactioncurrency

payment

paymentid (doc only)
companycode
amounttransactioncurrency

customer has address
customer placed salesorder
customer billed to billingdocument
customer has journalentry
customer made payment

salesorder includes product
salesorder sourced from plant

delivery fulfills salesorder
delivery ships product
delivery from plant

billingdocument bills for salesorder
billingdocument invoices product
billingdocument cancels billingdocument

journalentry records billingdocument
payment settles billingdocument

product stocked at plant

customer salesorder (1)
salesorder product (1)
salesorder billing (1)
customer billing (1)

billing payment (1)

customer salesorder plant (2)

product plant (1)

salesorder delivery (1)

customer salesorder delivery product (3)

customer salesorder billing journal (3)
