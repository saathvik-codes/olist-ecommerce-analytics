"""
Re-lay the four report pages on one grid and write a NEW .pbix (the source file is never changed).

    python restructure_report.py obsli.pbix Olist_Analytics_Dashboard.pbix

Works on the PBIR report definition stored inside the .pbix (Report/definition/...). It only touches
layout and labelling: positions, page names, visual titles, the header text box and slicer style.
The data model, measures and every visual's fields stay as they are, apart from the fixes listed in FIXES.
"""
import copy
import json
import sys
import zipfile

SRC, DST = sys.argv[1], sys.argv[2]
PAGES = "Report/definition/pages/"

# ---- grid (1920 x 1080 canvas) ---------------------------------------------------------------------
W, MARGIN, GAP = 1920, 24, 16
INNER = W - 2 * MARGIN                      # 1872
HEADER_Y, HEADER_H = 16, 92
KPI_Y, KPI_H = 124, 120
ROW1_Y, ROW1_H = 260, 390
ROW2_Y, ROW2_H = 666, 390                   # ends at 1056, leaving a 24px bottom margin
HALF = (INNER - GAP) // 2                   # 928
LEFT, RIGHT = MARGIN, MARGIN + HALF + GAP
TITLE_W, SLICER_W = 820, 300


def lit(text: str) -> dict:
    return {"expr": {"Literal": {"Value": "'" + text.replace("'", "''") + "'"}}}


TRUE, FALSE = {"expr": {"Literal": {"Value": "true"}}}, {"expr": {"Literal": {"Value": "false"}}}


def slot(x, y, w, h):
    return {"x": x, "y": y, "width": w, "height": h}


def kpi_slots(n):
    w = (INNER - GAP * (n - 1)) / n
    return [slot(round(MARGIN + i * (w + GAP), 2), KPI_Y, round(w, 2), KPI_H) for i in range(n)]


def slicer_slot(i_from_right):
    return slot(W - MARGIN - SLICER_W - i_from_right * (SLICER_W + GAP), HEADER_Y, SLICER_W, HEADER_H)


TITLE_SLOT = slot(MARGIN, HEADER_Y, TITLE_W, HEADER_H)
R1L, R1R = slot(LEFT, ROW1_Y, HALF, ROW1_H), slot(RIGHT, ROW1_Y, HALF, ROW1_H)
R2L, R2R = slot(LEFT, ROW2_Y, HALF, ROW2_H), slot(RIGHT, ROW2_Y, HALF, ROW2_H)
R2FULL = slot(MARGIN, ROW2_Y, INNER, ROW2_H)

# ---- what goes where: visuals are identified by type + the first field they show -------------------
# (key, slot, title) ; key = (visualType, "table[field]" of the first projection) ; title None = leave as is
P1, P2, P3, P4 = (kpi_slots(n) for n in (6, 4, 6, 4))
PLAN = {
    "Page 1": {
        "name": "Executive Overview",
        "header": ("Olist Marketplace: Executive Overview", "Revenue, orders, customers and service quality on delivered orders"),
        "items": [
            (("slicer", "dim_date[year]"), slicer_slot(1), "Year"),
            (("slicer", "dim_geography[region]"), slicer_slot(0), "Region"),
            (("cardVisual", "fact_orders[Total Revenue]"), P1[0], None),
            (("cardVisual", "fact_orders[Total Orders]"), P1[1], None),
            (("cardVisual", "fact_orders[AOV]"), P1[2], None),
            (("cardVisual", "fact_orders[Active Customers]"), P1[3], None),
            (("cardVisual", "fact_orders[Late Delivery %]"), P1[4], None),
            (("cardVisual", "fact_orders[Avg Review Score]"), P1[5], None),
            (("lineChart", "dim_date[year_month]"), R1L, "Monthly revenue and 3-month rolling revenue"),
            (("clusteredColumnChart", "dim_date[year_month]"), R1R, "Month-over-month revenue growth"),
            (("clusteredBarChart", "dim_geography[state]"), R2L, "Revenue by customer state"),
            (("clusteredBarChart", "fact_orders[payment_type]"), R2R, "Delivered orders by payment method"),
        ],
    },
    "Page 2": {
        "name": "Customers & Retention",
        "header": ("Customers & Retention", "Who buys, how often they return, and how each monthly cohort retains"),
        "items": [
            (("cardVisual", "fact_orders[Active Customers]"), P2[0], None),
            (("cardVisual", "fact_orders[Repeat Customer Rate]"), P2[1], None),
            (("cardVisual", "fact_orders[Revenue per Customer]"), P2[2], None),
            (("cardVisual", "fact_orders[Avg Basket Size]"), P2[3], None),
            (("lineChart", "dim_date[year_month]"), R1L, "New and returning customers by month"),
            (("clusteredBarChart", "dim_customer[rfm_segment]"), R1R, "Customers by RFM segment"),
            (("pivotTable", "dim_customer[cohort_month]"), R2FULL, "Cohort retention: share of each cohort active N months after first order"),
        ],
    },
    "Page 3": {
        "name": "Delivery & Reviews",
        "header": ("Delivery & Customer Satisfaction", "How late deliveries move review scores, by time and by state"),
        "items": [
            (("slicer", "dim_date[year]"), slicer_slot(1), "Year"),
            (("slicer", "dim_geography[region]"), slicer_slot(0), "Region"),
            (("cardVisual", "fact_orders[Late Delivery %]"), P3[0], None),
            (("cardVisual", "fact_orders[Avg Delivery Days]"), P3[1], None),
            (("cardVisual", "fact_orders[Avg Review Score]"), P3[2], None),
            (("cardVisual", "fact_orders[Low Review %]"), P3[3], None),
            (("cardVisual", "fact_orders[Avg Review - On Time]"), P3[4], None),
            (("cardVisual", "fact_orders[Avg Review - Late]"), P3[5], None),
            (("clusteredColumnChart", "fact_orders[delivery_band]"), R1L, "Average review score by delivery time band"),
            (("clusteredBarChart", "dim_geography[state]"), R1R, "Late delivery rate by customer state"),
            (("lineChart", "dim_date[year_month]"), R2L, "Late delivery rate by month"),
            (("hundredPercentStackedColumnChart", "fact_orders[delivery_status]"), R2R, "Review score mix: on-time vs late orders"),
        ],
    },
    "Page 4": {
        "name": "Products & Sellers",
        "header": ("Products & Sellers", "Which categories and sellers drive revenue, and how concentrated it is"),
        "items": [
            (("slicer", "dim_product[category]"), slicer_slot(1), "Category"),
            (("slicer", "dim_seller[seller_state]"), slicer_slot(0), "Seller state"),
            (("cardVisual", "fact_orders[Total Revenue]"), P4[0], None),
            (("cardVisual", "fact_orders[Active Sellers]"), P4[1], None),
            (("cardVisual", "fact_orders[Items Sold]"), P4[2], None),
            (("cardVisual", "fact_orders[Freight % of Revenue]"), P4[3], None),
            (("clusteredBarChart", "dim_product[category]"), R1L, "Revenue by product category"),
            (("tableEx", "dim_product[category]"), R1R, "Category ranking and Pareto share of revenue"),
            (("tableEx", "dim_seller[seller_id]"), R2FULL, "Seller performance"),
        ],
    },
}
# Category-only measures that are meaningless per seller (share is always 100%, Pareto is blank)
SELLER_TABLE_DROP = {"Category Revenue Share %", "Pareto Cumulative %"}


def load(z, name):
    return json.loads(z.read(name).decode("utf-8-sig"))


def dump(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def first_field(visual: dict) -> str:
    state = visual.get("query", {}).get("queryState") or {}
    for role in ("Category", "Rows", "Values", "Data"):
        for p in state.get(role, {}).get("projections", []):
            f = p["field"]
            node = f.get("Measure") or f.get("Column")
            return f"{node['Expression']['SourceRef']['Entity']}[{node['Property']}]"
    return ""


def header_textbox(template: dict, name: str, title: str, subtitle: str) -> dict:
    v = copy.deepcopy(template)
    v["name"] = name
    v["visual"]["objects"] = {"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": title, "textStyle": {"fontWeight": "bold", "fontSize": "20pt", "color": "#1F3A5F"}}]},
        {"textRuns": [{"value": subtitle, "textStyle": {"fontSize": "11pt", "color": "#52514E"}}]},
    ]}}]}
    return v


def main():
    zin = zipfile.ZipFile(SRC)
    out: dict[str, bytes] = {}          # changed or new parts
    removed: set[str] = {"SecurityBindings"}   # the report was edited outside Power BI, so the old binding no longer applies
    fixes: list[str] = []
    order = load(zin, PAGES + "pages.json")["pageOrder"]
    template_box = None
    for pid in order:                   # any existing text box is the template for page headers
        for n in zin.namelist():
            if n.startswith(f"{PAGES}{pid}/visuals/") and load(zin, n)["visual"].get("visualType") == "textbox":
                template_box = template_box or load(zin, n)
    if template_box is None:
        sys.exit("no text box found to use as a header template")

    for pid in order:
        page_file = f"{PAGES}{pid}/page.json"
        page = load(zin, page_file)
        plan = PLAN.get(page["displayName"])
        if not plan:
            sys.exit(f"unexpected page name {page['displayName']!r}: this script expects the original Page 1..4")
        page["displayName"] = plan["name"]
        out[page_file] = dump(page)

        files = [n for n in zin.namelist() if n.startswith(f"{PAGES}{pid}/visuals/")]
        visuals = {n: load(zin, n) for n in files}
        wanted = {key: (pos, title) for key, pos, title in plan["items"]}
        placed, header_done, z = set(), False, 0
        for n, v in visuals.items():
            vis = v["visual"]
            vtype = vis.get("visualType")
            if vtype == "textbox":
                if header_done:         # one header per page; extra (empty) text boxes are dropped
                    removed.add(n)
                    continue
                v = header_textbox(v, v["name"], *plan["header"])
                pos, title, header_done = TITLE_SLOT, None, True
            else:
                key = (vtype, first_field(vis))
                if key not in wanted or key in placed:
                    sys.exit(f"{plan['name']}: no slot planned for {key}")
                placed.add(key)
                pos, title = wanted[key]
            v["position"] = {**pos, "z": z * 1000, "tabOrder": z * 1000}
            z += 1
            vis = v["visual"]
            if title:
                vis.setdefault("visualContainerObjects", {})["title"] = [{"properties": {"show": TRUE, "text": lit(title)}}]
            if vtype == "slicer":
                objs = vis.setdefault("objects", {})
                for g in objs.get("general", []):       # a saved selection would silently filter the whole page
                    if g.get("properties", {}).pop("filter", None) is not None:
                        fixes.append(f"{plan['name']}: cleared the saved selection on the {title} slicer")
                if title != "Year":
                    objs["data"] = [{"properties": {"mode": lit("Dropdown")}}]
                objs["header"] = [{"properties": {"show": FALSE}}]   # the container title already names it
            if key_is(vtype, vis, "hundredPercentStackedColumnChart"):
                for p in vis["query"]["queryState"].get("Series", {}).get("projections", []):
                    col = p["field"].get("Column")
                    if col and col["Expression"]["SourceRef"]["Entity"] == "fact_order_items" and col["Property"] == "review_score":
                        col["Expression"]["SourceRef"]["Entity"] = "fact_orders"
                        p["queryRef"] = "fact_orders.review_score"
                        fixes.append("Delivery & Reviews: review score mix now reads fact_orders[review_score] "
                                     "(it was fact_order_items[review_score], which does not filter the order count)")
            if vtype != "textbox" and vtype != "slicer" and first_field(vis) == "dim_date[year_month]":
                # time axes read left to right in calendar order, not by the size of the measure
                vis["query"]["sortDefinition"] = {"sort": [{"field": {"Column": {
                    "Expression": {"SourceRef": {"Entity": "dim_date"}}, "Property": "year_month"}},
                    "direction": "Ascending"}]}
                fixes.append("month charts now sort by month instead of by value")
            if vtype == "tableEx" and first_field(vis) == "dim_seller[seller_id]":
                projs = vis["query"]["queryState"]["Values"]["projections"]
                keep = [p for p in projs if (p["field"].get("Measure") or {}).get("Property") not in SELLER_TABLE_DROP]
                if len(keep) != len(projs):
                    vis["query"]["queryState"]["Values"]["projections"] = keep
                    fixes.append("Products & Sellers: removed the two category-only measures from the seller table")
            out[n] = dump(v)
        missing = set(wanted) - placed
        if missing:
            sys.exit(f"{plan['name']}: planned visuals not found: {missing}")
        if not header_done:
            name = (pid[:10] + "hdr0000000")[:20]
            out[f"{PAGES}{pid}/visuals/{name}/visual.json"] = dump({
                **header_textbox(template_box, name, *plan["header"]),
                "position": {**TITLE_SLOT, "z": z * 1000, "tabOrder": z * 1000}})

    ct = zin.read("[Content_Types].xml").decode("utf-8-sig")
    ct = ct.replace('<Override PartName="/SecurityBindings" ContentType="" />', "")
    out["[Content_Types].xml"] = "﻿".encode("utf-8")[0:0] + b"\xef\xbb\xbf" + ct.encode("utf-8")

    with zipfile.ZipFile(DST, "w") as zout:
        done = set()
        for info in zin.infolist():
            if info.filename in removed:
                continue
            data = out.get(info.filename, None)
            zout.writestr(info.filename, zin.read(info.filename) if data is None else data,
                          compress_type=info.compress_type)
            done.add(info.filename)
        for name, data in out.items():
            if name not in done:
                zout.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
    print("written:", DST)
    for f in dict.fromkeys(fixes):
        print("fix:", f)


def key_is(vtype, vis, wanted_type):
    return vtype == wanted_type and "query" in vis


if __name__ == "__main__":
    main()
