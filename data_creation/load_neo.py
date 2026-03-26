#!/usr/bin/env python3
"""Load JSONL data directly into Neo4j as a clean SAP Order-to-Cash graph.

Reads all .jsonl part-files from data/ subdirectories, normalises values,
and creates a graph optimised for OTC flow traversal by an AI agent.

Usage:
    python load_to_neo4j.py [--batch-size 500] [--no-wipe]

Requires NEO4J_BOLT_URL, NEO4J_USER, NEO4J_PASSWORD in environment or .env.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

DATA_ROOT = Path(__file__).parent / "data"

ALL_SUBDIRS = [
    "business_partners",
    "customer_company_assignments",
    "customer_sales_area_assignments",
    "business_partner_addresses",
    "products",
    "product_descriptions",
    "product_plants",
    "product_storage_locations",
    "plants",
    "sales_order_headers",
    "sales_order_items",
    "sales_order_schedule_lines",
    "outbound_delivery_headers",
    "outbound_delivery_items",
    "billing_document_headers",
    "billing_document_items",
    "billing_document_cancellations",
    "journal_entry_items_accounts_receivable",
    "payments_accounts_receivable",
]

CONSTRAINTS = [
    ("Customer", "id"),
    ("Address", "id"),
    ("Product", "id"),
    ("Plant", "id"),
    ("SalesOrder", "id"),
    ("SalesOrderItem", "uid"),
    ("Delivery", "id"),
    ("DeliveryItem", "uid"),
    ("BillingDocument", "id"),
    ("BillingDocumentItem", "uid"),
    ("JournalEntry", "id"),
    ("ClearingDocument", "id"),
]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def read_jsonl(subdir: str) -> list[dict]:
    """Read every .jsonl file under *data/<subdir>* into a flat list."""
    folder = DATA_ROOT / subdir
    if not folder.is_dir():
        print(f"  WARNING: {folder} not found, skipping")
        return []
    records: list[dict] = []
    for fp in sorted(folder.glob("*.jsonl")):
        with fp.open(encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    records.append(json.loads(stripped))
                except json.JSONDecodeError:
                    pass
    return records


def clean(val):
    """Empty / whitespace-only strings → None; everything else passes through."""
    if isinstance(val, str) and val.strip() == "":
        return None
    return val


def to_float(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def norm_item(val) -> str | None:
    """Normalise SAP item numbers by stripping leading zeros: '000010' → '10'."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        return str(int(s))
    except ValueError:
        return s


def make_uid(*parts) -> str | None:
    """Composite key from parts joined by ':'.  Returns None if any part is None."""
    for p in parts:
        if p is None:
            return None
    return ":".join(str(p) for p in parts)


# ---------------------------------------------------------------------------
# Neo4j helpers
# ---------------------------------------------------------------------------

def write_batch(session, cypher: str, rows: list[dict], batch_size: int) -> int:
    total = 0
    for i in range(0, max(len(rows), 1), batch_size):
        chunk = rows[i : i + batch_size]
        if not chunk:
            break
        session.run(cypher, rows=chunk).consume()
        total += len(chunk)
    return total


def create_constraints(session) -> None:
    for label, prop in CONSTRAINTS:
        name = f"{label.lower()}_{prop}_unique"
        session.run(
            f"CREATE CONSTRAINT {name} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
        ).consume()


def wipe_graph(session) -> None:
    session.run("MATCH (n) DETACH DELETE n").consume()


# ---------------------------------------------------------------------------
# Read all JSONL data into memory
# ---------------------------------------------------------------------------

def read_all_data() -> dict[str, list[dict]]:
    data: dict[str, list[dict]] = {}
    for name in ALL_SUBDIRS:
        data[name] = read_jsonl(name)
        print(f"  {name}: {len(data[name])} records")
    return data


# ---------------------------------------------------------------------------
# Node loaders
# ---------------------------------------------------------------------------

def load_nodes(session, data: dict, bs: int) -> dict:
    """Create all graph nodes. Returns prepared row-lists needed by relationship loaders."""
    kept: dict = {}

    # ---- Customer ----
    cca_map = {}
    for r in data["customer_company_assignments"]:
        cid = clean(r.get("customer"))
        if cid:
            cca_map[cid] = r

    csa_first = {}
    for r in data["customer_sales_area_assignments"]:
        cid = clean(r.get("customer"))
        if cid and cid not in csa_first:
            csa_first[cid] = r

    rows = []
    for r in data["business_partners"]:
        cid = clean(r.get("customer"))
        if not cid:
            continue
        cc = cca_map.get(cid, {})
        cs = csa_first.get(cid, {})
        rows.append({
            "id": cid,
            "fullName": clean(r.get("businessPartnerFullName")),
            "name": clean(r.get("organizationBpName1")) or clean(r.get("businessPartnerName")),
            "grouping": clean(r.get("businessPartnerGrouping")),
            "category": clean(r.get("businessPartnerCategory")),
            "industry": clean(r.get("industry")),
            "isBlocked": r.get("businessPartnerIsBlocked", False),
            "creationDate": clean(r.get("creationDate")),
            "companyCode": clean(cc.get("companyCode")),
            "reconciliationAccount": clean(cc.get("reconciliationAccount")),
            "customerAccountGroup": clean(cc.get("customerAccountGroup")),
            "salesOrganization": clean(cs.get("salesOrganization")),
            "distributionChannel": clean(cs.get("distributionChannel")),
            "currency": clean(cs.get("currency")),
            "paymentTerms": clean(cs.get("customerPaymentTerms")),
        })
    n = write_batch(session, "UNWIND $rows AS r MERGE (c:Customer {id: r.id}) SET c += r", rows, bs)
    print(f"  Customer: {n}")

    # ---- Address ----
    rows_addr = []
    for r in data["business_partner_addresses"]:
        bp = clean(r.get("businessPartner"))
        aid = clean(r.get("addressId"))
        if not bp or not aid:
            continue
        rows_addr.append({
            "id": make_uid(bp, aid),
            "businessPartner": bp,
            "addressId": aid,
            "city": clean(r.get("cityName")),
            "country": clean(r.get("country")),
            "postalCode": clean(r.get("postalCode")),
            "region": clean(r.get("region")),
            "street": clean(r.get("streetName")),
        })
    n = write_batch(session, "UNWIND $rows AS r MERGE (a:Address {id: r.id}) SET a += r", rows_addr, bs)
    print(f"  Address: {n}")

    # ---- Product ----
    desc_map = {}
    for r in data["product_descriptions"]:
        pid = clean(r.get("product"))
        lang = (r.get("language") or "").upper()
        if pid and lang == "EN":
            desc_map[pid] = clean(r.get("productDescription"))

    prod_rows = []
    for r in data["products"]:
        pid = clean(r.get("product"))
        if not pid:
            continue
        prod_rows.append({
            "id": pid,
            "name": desc_map.get(pid),
            "type": clean(r.get("productType")),
            "group": clean(r.get("productGroup")),
            "baseUnit": clean(r.get("baseUnit")),
            "division": clean(r.get("division")),
            "grossWeight": to_float(r.get("grossWeight")),
            "netWeight": to_float(r.get("netWeight")),
            "weightUnit": clean(r.get("weightUnit")),
            "creationDate": clean(r.get("creationDate")),
        })
    n = write_batch(session, "UNWIND $rows AS r MERGE (p:Product {id: r.id}) SET p += r", prod_rows, bs)
    print(f"  Product: {n}")
    known_products = {r["id"] for r in prod_rows}

    # stub Products referenced by items but absent from the products master table
    extra_products: set[str] = set()
    for src in ("sales_order_items", "billing_document_items"):
        for r in data[src]:
            m = clean(r.get("material"))
            if m and m not in known_products:
                extra_products.add(m)
    if extra_products:
        stub = [{"id": pid} for pid in extra_products]
        n2 = write_batch(session, "UNWIND $rows AS r MERGE (p:Product {id: r.id})", stub, bs)
        print(f"  Product (stubs from item references): {n2}")
        known_products |= extra_products

    # ---- Plant ----
    plant_rows = []
    for r in data["plants"]:
        pid = clean(r.get("plant"))
        if not pid:
            continue
        plant_rows.append({
            "id": pid,
            "name": clean(r.get("plantName")),
            "salesOrganization": clean(r.get("salesOrganization")),
            "distributionChannel": clean(r.get("distributionChannel")),
            "division": clean(r.get("division")),
        })
    n = write_batch(session, "UNWIND $rows AS r MERGE (p:Plant {id: r.id}) SET p += r", plant_rows, bs)
    print(f"  Plant: {n}")
    known_plants = {r["id"] for r in plant_rows}

    extra_plants: set[str] = set()
    for r in data["sales_order_items"]:
        p = clean(r.get("productionPlant"))
        if p and p not in known_plants:
            extra_plants.add(p)
    for r in data["outbound_delivery_items"]:
        p = clean(r.get("plant"))
        if p and p not in known_plants:
            extra_plants.add(p)
    if extra_plants:
        stub = [{"id": pid} for pid in extra_plants]
        n2 = write_batch(session, "UNWIND $rows AS r MERGE (p:Plant {id: r.id})", stub, bs)
        print(f"  Plant (stubs from item references): {n2}")

    # ---- SalesOrder ----
    so_rows = []
    for r in data["sales_order_headers"]:
        sid = clean(r.get("salesOrder"))
        if not sid:
            continue
        so_rows.append({
            "id": sid,
            "type": clean(r.get("salesOrderType")),
            "salesOrganization": clean(r.get("salesOrganization")),
            "distributionChannel": clean(r.get("distributionChannel")),
            "division": clean(r.get("organizationDivision")),
            "creationDate": clean(r.get("creationDate")),
            "totalNetAmount": to_float(r.get("totalNetAmount")),
            "currency": clean(r.get("transactionCurrency")),
            "deliveryStatus": clean(r.get("overallDeliveryStatus")),
            "billingStatus": clean(r.get("overallOrdReltdBillgStatus")),
            "soldToParty": clean(r.get("soldToParty")),
            "paymentTerms": clean(r.get("customerPaymentTerms")),
            "requestedDeliveryDate": clean(r.get("requestedDeliveryDate")),
            "incotermsClassification": clean(r.get("incotermsClassification")),
            "incotermsLocation": clean(r.get("incotermsLocation1")),
        })
    n = write_batch(session, "UNWIND $rows AS r MERGE (s:SalesOrder {id: r.id}) SET s += r", so_rows, bs)
    print(f"  SalesOrder: {n}")

    # ---- SalesOrderItem ----
    sched_map: dict[tuple, dict] = {}
    for r in data["sales_order_schedule_lines"]:
        so = clean(r.get("salesOrder"))
        item = norm_item(r.get("salesOrderItem"))
        if not so or not item:
            continue
        dt = clean(r.get("confirmedDeliveryDate"))
        qty = to_float(r.get("confdOrderQtyByMatlAvailCheck"))
        key = (so, item)
        prev = sched_map.get(key)
        if prev is None or (dt and (prev["date"] is None or dt < prev["date"])):
            sched_map[key] = {"date": dt, "qty": qty}

    soi_rows = []
    for r in data["sales_order_items"]:
        so = clean(r.get("salesOrder"))
        item = norm_item(r.get("salesOrderItem"))
        if not so or not item:
            continue
        sched = sched_map.get((so, item), {})
        soi_rows.append({
            "uid": make_uid(so, item),
            "salesOrder": so,
            "item": item,
            "category": clean(r.get("salesOrderItemCategory")),
            "material": clean(r.get("material")),
            "quantity": to_float(r.get("requestedQuantity")),
            "quantityUnit": clean(r.get("requestedQuantityUnit")),
            "netAmount": to_float(r.get("netAmount")),
            "currency": clean(r.get("transactionCurrency")),
            "materialGroup": clean(r.get("materialGroup")),
            "plant": clean(r.get("productionPlant")),
            "storageLocation": clean(r.get("storageLocation")),
            "confirmedDeliveryDate": sched.get("date"),
            "confirmedQuantity": to_float(sched.get("qty")),
        })
    n = write_batch(session, "UNWIND $rows AS r MERGE (si:SalesOrderItem {uid: r.uid}) SET si += r", soi_rows, bs)
    print(f"  SalesOrderItem: {n}")
    kept["soi_rows"] = soi_rows

    # ---- Delivery ----
    del_rows = []
    for r in data["outbound_delivery_headers"]:
        did = clean(r.get("deliveryDocument"))
        if not did:
            continue
        del_rows.append({
            "id": did,
            "creationDate": clean(r.get("creationDate")),
            "actualGoodsMovementDate": clean(r.get("actualGoodsMovementDate")),
            "shippingPoint": clean(r.get("shippingPoint")),
            "goodsMovementStatus": clean(r.get("overallGoodsMovementStatus")),
            "pickingStatus": clean(r.get("overallPickingStatus")),
            "deliveryBlockReason": clean(r.get("deliveryBlockReason")),
        })
    n = write_batch(session, "UNWIND $rows AS r MERGE (d:Delivery {id: r.id}) SET d += r", del_rows, bs)
    print(f"  Delivery: {n}")

    # ---- DeliveryItem ----
    di_rows = []
    for r in data["outbound_delivery_items"]:
        did = clean(r.get("deliveryDocument"))
        item = norm_item(r.get("deliveryDocumentItem"))
        if not did or not item:
            continue
        di_rows.append({
            "uid": make_uid(did, item),
            "deliveryDocument": did,
            "item": item,
            "quantity": to_float(r.get("actualDeliveryQuantity")),
            "quantityUnit": clean(r.get("deliveryQuantityUnit")),
            "plant": clean(r.get("plant")),
            "storageLocation": clean(r.get("storageLocation")),
            "batch": clean(r.get("batch")),
            "referenceSalesOrder": clean(r.get("referenceSdDocument")),
            "referenceSalesOrderItem": norm_item(r.get("referenceSdDocumentItem")),
        })
    n = write_batch(session, "UNWIND $rows AS r MERGE (di:DeliveryItem {uid: r.uid}) SET di += r", di_rows, bs)
    print(f"  DeliveryItem: {n}")
    kept["di_rows"] = di_rows

    # ---- BillingDocument (headers + cancellations, deduplicated) ----
    bd_seen: dict[str, dict] = {}
    for r in data["billing_document_headers"] + data["billing_document_cancellations"]:
        bd_id = clean(r.get("billingDocument"))
        if not bd_id or bd_id in bd_seen:
            continue
        bd_seen[bd_id] = {
            "id": bd_id,
            "type": clean(r.get("billingDocumentType")),
            "date": clean(r.get("billingDocumentDate")),
            "creationDate": clean(r.get("creationDate")),
            "totalNetAmount": to_float(r.get("totalNetAmount")),
            "currency": clean(r.get("transactionCurrency")),
            "companyCode": clean(r.get("companyCode")),
            "isCancelled": r.get("billingDocumentIsCancelled", False),
            "cancelledBillingDocument": clean(r.get("cancelledBillingDocument")),
            "accountingDocument": clean(r.get("accountingDocument")),
            "fiscalYear": clean(r.get("fiscalYear")),
            "soldToParty": clean(r.get("soldToParty")),
        }
    bd_rows = list(bd_seen.values())
    n = write_batch(session, "UNWIND $rows AS r MERGE (b:BillingDocument {id: r.id}) SET b += r", bd_rows, bs)
    print(f"  BillingDocument: {n}")
    kept["bd_rows"] = bd_rows

    # ---- BillingDocumentItem ----
    bdi_rows = []
    for r in data["billing_document_items"]:
        bd = clean(r.get("billingDocument"))
        item = norm_item(r.get("billingDocumentItem"))
        if not bd or not item:
            continue
        bdi_rows.append({
            "uid": make_uid(bd, item),
            "billingDocument": bd,
            "item": item,
            "material": clean(r.get("material")),
            "quantity": to_float(r.get("billingQuantity")),
            "quantityUnit": clean(r.get("billingQuantityUnit")),
            "netAmount": to_float(r.get("netAmount")),
            "currency": clean(r.get("transactionCurrency")),
            "referenceDelivery": clean(r.get("referenceSdDocument")),
            "referenceDeliveryItem": norm_item(r.get("referenceSdDocumentItem")),
        })
    n = write_batch(session, "UNWIND $rows AS r MERGE (bi:BillingDocumentItem {uid: r.uid}) SET bi += r", bdi_rows, bs)
    print(f"  BillingDocumentItem: {n}")
    kept["bdi_rows"] = bdi_rows

    # ---- JournalEntry (aggregated to document level) ----
    je_docs: dict[str, dict] = {}
    for r in data["journal_entry_items_accounts_receivable"]:
        doc = clean(r.get("accountingDocument"))
        fy = clean(r.get("fiscalYear"))
        if not doc or not fy:
            continue
        je_id = make_uid(doc, fy)
        if je_id not in je_docs:
            je_docs[je_id] = {
                "id": je_id,
                "accountingDocument": doc,
                "fiscalYear": fy,
                "companyCode": clean(r.get("companyCode")),
                "documentType": clean(r.get("accountingDocumentType")),
                "postingDate": clean(r.get("postingDate")),
                "documentDate": clean(r.get("documentDate")),
                "referenceDocument": clean(r.get("referenceDocument")),
                "customer": clean(r.get("customer")),
                "profitCenter": clean(r.get("profitCenter")),
                "currency": clean(r.get("transactionCurrency")),
                "glAccount": clean(r.get("glAccount")),
                "totalAmount": 0.0,
                "clearingDate": clean(r.get("clearingDate")),
                "clearingDocument": clean(r.get("clearingAccountingDocument")),
                "clearingDocFiscalYear": clean(r.get("clearingDocFiscalYear")),
                "itemCount": 0,
            }
        amt = to_float(r.get("amountInTransactionCurrency"))
        if amt:
            je_docs[je_id]["totalAmount"] += amt
        je_docs[je_id]["itemCount"] += 1

    je_rows = list(je_docs.values())
    for row in je_rows:
        row["totalAmount"] = round(row["totalAmount"], 2)

    n = write_batch(session, "UNWIND $rows AS r MERGE (j:JournalEntry {id: r.id}) SET j += r", je_rows, bs)
    print(f"  JournalEntry: {n}")
    kept["je_rows"] = je_rows

    # ---- ClearingDocument (unique clearing refs from JE + Payments) ----
    cd_map: dict[str, dict] = {}
    for r in data["journal_entry_items_accounts_receivable"] + data["payments_accounts_receivable"]:
        cd = clean(r.get("clearingAccountingDocument"))
        fy = clean(r.get("clearingDocFiscalYear"))
        if not cd or not fy:
            continue
        cd_id = make_uid(cd, fy)
        if cd_id and cd_id not in cd_map:
            cd_map[cd_id] = {
                "id": cd_id,
                "accountingDocument": cd,
                "fiscalYear": fy,
                "clearingDate": clean(r.get("clearingDate")),
                "customer": clean(r.get("customer")),
                "companyCode": clean(r.get("companyCode")),
            }
    cd_rows = list(cd_map.values())
    n = write_batch(session, "UNWIND $rows AS r MERGE (cd:ClearingDocument {id: r.id}) SET cd += r", cd_rows, bs)
    print(f"  ClearingDocument: {n}")
    kept["cd_rows"] = cd_rows

    return kept


# ---------------------------------------------------------------------------
# Relationship loaders
# ---------------------------------------------------------------------------

def load_relationships(session, data: dict, kept: dict, bs: int) -> None:
    soi_rows = kept["soi_rows"]
    di_rows = kept["di_rows"]
    bd_rows = kept["bd_rows"]
    bdi_rows = kept["bdi_rows"]
    je_rows = kept["je_rows"]
    cd_rows = kept["cd_rows"]

    def _w(label: str, cypher: str, rows: list[dict]) -> None:
        n = write_batch(session, cypher, rows, bs)
        print(f"  {label}: {n}")

    # -- Customer -[:PLACED]-> SalesOrder
    rows = []
    for r in data["sales_order_headers"]:
        cid = clean(r.get("soldToParty"))
        sid = clean(r.get("salesOrder"))
        if cid and sid:
            rows.append({"c": cid, "s": sid})
    _w("Customer-[:PLACED]->SalesOrder", """
        UNWIND $rows AS r
        MATCH (c:Customer {id: r.c})
        MATCH (s:SalesOrder {id: r.s})
        MERGE (c)-[:PLACED]->(s)
    """, rows)

    # -- Customer -[:HAS_ADDRESS]-> Address
    rows = []
    for r in data["business_partner_addresses"]:
        bp = clean(r.get("businessPartner"))
        aid = clean(r.get("addressId"))
        if bp and aid:
            rows.append({"c": bp, "a": make_uid(bp, aid)})
    _w("Customer-[:HAS_ADDRESS]->Address", """
        UNWIND $rows AS r
        MATCH (c:Customer {id: r.c})
        MATCH (a:Address {id: r.a})
        MERGE (c)-[:HAS_ADDRESS]->(a)
    """, rows)

    # -- SalesOrder -[:HAS_ITEM]-> SalesOrderItem
    rows = [{"s": r["salesOrder"], "si": r["uid"]} for r in soi_rows]
    _w("SalesOrder-[:HAS_ITEM]->SalesOrderItem", """
        UNWIND $rows AS r
        MATCH (s:SalesOrder {id: r.s})
        MATCH (si:SalesOrderItem {uid: r.si})
        MERGE (s)-[:HAS_ITEM]->(si)
    """, rows)

    # -- SalesOrderItem -[:FOR_PRODUCT]-> Product
    seen: set = set()
    rows = []
    for r in soi_rows:
        mat = r.get("material")
        if mat and (r["uid"], mat) not in seen:
            seen.add((r["uid"], mat))
            rows.append({"si": r["uid"], "p": mat})
    _w("SalesOrderItem-[:FOR_PRODUCT]->Product", """
        UNWIND $rows AS r
        MATCH (si:SalesOrderItem {uid: r.si})
        MATCH (p:Product {id: r.p})
        MERGE (si)-[:FOR_PRODUCT]->(p)
    """, rows)

    # -- SalesOrderItem -[:FROM_PLANT]-> Plant
    seen = set()
    rows = []
    for r in soi_rows:
        pl = r.get("plant")
        if pl and (r["uid"], pl) not in seen:
            seen.add((r["uid"], pl))
            rows.append({"si": r["uid"], "pl": pl})
    _w("SalesOrderItem-[:FROM_PLANT]->Plant", """
        UNWIND $rows AS r
        MATCH (si:SalesOrderItem {uid: r.si})
        MATCH (pl:Plant {id: r.pl})
        MERGE (si)-[:FROM_PLANT]->(pl)
    """, rows)

    # -- SalesOrder -[:DELIVERED_VIA]-> Delivery  (derived from delivery items)
    pairs: set[tuple] = set()
    for r in data["outbound_delivery_items"]:
        so = clean(r.get("referenceSdDocument"))
        dd = clean(r.get("deliveryDocument"))
        if so and dd:
            pairs.add((so, dd))
    rows = [{"s": so, "d": dd} for so, dd in pairs]
    _w("SalesOrder-[:DELIVERED_VIA]->Delivery", """
        UNWIND $rows AS r
        MATCH (s:SalesOrder {id: r.s})
        MATCH (d:Delivery {id: r.d})
        MERGE (s)-[:DELIVERED_VIA]->(d)
    """, rows)

    # -- Delivery -[:HAS_ITEM]-> DeliveryItem
    rows = [{"d": r["deliveryDocument"], "di": r["uid"]} for r in di_rows]
    _w("Delivery-[:HAS_ITEM]->DeliveryItem", """
        UNWIND $rows AS r
        MATCH (d:Delivery {id: r.d})
        MATCH (di:DeliveryItem {uid: r.di})
        MERGE (d)-[:HAS_ITEM]->(di)
    """, rows)

    # -- DeliveryItem -[:FULFILLS]-> SalesOrderItem
    rows = []
    for r in di_rows:
        so = r.get("referenceSalesOrder")
        so_item = r.get("referenceSalesOrderItem")
        if so and so_item:
            soi_uid = make_uid(so, so_item)
            if soi_uid:
                rows.append({"di": r["uid"], "si": soi_uid})
    _w("DeliveryItem-[:FULFILLS]->SalesOrderItem", """
        UNWIND $rows AS r
        MATCH (di:DeliveryItem {uid: r.di})
        MATCH (si:SalesOrderItem {uid: r.si})
        MERGE (di)-[:FULFILLS]->(si)
    """, rows)

    # -- DeliveryItem -[:FROM_PLANT]-> Plant
    seen = set()
    rows = []
    for r in di_rows:
        pl = r.get("plant")
        if pl and (r["uid"], pl) not in seen:
            seen.add((r["uid"], pl))
            rows.append({"di": r["uid"], "pl": pl})
    _w("DeliveryItem-[:FROM_PLANT]->Plant", """
        UNWIND $rows AS r
        MATCH (di:DeliveryItem {uid: r.di})
        MATCH (pl:Plant {id: r.pl})
        MERGE (di)-[:FROM_PLANT]->(pl)
    """, rows)

    # -- Delivery -[:BILLED_IN]-> BillingDocument  (derived from billing items)
    pairs = set()
    for r in data["billing_document_items"]:
        dd = clean(r.get("referenceSdDocument"))
        bd = clean(r.get("billingDocument"))
        if dd and bd:
            pairs.add((dd, bd))
    rows = [{"d": dd, "b": bd} for dd, bd in pairs]
    _w("Delivery-[:BILLED_IN]->BillingDocument", """
        UNWIND $rows AS r
        MATCH (d:Delivery {id: r.d})
        MATCH (b:BillingDocument {id: r.b})
        MERGE (d)-[:BILLED_IN]->(b)
    """, rows)

    # -- BillingDocument -[:HAS_ITEM]-> BillingDocumentItem
    rows = [{"b": r["billingDocument"], "bi": r["uid"]} for r in bdi_rows]
    _w("BillingDocument-[:HAS_ITEM]->BillingDocumentItem", """
        UNWIND $rows AS r
        MATCH (b:BillingDocument {id: r.b})
        MATCH (bi:BillingDocumentItem {uid: r.bi})
        MERGE (b)-[:HAS_ITEM]->(bi)
    """, rows)

    # -- BillingDocumentItem -[:BILLS]-> DeliveryItem
    rows = []
    for r in bdi_rows:
        dd = r.get("referenceDelivery")
        dd_item = r.get("referenceDeliveryItem")
        if dd and dd_item:
            di_uid = make_uid(dd, dd_item)
            if di_uid:
                rows.append({"bi": r["uid"], "di": di_uid})
    _w("BillingDocumentItem-[:BILLS]->DeliveryItem", """
        UNWIND $rows AS r
        MATCH (bi:BillingDocumentItem {uid: r.bi})
        MATCH (di:DeliveryItem {uid: r.di})
        MERGE (bi)-[:BILLS]->(di)
    """, rows)

    # -- BillingDocumentItem -[:FOR_PRODUCT]-> Product
    seen = set()
    rows = []
    for r in bdi_rows:
        mat = r.get("material")
        if mat and (r["uid"], mat) not in seen:
            seen.add((r["uid"], mat))
            rows.append({"bi": r["uid"], "p": mat})
    _w("BillingDocumentItem-[:FOR_PRODUCT]->Product", """
        UNWIND $rows AS r
        MATCH (bi:BillingDocumentItem {uid: r.bi})
        MATCH (p:Product {id: r.p})
        MERGE (bi)-[:FOR_PRODUCT]->(p)
    """, rows)

    # -- BillingDocument -[:BILLED_TO]-> Customer
    seen = set()
    rows = []
    for r in bd_rows:
        cid = r.get("soldToParty")
        if cid and (r["id"], cid) not in seen:
            seen.add((r["id"], cid))
            rows.append({"b": r["id"], "c": cid})
    _w("BillingDocument-[:BILLED_TO]->Customer", """
        UNWIND $rows AS r
        MATCH (b:BillingDocument {id: r.b})
        MATCH (c:Customer {id: r.c})
        MERGE (b)-[:BILLED_TO]->(c)
    """, rows)

    # -- BillingDocument -[:CANCELS]-> BillingDocument
    rows = []
    for r in bd_rows:
        cancelled = r.get("cancelledBillingDocument")
        if cancelled:
            rows.append({"src": r["id"], "dst": cancelled})
    if rows:
        _w("BillingDocument-[:CANCELS]->BillingDocument", """
            UNWIND $rows AS r
            MATCH (src:BillingDocument {id: r.src})
            MATCH (dst:BillingDocument {id: r.dst})
            MERGE (src)-[:CANCELS]->(dst)
        """, rows)
    else:
        print("  BillingDocument-[:CANCELS]->BillingDocument: 0 (no cancellation links in data)")

    # -- BillingDocument -[:RECORDED_AS]-> JournalEntry
    seen = set()
    rows = []
    for r in bd_rows:
        ad = r.get("accountingDocument")
        fy = r.get("fiscalYear")
        if ad and fy:
            je_id = make_uid(ad, fy)
            if je_id and (r["id"], je_id) not in seen:
                seen.add((r["id"], je_id))
                rows.append({"b": r["id"], "j": je_id})
    _w("BillingDocument-[:RECORDED_AS]->JournalEntry", """
        UNWIND $rows AS r
        MATCH (b:BillingDocument {id: r.b})
        MATCH (j:JournalEntry {id: r.j})
        MERGE (b)-[:RECORDED_AS]->(j)
    """, rows)

    # -- JournalEntry -[:FOR_CUSTOMER]-> Customer
    seen = set()
    rows = []
    for r in je_rows:
        cid = r.get("customer")
        if cid and (r["id"], cid) not in seen:
            seen.add((r["id"], cid))
            rows.append({"j": r["id"], "c": cid})
    _w("JournalEntry-[:FOR_CUSTOMER]->Customer", """
        UNWIND $rows AS r
        MATCH (j:JournalEntry {id: r.j})
        MATCH (c:Customer {id: r.c})
        MERGE (j)-[:FOR_CUSTOMER]->(c)
    """, rows)

    # -- JournalEntry -[:CLEARED_BY]-> ClearingDocument
    seen = set()
    rows = []
    for r in je_rows:
        cd_doc = r.get("clearingDocument")
        cd_fy = r.get("clearingDocFiscalYear")
        if cd_doc and cd_fy:
            cd_id = make_uid(cd_doc, cd_fy)
            if cd_id and (r["id"], cd_id) not in seen:
                seen.add((r["id"], cd_id))
                rows.append({"j": r["id"], "cd": cd_id})
    _w("JournalEntry-[:CLEARED_BY]->ClearingDocument", """
        UNWIND $rows AS r
        MATCH (j:JournalEntry {id: r.j})
        MATCH (cd:ClearingDocument {id: r.cd})
        MERGE (j)-[:CLEARED_BY]->(cd)
    """, rows)

    # -- ClearingDocument -[:FOR_CUSTOMER]-> Customer
    seen = set()
    rows = []
    for r in cd_rows:
        cid = r.get("customer")
        if cid and (r["id"], cid) not in seen:
            seen.add((r["id"], cid))
            rows.append({"cd": r["id"], "c": cid})
    _w("ClearingDocument-[:FOR_CUSTOMER]->Customer", """
        UNWIND $rows AS r
        MATCH (cd:ClearingDocument {id: r.cd})
        MATCH (c:Customer {id: r.c})
        MERGE (cd)-[:FOR_CUSTOMER]->(c)
    """, rows)

    # -- Product -[:AVAILABLE_AT]-> Plant  (from product_plants)
    seen = set()
    rows = []
    for r in data["product_plants"]:
        pid = clean(r.get("product"))
        pl = clean(r.get("plant"))
        if pid and pl and (pid, pl) not in seen:
            seen.add((pid, pl))
            rows.append({
                "p": pid, "pl": pl,
                "profitCenter": clean(r.get("profitCenter")),
                "mrpType": clean(r.get("mrpType")),
            })
    _w("Product-[:AVAILABLE_AT]->Plant", """
        UNWIND $rows AS r
        MATCH (p:Product {id: r.p})
        MATCH (pl:Plant {id: r.pl})
        MERGE (p)-[rel:AVAILABLE_AT]->(pl)
        SET rel.profitCenter = r.profitCenter, rel.mrpType = r.mrpType
    """, rows)

    # -- Product -[:STORED_AT]-> Plant  (from product_storage_locations)
    seen = set()
    rows = []
    for r in data["product_storage_locations"]:
        pid = clean(r.get("product"))
        pl = clean(r.get("plant"))
        sl = clean(r.get("storageLocation"))
        if pid and pl:
            key = (pid, pl, sl)
            if key not in seen:
                seen.add(key)
                rows.append({"p": pid, "pl": pl, "sl": sl})
    _w("Product-[:STORED_AT]->Plant", """
        UNWIND $rows AS r
        MATCH (p:Product {id: r.p})
        MATCH (pl:Plant {id: r.pl})
        MERGE (p)-[rel:STORED_AT {storageLocation: coalesce(r.sl, '')}]->(pl)
    """, rows)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify(session) -> None:
    print("\nNode counts:")
    for label, _ in CONSTRAINTS:
        result = session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()
        print(f"  {label}: {result['c'] if result else 0}")

    rel_types = [
        "PLACED", "HAS_ADDRESS", "HAS_ITEM", "DELIVERED_VIA", "FULFILLS",
        "BILLED_IN", "BILLS", "FOR_PRODUCT", "FROM_PLANT", "BILLED_TO",
        "CANCELS", "RECORDED_AS", "FOR_CUSTOMER", "CLEARED_BY",
        "AVAILABLE_AT", "STORED_AT",
    ]
    print("Relationship counts:")
    for rt in rel_types:
        result = session.run(f"MATCH ()-[r:{rt}]->() RETURN count(r) AS c").single()
        print(f"  {rt}: {result['c'] if result else 0}")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=500, help="UNWIND batch size")
    parser.add_argument("--no-wipe", action="store_true", help="Skip wiping the existing graph")
    parser.add_argument("--env-file", type=Path, default=None, help="Path to .env file")
    args = parser.parse_args()

    if args.env_file:
        load_dotenv(args.env_file)
    else:
        load_dotenv()

    required = ["NEO4J_BOLT_URL", "NEO4J_USER", "NEO4J_PASSWORD"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    neo4j_db = os.environ.get("NEO4J_DATABASE", "neo4j")

    driver = GraphDatabase.driver(
        os.environ["NEO4J_BOLT_URL"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
    )

    try:
        with driver.session(database=neo4j_db) as session:
            if not args.no_wipe:
                print("Wiping existing graph...")
                wipe_graph(session)

            print("Creating constraints...")
            create_constraints(session)

            print("\n=== Reading JSONL files ===")
            data = read_all_data()

            print("\n=== Creating nodes ===")
            kept = load_nodes(session, data, args.batch_size)

            print("\n=== Creating relationships ===")
            load_relationships(session, data, kept, args.batch_size)

            print("\n=== Verification ===")
            verify(session)

            print("\nGraph loaded successfully.")
    finally:
        driver.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
