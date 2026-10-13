"""
Rebuild the "Seller performance" table on the Products & Sellers page of a .pbix, in place.

    python fix_seller_table.py Olist_Analytics_Dashboard_v2.pbix

Only that one visual changes: it gets six columns that fill the full width, readable headers, and is
sorted by revenue (largest first). A backup of the file is written next to it first.
"""
import json
import shutil
import sys
import zipfile
from pathlib import Path

SRC = Path(sys.argv[1])
PAGES = "Report/definition/pages/"

# (table, field, is_measure, header shown, width in px) - widths add up to the usable width of the visual
COLUMNS = [
    ("dim_seller", "seller_id", False, "Seller ID", 470),
    ("dim_seller", "seller_state", False, "State", 170),
    ("fact_orders", "Total Revenue", True, "Revenue", 280),
    ("fact_orders", "Total Orders", True, "Orders", 250),
    ("fact_orders", "Late Delivery % (Product View)", True, "Late delivery %", 320),
    ("fact_orders", "Avg Review (Product View)", True, "Avg review score", 320),
]


def expr(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def field(table: str, name: str, is_measure: bool) -> dict:
    return {"Measure" if is_measure else "Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def main():
    zin = zipfile.ZipFile(SRC)
    target = None
    for n in zin.namelist():
        if n.startswith(PAGES) and n.endswith("visual.json"):
            v = json.loads(zin.read(n).decode("utf-8-sig"))
            projs = v["visual"].get("query", {}).get("queryState", {}).get("Values", {}).get("projections", [])
            if v["visual"].get("visualType") == "tableEx" and projs and projs[0]["queryRef"] == "dim_seller.seller_id":
                target = (n, v)
    if not target:
        sys.exit("seller table not found")
    name, v = target
    vis = v["visual"]
    vis["query"]["queryState"]["Values"]["projections"] = [
        {"field": field(t, f, m), "queryRef": f"{t}.{f}", "nativeQueryRef": f, "displayName": shown}
        for t, f, m, shown, _ in COLUMNS]
    vis["query"]["sortDefinition"] = {"sort": [{"field": field("fact_orders", "Total Revenue", True), "direction": "Descending"}]}
    objs = vis.setdefault("objects", {})
    objs["columnWidth"] = [{"properties": {"value": expr(f"{w}D")}, "selector": {"metadata": f"{t}.{f}"}}
                           for t, f, _, _, w in COLUMNS]
    headers = objs.setdefault("columnHeaders", [{"properties": {}}])
    headers[0].setdefault("properties", {})["autoSizeColumnWidth"] = expr("false")
    vis.setdefault("visualContainerObjects", {})["title"] = [{"properties": {
        "show": expr("true"), "text": expr("'Seller performance: revenue, orders, late deliveries and reviews (largest sellers first)'")}}]

    backup = SRC.with_name(SRC.stem + "_backup" + SRC.suffix)
    shutil.copy2(SRC, backup)
    tmp = SRC.with_suffix(".tmp")
    new = json.dumps(v, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with zipfile.ZipFile(tmp, "w") as zout:
        for info in zin.infolist():
            if info.filename == "SecurityBindings":      # edited outside Power BI
                continue
            data = new if info.filename == name else zin.read(info.filename)
            if info.filename == "[Content_Types].xml":
                data = data.replace(b'<Override PartName="/SecurityBindings" ContentType="" />', b"")
            zout.writestr(info.filename, data, compress_type=info.compress_type)
    zin.close()
    tmp.replace(SRC)
    print("updated:", SRC, "| backup:", backup)


if __name__ == "__main__":
    main()
