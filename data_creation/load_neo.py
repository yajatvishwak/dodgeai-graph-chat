"""Load all Postgres data into Neo4j using propose_graph_model_2 mappings."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from decimal import Decimal

import psycopg
from dotenv import load_dotenv
from neo4j import GraphDatabase
from psycopg.rows import dict_row


CONSTRAINTS: list[tuple[str, str, str]] = [
    ("customer_id_unique", "Customer", "customerId"),
    ("address_id_unique", "Address", "addressId"),
    ("product_id_unique", "Product", "productId"),
    ("plant_id_unique", "Plant", "plantId"),
    ("sales_order_id_unique", "SalesOrder", "salesOrderId"),
    ("sales_order_item_id_unique", "SalesOrderItem", "salesOrderItemUid"),
    ("delivery_id_unique", "Delivery", "deliveryId"),
    ("delivery_item_id_unique", "DeliveryItem", "deliveryItemUid"),
    ("billing_document_id_unique", "BillingDocument", "billingDocumentId"),
    ("billing_item_id_unique", "BillingItem", "billingItemUid"),
    ("journal_entry_id_unique", "JournalEntry", "journalEntryId"),
    ("payment_id_unique", "Payment", "paymentId"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Path to .env (default: python-dotenv search behavior).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for Postgres fetch and Neo4j writes.",
    )
    parser.add_argument(
        "--wipe",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Wipe existing Neo4j graph before loading (default: true).",
    )
    return parser.parse_args()


def require_env(keys: list[str]) -> None:
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def connect_postgres() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ["PGHOST"],
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        autocommit=False,
    )


def connect_neo4j():
    return GraphDatabase.driver(
        os.environ["NEO4J_BOLT_URL"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )


def iter_query_batches(
    conn: psycopg.Connection, query: str, batch_size: int
) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query)
        while True:
            rows = cur.fetchmany(batch_size)
            if not rows:
                break
            # Neo4j Python driver doesn't accept `decimal.Decimal` parameters;
            # convert to float (Neo4j numeric type compatible).
            rows = [
                {k: (float(v) if isinstance(v, Decimal) else v) for k, v in row.items()}
                for row in rows
            ]
            yield rows


def run_write_batches(session, query: str, rows: list[dict[str, Any]]) -> None:
    def _tx(tx, payload: list[dict[str, Any]]) -> None:
        tx.run(query, rows=payload).consume()

    session.execute_write(_tx, rows)


def create_constraints(session) -> None:
    for name, label, prop in CONSTRAINTS:
        query = (
            f"CREATE CONSTRAINT {name} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
        )
        session.run(query).consume()


def wipe_graph(session) -> None:
    session.run("MATCH (n) DETACH DELETE n").consume()


LOAD_STEPS: list[dict[str, str]] = [
    {
        "name": "Customer nodes",
        "sql": """
            SELECT
              bp.customer AS "customerId",
              MIN(bp."businessPartnerFullName") AS "fullName",
              MIN(bp."businessPartnerGrouping") AS "grouping",
              MIN(bp.industry) AS industry,
              BOOL_OR(bp."businessPartnerIsBlocked") AS "isBlocked",
              MIN(cca."companyCode") AS "companyCode",
              MIN(csa."salesOrganization") AS "salesOrganization",
              MIN(csa."distributionChannel") AS "distributionChannel",
              MIN(csa.division) AS division,
              MIN(csa."customerPaymentTerms") AS "paymentTerms",
              MIN(csa.currency) AS currency
            FROM business_partners bp
            LEFT JOIN customer_company_assignments cca
              ON cca.customer = bp.customer
            LEFT JOIN customer_sales_area_assignments csa
              ON csa.customer = bp.customer
            WHERE bp.customer IS NOT NULL
            GROUP BY bp.customer
        """,
        "cypher": """
            UNWIND $rows AS row
            MERGE (c:Customer {customerId: row.customerId})
            SET c.fullName = row.fullName,
                c.grouping = row.grouping,
                c.industry = row.industry,
                c.isBlocked = row.isBlocked,
                c.companyCode = row.companyCode,
                c.salesOrganization = row.salesOrganization,
                c.distributionChannel = row.distributionChannel,
                c.division = row.division,
                c.paymentTerms = row.paymentTerms,
                c.currency = row.currency
        """,
    },
    {
        "name": "Address nodes",
        "sql": """
            SELECT
              bpa."addressId" AS "addressId",
              bpa."cityName" AS city,
              bpa.country AS country,
              bpa."postalCode" AS "postalCode",
              bpa.region AS region,
              bpa."streetName" AS street,
              bpa."validityStartDate" AS "validFrom",
              bpa."validityEndDate" AS "validTo"
            FROM business_partner_addresses bpa
            WHERE bpa."addressId" IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MERGE (a:Address {addressId: row.addressId})
            SET a.city = row.city,
                a.country = row.country,
                a.postalCode = row.postalCode,
                a.region = row.region,
                a.street = row.street,
                a.validFrom = row.validFrom,
                a.validTo = row.validTo
        """,
    },
    {
        "name": "Plant nodes",
        "sql": """
            SELECT
              p.plant AS "plantId",
              MIN(p."plantName") AS "plantName"
            FROM plants p
            GROUP BY p.plant
        """,
        "cypher": """
            UNWIND $rows AS row
            MERGE (p:Plant {plantId: row.plantId})
            SET p.plantName = row.plantName
        """,
    },
    {
        "name": "Product nodes",
        "sql": """
            SELECT
              p.product AS "productId",
              MIN(pd."productDescription") FILTER (WHERE UPPER(pd.language) = 'EN') AS "productName",
              MIN(p."productType") AS "productType",
              MIN(pp."profitCenter") AS "profitCenter"
            FROM products p
            LEFT JOIN product_descriptions pd
              ON pd.product = p.product
            LEFT JOIN product_plants pp
              ON pp.product = p.product
            GROUP BY p.product
        """,
        "cypher": """
            UNWIND $rows AS row
            MERGE (p:Product {productId: row.productId})
            SET p.productName = row.productName,
                p.productType = row.productType,
                p.profitCenter = row.profitCenter
        """,
    },
    {
        "name": "SalesOrder nodes",
        "sql": """
            SELECT
              soh."salesOrder" AS "salesOrderId",
              soh."creationDate" AS "orderDate",
              (soh."totalNetAmount"::double precision) AS "totalNetAmount",
              soh."transactionCurrency" AS currency
            FROM sales_order_headers soh
        """,
        "cypher": """
            UNWIND $rows AS row
            MERGE (s:SalesOrder {salesOrderId: row.salesOrderId})
            SET s.orderDate = row.orderDate,
                s.totalNetAmount = row.totalNetAmount,
                s.currency = row.currency
        """,
    },
    {
        "name": "SalesOrderItem nodes",
        "sql": """
            SELECT
              soi."salesOrder" AS "salesOrderId",
              soi."salesOrderItem" AS "salesOrderItemId",
              (soi."salesOrder"::text || ':' || soi."salesOrderItem"::text) AS "salesOrderItemUid",
              soi.material AS "productId",
              soi."productionPlant" AS "plantId",
              soi."netAmount" AS "netAmount",
              MIN(sosl."confirmedDeliveryDate")::text AS "confirmedDeliveryDate"
            FROM sales_order_items soi
            LEFT JOIN sales_order_schedule_lines sosl
              ON sosl."salesOrder" = soi."salesOrder"
             AND sosl."salesOrderItem" = soi."salesOrderItem"
            GROUP BY
              soi."salesOrder",
              soi."salesOrderItem",
              soi.material,
              soi."productionPlant",
              soi."netAmount"
        """,
        "cypher": """
            UNWIND $rows AS row
            MERGE (si:SalesOrderItem {salesOrderItemUid: row.salesOrderItemUid})
            SET si.salesOrderId = row.salesOrderId,
                si.salesOrderItemId = row.salesOrderItemId,
                si.productId = row.productId,
                si.plantId = row.plantId,
                si.netAmount = row.netAmount,
                si.confirmedDeliveryDate = row.confirmedDeliveryDate
        """,
    },
    {
        "name": "SalesOrder HAS_SALE_ITEM SalesOrderItem",
        "sql": """
            SELECT DISTINCT
              (soi."salesOrder"::text || ':' || soi."salesOrderItem"::text) AS "salesOrderItemUid",
              soi."salesOrder" AS "salesOrderId"
            FROM sales_order_items soi
            WHERE soi."salesOrder" IS NOT NULL
              AND soi."salesOrderItem" IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (s:SalesOrder {salesOrderId: row.salesOrderId})
            MATCH (si:SalesOrderItem {salesOrderItemUid: row.salesOrderItemUid})
            MERGE (s)-[:HAS_SALE_ITEM]->(si)
        """,
    },
    {
        "name": "SalesOrderItem REFERENCES_PRODUCT/PLANT",
        "sql": """
            SELECT DISTINCT
              (soi."salesOrder"::text || ':' || soi."salesOrderItem"::text) AS "salesOrderItemUid",
              soi.material AS "productId",
              soi."productionPlant" AS "plantId"
            FROM sales_order_items soi
            WHERE soi.material IS NOT NULL
              AND soi."productionPlant" IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (si:SalesOrderItem {salesOrderItemUid: row.salesOrderItemUid})
            MATCH (p:Product {productId: row.productId})
            MERGE (si)-[:REFERENCES_PRODUCT]->(p)
            WITH si, row
            MATCH (pl:Plant {plantId: row.plantId})
            MERGE (si)-[:REFERENCES_PLANT]->(pl)
        """,
    },
    {
        "name": "Delivery nodes",
        "sql": """
            SELECT
              odh."deliveryDocument" AS "deliveryId",
              odh."creationDateTime" AS "deliveryDate",
              odh."shippingPoint" AS "shippingPoint",
              odh."overallGoodsMovementStatus" AS "goodsMovementStatus"
            FROM outbound_delivery_headers odh
        """,
        "cypher": """
            UNWIND $rows AS row
            MERGE (d:Delivery {deliveryId: row.deliveryId})
            SET d.deliveryDate = row.deliveryDate,
                d.shippingPoint = row.shippingPoint,
                d.goodsMovementStatus = row.goodsMovementStatus
        """,
    },
    {
        "name": "DeliveryItem nodes",
        "sql": """
            SELECT
              odi."deliveryDocument" AS "deliveryId",
              odi."deliveryDocumentItem" AS "deliveryItemId",
              (odi."deliveryDocument"::text || ':' || odi."deliveryDocumentItem"::text) AS "deliveryItemUid",
              soi.material AS "productId",
              odi.plant AS "plantId"
            FROM outbound_delivery_items odi
            LEFT JOIN sales_order_items soi
              ON soi."salesOrder" = odi."referenceSdDocument"
             AND soi."salesOrderItem" = odi."referenceSdDocumentItem"
            WHERE odi."deliveryDocument" IS NOT NULL
              AND odi."deliveryDocumentItem" IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MERGE (di:DeliveryItem {deliveryItemUid: row.deliveryItemUid})
            SET di.deliveryId = row.deliveryId,
                di.deliveryItemId = row.deliveryItemId,
                di.productId = row.productId,
                di.plantId = row.plantId
        """,
    },
    {
        "name": "Delivery HAS_DELIVERY_ITEM DeliveryItem",
        "sql": """
            SELECT DISTINCT
              (odi."deliveryDocument"::text || ':' || odi."deliveryDocumentItem"::text) AS "deliveryItemUid",
              odi."deliveryDocument" AS "deliveryId"
            FROM outbound_delivery_items odi
            WHERE odi."deliveryDocument" IS NOT NULL
              AND odi."deliveryDocumentItem" IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (d:Delivery {deliveryId: row.deliveryId})
            MATCH (di:DeliveryItem {deliveryItemUid: row.deliveryItemUid})
            MERGE (d)-[:HAS_DELIVERY_ITEM]->(di)
        """,
    },
    {
        "name": "DeliveryItem REFERENCES_PRODUCT/PLANT",
        "sql": """
            SELECT DISTINCT
              (odi."deliveryDocument"::text || ':' || odi."deliveryDocumentItem"::text) AS "deliveryItemUid",
              soi.material AS "productId",
              odi.plant AS "plantId"
            FROM outbound_delivery_items odi
            LEFT JOIN sales_order_items soi
              ON soi."salesOrder" = odi."referenceSdDocument"
             AND soi."salesOrderItem" = odi."referenceSdDocumentItem"
            WHERE soi.material IS NOT NULL
              AND odi.plant IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (di:DeliveryItem {deliveryItemUid: row.deliveryItemUid})
            MATCH (p:Product {productId: row.productId})
            MERGE (di)-[:REFERENCES_PRODUCT]->(p)
            WITH di, row
            MATCH (pl:Plant {plantId: row.plantId})
            MERGE (di)-[:REFERENCES_PLANT]->(pl)
        """,
    },
    {
        "name": "BillingDocument nodes",
        "sql": """
            SELECT
              bdh."billingDocument" AS "billingDocumentId",
              bdh."billingDocumentDate" AS "billingDate",
              bdh."billingDocumentType" AS "billingType",
              bdh."companyCode" AS "companyCode",
              bdh."transactionCurrency" AS currency,
              (bdh."totalNetAmount"::double precision) AS "totalNetAmount",
              bdh."billingDocumentIsCancelled" AS "isCancelled",
              bdh."cancelledBillingDocument" AS "cancelledBillingDocumentId"
            FROM billing_document_headers bdh
        """,
        "cypher": """
            UNWIND $rows AS row
            MERGE (b:BillingDocument {billingDocumentId: row.billingDocumentId})
            SET b.billingDate = row.billingDate,
                b.billingType = row.billingType,
                b.companyCode = row.companyCode,
                b.currency = row.currency,
                b.totalNetAmount = row.totalNetAmount,
                b.isCancelled = row.isCancelled,
                b.cancelledBillingDocumentId = row.cancelledBillingDocumentId
        """,
    },
    {
        "name": "BillingItem nodes",
        "sql": """
            SELECT
              bdi."billingDocument" AS "billingDocumentId",
              bdi."billingDocumentItem" AS "billingItemId",
              (bdi."billingDocument"::text || ':' || bdi."billingDocumentItem"::text) AS "billingItemUid",
              bdi.material AS "productId",
              bdi."billingQuantity" AS "quantity",
              bdi."netAmount" AS "netAmount"
            FROM billing_document_items bdi
            WHERE bdi."billingDocument" IS NOT NULL
              AND bdi."billingDocumentItem" IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MERGE (bi:BillingItem {billingItemUid: row.billingItemUid})
            SET bi.billingDocumentId = row.billingDocumentId,
                bi.billingItemId = row.billingItemId,
                bi.productId = row.productId,
                bi.quantity = row.quantity,
                bi.netAmount = row.netAmount
        """,
    },
    {
        "name": "BillingDocument HAS_BILLING_ITEM BillingItem",
        "sql": """
            SELECT DISTINCT
              (bdi."billingDocument"::text || ':' || bdi."billingDocumentItem"::text) AS "billingItemUid",
              bdi."billingDocument" AS "billingDocumentId"
            FROM billing_document_items bdi
            WHERE bdi."billingDocument" IS NOT NULL
              AND bdi."billingDocumentItem" IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (b:BillingDocument {billingDocumentId: row.billingDocumentId})
            MATCH (bi:BillingItem {billingItemUid: row.billingItemUid})
            MERGE (b)-[:HAS_BILLING_ITEM]->(bi)
        """,
    },
    {
        "name": "BillingItem REFERENCES_PRODUCT",
        "sql": """
            SELECT DISTINCT
              (bdi."billingDocument"::text || ':' || bdi."billingDocumentItem"::text) AS "billingItemUid",
              bdi.material AS "productId"
            FROM billing_document_items bdi
            WHERE bdi.material IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (bi:BillingItem {billingItemUid: row.billingItemUid})
            MATCH (p:Product {productId: row.productId})
            MERGE (bi)-[:REFERENCES_PRODUCT]->(p)
        """,
    },
    {
        "name": "JournalEntry nodes",
        "sql": """
            SELECT
              (je."accountingDocument"::text || ':' || je."fiscalYear"::text) AS "journalEntryId",
              je."companyCode" AS "companyCode",
              je."fiscalYear" AS "fiscalYear",
              (je."amountInTransactionCurrency"::double precision) AS "amountTransactionCurrency"
            FROM journal_entry_items_accounts_receivable je
        """,
        "cypher": """
            UNWIND $rows AS row
            MERGE (j:JournalEntry {journalEntryId: row.journalEntryId})
            SET j.companyCode = row.companyCode,
                j.fiscalYear = row.fiscalYear,
                j.amountTransactionCurrency = row.amountTransactionCurrency
        """,
    },
    {
        "name": "Payment nodes",
        "sql": """
            SELECT
              p."accountingDocument" AS "paymentId",
              p."companyCode" AS "companyCode",
              (p."amountInTransactionCurrency"::double precision) AS "amountTransactionCurrency"
            FROM payments_accounts_receivable p
        """,
        "cypher": """
            UNWIND $rows AS row
            MERGE (p:Payment {paymentId: row.paymentId})
            SET p.companyCode = row.companyCode,
                p.amountTransactionCurrency = row.amountTransactionCurrency
        """,
    },
    {
        "name": "Customer HAS_ADDRESS Address",
        "sql": """
            SELECT DISTINCT
              bpa."businessPartner" AS "customerId",
              bpa."addressId" AS "addressId"
            FROM business_partner_addresses bpa
            WHERE bpa."businessPartner" IS NOT NULL
              AND bpa."addressId" IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (c:Customer {customerId: row.customerId})
            MATCH (a:Address {addressId: row.addressId})
            MERGE (c)-[:HAS_ADDRESS]->(a)
        """,
    },
    {
        "name": "Customer PLACED SalesOrder",
        "sql": """
            SELECT DISTINCT
              soh."soldToParty" AS "customerId",
              soh."salesOrder" AS "salesOrderId"
            FROM sales_order_headers soh
            WHERE soh."soldToParty" IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (c:Customer {customerId: row.customerId})
            MATCH (s:SalesOrder {salesOrderId: row.salesOrderId})
            MERGE (c)-[:PLACED]->(s)
        """,
    },
    {
        "name": "Customer BILLED_TO BillingDocument",
        "sql": """
            SELECT DISTINCT
              bdh."soldToParty" AS "customerId",
              bdh."billingDocument" AS "billingDocumentId"
            FROM billing_document_headers bdh
            WHERE bdh."soldToParty" IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (c:Customer {customerId: row.customerId})
            MATCH (b:BillingDocument {billingDocumentId: row.billingDocumentId})
            MERGE (c)-[:BILLED_TO]->(b)
        """,
    },
    {
        "name": "Customer HAS_JOURNAL_ENTRY JournalEntry",
        "sql": """
            SELECT DISTINCT
              je.customer AS "customerId",
              (je."accountingDocument"::text || ':' || je."fiscalYear"::text) AS "journalEntryId"
            FROM journal_entry_items_accounts_receivable je
            WHERE je.customer IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (c:Customer {customerId: row.customerId})
            MATCH (j:JournalEntry {journalEntryId: row.journalEntryId})
            MERGE (c)-[:HAS_JOURNAL_ENTRY]->(j)
        """,
    },
    {
        "name": "Customer MADE_PAYMENT Payment",
        "sql": """
            SELECT DISTINCT
              p.customer AS "customerId",
              p."accountingDocument" AS "paymentId"
            FROM payments_accounts_receivable p
            WHERE p.customer IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (c:Customer {customerId: row.customerId})
            MATCH (p:Payment {paymentId: row.paymentId})
            MERGE (c)-[:MADE_PAYMENT]->(p)
        """,
    },
    {
        "name": "SalesOrder INCLUDES Product",
        "sql": """
            SELECT DISTINCT
              soi."salesOrder" AS "salesOrderId",
              soi.material AS "productId"
            FROM sales_order_items soi
            WHERE soi.material IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (s:SalesOrder {salesOrderId: row.salesOrderId})
            MATCH (p:Product {productId: row.productId})
            MERGE (s)-[:INCLUDES]->(p)
        """,
    },
    {
        "name": "SalesOrder SOURCED_FROM Plant",
        "sql": """
            SELECT DISTINCT
              soi."salesOrder" AS "salesOrderId",
              soi."productionPlant" AS "plantId"
            FROM sales_order_items soi
            WHERE soi."productionPlant" IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (s:SalesOrder {salesOrderId: row.salesOrderId})
            MATCH (p:Plant {plantId: row.plantId})
            MERGE (s)-[:SOURCED_FROM]->(p)
        """,
    },
    {
        "name": "Delivery FULFILLS SalesOrder",
        "sql": """
            SELECT DISTINCT
              odi."deliveryDocument" AS "deliveryId",
              odi."referenceSdDocument" AS "salesOrderId"
            FROM outbound_delivery_items odi
            WHERE odi."referenceSdDocument" IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (d:Delivery {deliveryId: row.deliveryId})
            MATCH (s:SalesOrder {salesOrderId: row.salesOrderId})
            MERGE (d)-[:FULFILLS]->(s)
        """,
    },
    {
        "name": "Delivery SHIPS Product",
        "sql": """
            SELECT DISTINCT
              odi."deliveryDocument" AS "deliveryId",
              soi.material AS "productId"
            FROM outbound_delivery_items odi
            LEFT JOIN sales_order_items soi
              ON soi."salesOrder" = odi."referenceSdDocument"
             AND soi."salesOrderItem" = odi."referenceSdDocumentItem"
            WHERE soi.material IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (d:Delivery {deliveryId: row.deliveryId})
            MATCH (p:Product {productId: row.productId})
            MERGE (d)-[:SHIPS]->(p)
        """,
    },
    {
        "name": "Delivery DISPATCHED_FROM Plant",
        "sql": """
            SELECT DISTINCT
              odi."deliveryDocument" AS "deliveryId",
              odi.plant AS "plantId"
            FROM outbound_delivery_items odi
            WHERE odi.plant IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (d:Delivery {deliveryId: row.deliveryId})
            MATCH (p:Plant {plantId: row.plantId})
            MERGE (d)-[:DISPATCHED_FROM]->(p)
        """,
    },
    {
        "name": "BillingDocument BILLS_FOR SalesOrder",
        "sql": """
            SELECT DISTINCT
              bdi."billingDocument" AS "billingDocumentId",
              bdi."referenceSdDocument" AS "salesOrderId"
            FROM billing_document_items bdi
            WHERE bdi."referenceSdDocument" IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (b:BillingDocument {billingDocumentId: row.billingDocumentId})
            MATCH (s:SalesOrder {salesOrderId: row.salesOrderId})
            MERGE (b)-[:BILLS_FOR]->(s)
        """,
    },
    {
        "name": "BillingDocument INVOICES Product",
        "sql": """
            SELECT DISTINCT
              bdi."billingDocument" AS "billingDocumentId",
              bdi.material AS "productId"
            FROM billing_document_items bdi
            WHERE bdi.material IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (b:BillingDocument {billingDocumentId: row.billingDocumentId})
            MATCH (p:Product {productId: row.productId})
            MERGE (b)-[:INVOICES]->(p)
        """,
    },
    {
        "name": "BillingDocument CANCELS BillingDocument",
        "sql": """
            SELECT DISTINCT
              bdc."billingDocument" AS "billingDocumentId",
              bdc."cancelledBillingDocument" AS "cancelledBillingDocumentId"
            FROM billing_document_cancellations bdc
            WHERE bdc."cancelledBillingDocument" IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (src:BillingDocument {billingDocumentId: row.billingDocumentId})
            MATCH (dst:BillingDocument {billingDocumentId: row.cancelledBillingDocumentId})
            MERGE (src)-[:CANCELS]->(dst)
        """,
    },
    {
        "name": "JournalEntry RECORDS BillingDocument",
        "sql": """
            SELECT DISTINCT
              (je."accountingDocument"::text || ':' || je."fiscalYear"::text) AS "journalEntryId",
              je."referenceDocument" AS "billingDocumentId"
            FROM journal_entry_items_accounts_receivable je
            WHERE je."referenceDocument" IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (j:JournalEntry {journalEntryId: row.journalEntryId})
            MATCH (b:BillingDocument {billingDocumentId: row.billingDocumentId})
            MERGE (j)-[:RECORDS]->(b)
        """,
    },
    {
        "name": "Payment SETTLES BillingDocument",
        "sql": """
            SELECT DISTINCT
              p."accountingDocument" AS "paymentId",
              p."invoiceReference" AS "billingDocumentId"
            FROM payments_accounts_receivable p
            WHERE p."invoiceReference" IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (p:Payment {paymentId: row.paymentId})
            MATCH (b:BillingDocument {billingDocumentId: row.billingDocumentId})
            MERGE (p)-[:SETTLES]->(b)
        """,
    },
    {
        "name": "Product STOCKED_AT Plant",
        "sql": """
            SELECT DISTINCT
              pp.product AS "productId",
              pp.plant AS "plantId"
            FROM product_plants pp
            WHERE pp.product IS NOT NULL
              AND pp.plant IS NOT NULL
        """,
        "cypher": """
            UNWIND $rows AS row
            MATCH (p:Product {productId: row.productId})
            MATCH (pl:Plant {plantId: row.plantId})
            MERGE (p)-[:STOCKED_AT]->(pl)
        """,
    },
]


def run_load(
    pg_conn: psycopg.Connection,
    neo4j_session,
    batch_size: int,
) -> None:
    for step in LOAD_STEPS:
        total = 0
        for batch in iter_query_batches(pg_conn, step["sql"], batch_size):
            run_write_batches(neo4j_session, step["cypher"], batch)
            total += len(batch)
        print(f"{step['name']}: rows processed={total}")


def verify_counts(session) -> None:
    labels = [
        "Customer",
        "Address",
        "Product",
        "Plant",
        "SalesOrder",
        "Delivery",
        "BillingDocument",
        "JournalEntry",
        "Payment",
    ]
    print("Label counts:")
    for label in labels:
        rec = session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()
        print(f"  {label}: {rec['c'] if rec else 0}")

    placed = session.run(
        "MATCH (:Customer)-[r:PLACED]->(:SalesOrder) RETURN count(r) AS c"
    ).single()
    settles = session.run(
        "MATCH (:Payment)-[r:SETTLES]->(:BillingDocument) RETURN count(r) AS c"
    ).single()
    print(f"Relationship count Customer-[:PLACED]->SalesOrder: {placed['c'] if placed else 0}")
    print(
        f"Relationship count Payment-[:SETTLES]->BillingDocument: {settles['c'] if settles else 0}"
    )


def main() -> None:
    args = parse_args()

    if args.env_file is not None:
        load_dotenv(args.env_file)
    else:
        load_dotenv()

    require_env(["PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD"])
    require_env(["NEO4J_BOLT_URL", "NEO4J_USER", "NEO4J_PASSWORD"])

    neo4j_db = os.environ.get("NEO4J_DATABASE", "neo4j")

    pg_conn = connect_postgres()
    driver = connect_neo4j()
    try:
        with driver.session(database=neo4j_db) as session:
            if args.wipe:
                print("Wiping Neo4j graph...")
                wipe_graph(session)

            print("Creating constraints...")
            create_constraints(session)

            print("Loading graph data...")
            run_load(pg_conn, session, args.batch_size)

            print("Verification...")
            verify_counts(session)
    finally:
        pg_conn.close()
        driver.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
