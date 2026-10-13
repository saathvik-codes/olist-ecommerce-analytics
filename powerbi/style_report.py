"""
Apply the corporate theme and structural polish to the report and write a NEW .pbix.

    python style_report.py Olist_Analytics_Dashboard.pbix Olist_Analytics_Dashboard_v2.pbix

Run it on the file you are currently working in: it keeps every field, filter and conditional-format rule
you added. It changes only presentation:
  * replaces the embedded theme with theme.json (colours, fonts, card / table / axis styling)
  * turns each page's title box into a full-width navy header band, with the slicers sitting on it
  * re-lays the Customers page so the cohort heatmap is tall enough to show every cohort
  * widens the heatmap columns and gives it a stronger colour scale
"""
import json
import sys
import zipfile
from pathlib import Path

SRC, DST = sys.argv[1], sys.argv[2]
HERE = Path(__file__).resolve().parent
PAGES = "Report/definition/pages/"

NAVY, WHITE, SOFT = "#0F2747", "#FFFFFF", "#B8C7DC"
W, MARGIN, GAP = 1920, 24, 16
BAND = {"x": MARGIN, "y": 12, "width": W - 2 * MARGIN, "height": 104}
SLICER_Y, SLICER_H, SLICER_W = 22, 84, 290
ROW1_Y, ROW_H, ROW2_Y, BOTTOM = 260, 390, 666, 1056
SUBTITLES = {
    "Executive Overview": "Revenue, orders, customers and service quality on delivered orders",
    "Customers & Retention": "Who buys, how often they return, and how each monthly cohort retains",
    "Delivery & Reviews": "How late deliveries move review scores, by time and by state",
    "Products & Sellers": "Which categories and sellers drive revenue, and how concentrated it is",
}
TITLES = {"Executive Overview": "Olist Marketplace: Executive Overview", "Delivery & Reviews": "Delivery & Customer Satisfaction"}


def expr(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def colour(hex_code: str) -> dict:
    return {"solid": {"color": expr(f"'{hex_code}'")}}


def load(z, name):
    return json.loads(z.read(name).decode("utf-8-sig"))


def dump(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def first_field(vis: dict) -> str:
    state = vis.get("query", {}).get("queryState") or {}
    for role in ("Category", "Rows", "Values", "Data"):
        for p in state.get(role, {}).get("projections", []):
            node = p["field"].get("Measure") or p["field"].get("Column")
            return f"{node['Expression']['SourceRef']['Entity']}[{node['Property']}]"
    return ""


def style_header(v: dict, page_name: str) -> None:
    v["position"].update(BAND, z=0, tabOrder=0)
    vis = v["visual"]
    vis["objects"] = {"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": TITLES.get(page_name, page_name),
                       "textStyle": {"fontWeight": "bold", "fontSize": "22pt", "color": WHITE}}]},
        {"textRuns": [{"value": SUBTITLES.get(page_name, ""), "textStyle": {"fontSize": "11pt", "color": SOFT}}]},
    ]}}]}
    vis["visualContainerObjects"] = {
        "background": [{"properties": {"show": expr("true"), "color": colour(NAVY), "transparency": expr("0D")}}],
        "border": [{"properties": {"show": expr("false")}}],
        "dropShadow": [{"properties": {"show": expr("false")}}],
        "padding": [{"properties": {"left": expr("22D"), "top": expr("14D"), "right": expr("12D"), "bottom": expr("8D")}}],
    }


def use_month_start_axis(vis: dict) -> None:
    """Put the real date column dim_date[month_start] on the time axis, so months run in calendar order
    whatever text format year_month ended up in."""
    for p in vis["query"]["queryState"]["Category"]["projections"]:
        col = p["field"].get("Column")
        if col and col["Property"] == "year_month":
            col["Property"] = "month_start"
            p["queryRef"], p["nativeQueryRef"] = "dim_date.month_start", "month_start"
    vis["query"]["sortDefinition"] = {"sort": [{"field": {"Column": {
        "Expression": {"SourceRef": {"Entity": "dim_date"}}, "Property": "month_start"}}, "direction": "Ascending"}]}


def style_cohort_matrix(v: dict) -> None:
    v["position"].update(x=796, y=ROW1_Y, width=W - MARGIN - 796, height=BOTTOM - ROW1_Y)
    objs = v["visual"].setdefault("objects", {})
    measure = {"Measure": {"Expression": {"SourceRef": {"Entity": "fact_orders"}}, "Property": "Cohort Retention %"}}
    # Fixed bounds (0%, 0.3%, 0.6%): one tiny early cohort with a huge rate would otherwise wash every cell out
    stop = lambda c, at: {"color": {"Literal": {"Value": f"'{c}'"}}, "value": {"Literal": {"Value": at}}}
    objs["values"] = [
        {"properties": {"fontSize": expr("11D")}},
        {"properties": {"backColor": {"solid": {"color": {"expr": {"FillRule": {"Input": measure, "FillRule": {
            "linearGradient3": {"min": stop("#F0FDFA", "0D"), "mid": stop("#7DD3C8", "0.003D"), "max": stop("#0E9F8E", "0.006D"),
                                "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}}}}}}}}}},
         "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": "fact_orders.Cohort Retention %"}},
    ]
    objs["columnWidth"] = [{"properties": {"value": expr("76D")}, "selector": {"metadata": "fact_orders.Cohort Retention %"}}]
    objs["columnHeaders"] = [{"properties": {"autoSizeColumnWidth": expr("false"), "alignment": expr("'Center'")}}]
    objs["grid"] = [{"properties": {"rowPadding": expr("9D"), "gridVertical": expr("false")}}]
    v["visual"].setdefault("visualContainerObjects", {})["title"] = [{"properties": {
        "show": expr("true"), "text": expr("'Cohort retention heatmap: % of each monthly cohort ordering again, by months since first order'")}}]


def main():
    zin = zipfile.ZipFile(SRC)
    out: dict[str, bytes] = {}
    theme_parts = [n for n in zin.namelist() if "/RegisteredResources/" in n and n.endswith(".json")]
    if len(theme_parts) != 1:
        sys.exit(f"expected one custom theme inside the report, found {theme_parts}")
    out[theme_parts[0]] = (HERE / "theme.json").read_bytes()

    pages_meta = load(zin, PAGES + "pages.json")
    for pid in pages_meta["pageOrder"]:
        page_name = load(zin, f"{PAGES}{pid}/page.json")["displayName"]
        if page_name not in SUBTITLES:
            sys.exit(f"unexpected page {page_name!r}: run restructure_report.py first")
        slicers = []
        for n in [n for n in zin.namelist() if n.startswith(f"{PAGES}{pid}/visuals/")]:
            v = load(zin, n)
            vis = v["visual"]
            vtype = vis.get("visualType")
            if vtype == "textbox":
                style_header(v, page_name)
            elif vtype == "slicer":
                slicers.append((v["position"]["x"], n, v))
                continue
            elif vtype == "pivotTable":
                style_cohort_matrix(v)
            elif page_name == "Customers & Retention" and vtype == "lineChart":
                v["position"].update(x=MARGIN, y=ROW1_Y, width=756, height=ROW_H)
            elif page_name == "Customers & Retention" and vtype == "clusteredBarChart":
                v["position"].update(x=MARGIN, y=ROW2_Y, width=756, height=ROW_H)
            if first_field(vis) == "dim_date[year_month]":
                use_month_start_axis(vis)
            if v["position"].get("z", 0) == 0 and vtype != "textbox":
                v["position"]["z"] = v["position"]["tabOrder"] = 500      # stay above the header band
            out[n] = dump(v)
        # slicers sit on the right end of the band, in their current left-to-right order
        for i, (_, n, v) in enumerate(sorted(slicers, key=lambda s: -s[0])):
            v["position"].update(x=W - MARGIN - 14 - SLICER_W - i * (SLICER_W + 12), y=SLICER_Y,
                                 width=SLICER_W, height=SLICER_H, z=20000 + i, tabOrder=20000 + i)
            out[n] = dump(v)

    if len(sys.argv) > 3:                       # optional: page to show when the file opens
        want = sys.argv[3]
        for pid in pages_meta["pageOrder"]:
            if load(zin, f"{PAGES}{pid}/page.json")["displayName"] == want:
                pages_meta["activePageName"] = pid
        out[PAGES + "pages.json"] = dump(pages_meta)

    removed = {"SecurityBindings"}              # edited outside Power BI, so the old binding no longer applies
    ct = zin.read("[Content_Types].xml").decode("utf-8-sig")
    out["[Content_Types].xml"] = b"\xef\xbb\xbf" + ct.replace(
        '<Override PartName="/SecurityBindings" ContentType="" />', "").encode("utf-8")
    with zipfile.ZipFile(DST, "w") as zout:
        for info in zin.infolist():
            if info.filename not in removed:
                zout.writestr(info.filename, out.get(info.filename) or zin.read(info.filename),
                              compress_type=info.compress_type)
    print("written:", DST)


if __name__ == "__main__":
    main()
