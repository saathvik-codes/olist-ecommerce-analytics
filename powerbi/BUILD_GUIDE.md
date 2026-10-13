# Power BI build guide - Olist E-Commerce Analytics

You build this report yourself so that you can defend every relationship, measure and
visual in an interview. Everything hard (clean data, star schema, DAX, expected values)
is already prepared. Budget about **60-75 minutes**.

| Step | What | Time |
|---|---|---:|
| 1 | Import the 7 CSVs and fix column types | 10 min |
| 2 | Build the relationships | 8 min |
| 3 | Date table, sort orders, hide keys | 5 min |
| 4 | Apply the theme | 1 min |
| 5 | Add the measures and set formats | 10 min |
| 6 | Validate against `EXPECTED_VALUES.md` | 5 min |
| 7 | Build the 4 pages | 30-35 min |

Files in this folder:

* `data/*.csv` - the star schema (5 dimensions, 2 facts), exported by `python run_all.py`
* `measures.dax` - 38 measures with one-line explanations
* `EXPECTED_VALUES.md` - what each measure must show, computed independently in SQL
* `theme.json` - colours and fonts

Honest status: the data, the DAX logic and the expected values were produced and
cross-checked in SQL, but **nothing in this folder has been opened in Power BI by the
person who prepared it**. Step 6 is therefore not optional. If a measure does not match,
the cause is almost always a column type (step 1) or a relationship (step 2).

---

## Step 1 - Import the data

1. Open Power BI Desktop. **File > Options and settings > Options > Current File > Data Load**:
   untick **Auto date/time**. (We use our own date table; the automatic one bloats the model.)
2. **Home > Get data > Text/CSV**. Pick `data/dim_date.csv`, click **Transform Data**
   (not Load) so Power Query opens.
3. In Power Query: **Home > New Source > Text/CSV** and add the other six files:
   `dim_customer`, `dim_geography`, `dim_product`, `dim_seller`, `fact_orders`, `fact_order_items`.
4. Check the row counts (bottom-left of Power Query after scrolling, or later in Table view):

   | Table | Rows |
   |---|---:|
   | dim_date | 1,096 |
   | dim_customer | 96,096 |
   | dim_geography | 19,179 |
   | dim_product | 32,951 |
   | dim_seller | 3,095 |
   | fact_orders | 99,441 |
   | fact_order_items | 112,650 |

5. Fix the column types below (click the type icon in the column header). Power BI guesses
   most types correctly; **these are the ones it gets wrong**:

   | Table | Column | Set type to | Why |
   |---|---|---|---|
   | dim_date | `year_month` | Text | "2017-01" is a label, not a date |
   | dim_date | `date`, `month_start` | Date | used for the relationship and time intelligence |
   | dim_customer | `cohort_month` | Text | label for the cohort matrix |
   | dim_customer | `first_order_date`, `last_order_date` | Date | |
   | dim_geography | `zip_code_prefix` | Text | keeps leading zeros (e.g. 01037) |
   | dim_seller | `seller_zip_code_prefix` | Text | keeps leading zeros |
   | fact_orders | `purchase_date` | Date | relationship to dim_date |
   | fact_order_items | `purchase_date` | Date | relationship to dim_date |
   | fact_order_items | `price`, `freight_value` | Decimal number | |
   | fact_orders | `items_value`, `freight_value`, `order_value`, `payment_value` | Decimal number | |

   If Power Query added a "Changed Type" step that turned `year_month` or `cohort_month`
   into a date, just change it back to Text and choose **Replace current**.
   All flag columns (`is_delivered`, `is_late`, `has_delivery_date`, `is_low_review`,
   `is_analysis_window`, `is_repeat_customer`) must be **Whole number**.
6. **Home > Close & Apply**.

## Step 2 - Relationships (Model view)

Delete any relationship Power BI auto-created, then create exactly these eight
(drag the dimension column onto the fact column). All are **one-to-many (1:*)**,
**single** cross-filter direction (dimension filters fact), **active**.

| # | From (one side) | To (many side) |
|---|---|---|
| 1 | dim_date[date] | fact_orders[purchase_date] |
| 2 | dim_date[date] | fact_order_items[purchase_date] |
| 3 | dim_customer[customer_key] | fact_orders[customer_key] |
| 4 | dim_customer[customer_key] | fact_order_items[customer_key] |
| 5 | dim_geography[geography_key] | fact_orders[geography_key] |
| 6 | dim_geography[geography_key] | fact_order_items[geography_key] |
| 7 | dim_product[product_key] | fact_order_items[product_key] |
| 8 | dim_seller[seller_key] | fact_order_items[seller_key] |

```
            dim_date        dim_customer      dim_geography
               | \             /   \            /   |
               |  \           /     \          /    |
               |   +---- fact_orders -+-------+     |
               |                                    |
               +--------- fact_order_items ---------+
                            /         \
                     dim_product     dim_seller
```

Rules to remember (interviewers ask):

* **Do not relate fact_orders to fact_order_items.** Two facts share dimensions; they are
  never joined to each other. That is what makes it a star (strictly, a "galaxy") schema.
* dim_product and dim_seller filter only fact_order_items, because product and seller
  exist at line-item grain, not order grain. That is why delivery and review measures have
  a separate "(Product View)" version.
* Never set a relationship to "Both" here: it creates ambiguous filter paths between the
  two facts.
* dim_geography is the **customer's** location. Seller location is on dim_seller
  (`seller_state`, `seller_region`).

## Step 3 - Date table, sorting, tidy-up

1. Table view > select **dim_date** > **Table tools > Mark as date table** > date column = `date`.
2. Select `dim_date[month_name]` > **Column tools > Sort by column** > `month`.
   Select `dim_date[day_name]` > Sort by column > `day_of_week`.
3. Hide the key columns from report view (right-click > Hide): every `*_key` column in the
   fact tables, `purchase_date_key`, `date_key`, `month_index`.
4. Set **Summarization = Don't summarize** for: `dim_date[year]`, `[quarter]`, `[month]`,
   `dim_customer[r_score]`, `[f_score]`, `[m_score]`, `fact_orders[months_since_first_order]`,
   `fact_orders[customer_order_seq]`, `fact_orders[review_score]`.
5. Data category: `dim_geography[state_name]` > State or Province; `latitude` > Latitude;
   `longitude` > Longitude (only needed if you add a map).

## Step 4 - Theme

**View > Themes > Browse for themes** > `theme.json`. If Power BI rejects the file, skip
this step (it is cosmetic) and use any built-in theme.

## Step 5 - Measures

**Fast path.** Go to **DAX query view** (4th icon in the left rail). Paste the whole of
`measures.dax`. Above the `DEFINE` block click **Update model with changes**
(or the "Update model: Add new measure" link above each measure). All 38 measures are
created on `fact_orders`. Then press **Run**: the single result row is your first check.

**Learning path (recommended for the first ten).** Report view > select `fact_orders` >
**Modeling > New measure** and type the measure yourself, e.g.

```
Total Revenue = CALCULATE ( SUM ( fact_order_items[price] ), fact_order_items[is_delivered] = 1 )
```

Then set formats (select the measure > Measure tools > Format):

| Format | Measures |
|---|---|
| Currency, 2 decimals (R$) | Total Revenue, Freight Revenue, AOV, Revenue Rolling 3M, Revenue YTD, Cumulative Revenue, Revenue per Customer |
| Whole number, thousands separator | Total Orders, Items Sold, Active Customers, New Customers, Returning Customers, Repeat Customers, Orders Placed, Delivered Orders, Active Sellers, Category Rank |
| Percentage, 2 decimals | Freight % of Revenue, Revenue MoM %, Revenue YoY %, Returning Customer %, Repeat Customer Rate, Cohort Retention %, Delivered Order Rate, Late Delivery %, Low Review %, Category Revenue Share %, Pareto Cumulative %, Late Delivery % (Product View), Credit Card Order Share |
| Decimal number, 2 decimals | Avg Basket Size, Avg Delivery Days, Avg Delay vs Promise, Avg Review Score, Avg Review - Late, Avg Review - On Time, Avg Review (Product View), Avg Installments (Card) |

Which slicers each family of measures responds to:

| Measures | Reads | Responds to |
|---|---|---|
| Sales (Total Revenue, Total Orders, AOV, Items Sold, time intelligence, category and seller measures) | fact_order_items | date, customer, geography, product, seller |
| Customers, delivery, reviews, payments | fact_orders | date, customer, geography (not product / seller) |
| "(Product View)" delivery and review measures | fact_order_items | everything, counted per distinct order |

## Step 6 - Validate (do not skip)

Add a blank page, drop **Card** visuals for the measures below and compare with
`EXPECTED_VALUES.md` (56 checks in total; these are the must-pass ones):

| Measure | No filters |
|---|---:|
| Total Revenue | 13,221,498.11 |
| Total Orders | 96,478 |
| AOV | 137.04 |
| Active Customers | 93,358 |
| Repeat Customer Rate | 3.00% |
| Late Delivery % | 6.77% |
| Avg Review Score | 4.156 |
| Delivered Order Rate | 97.02% |

Then add a table with `dim_date[year_month]`, `[Total Revenue]`, `[Revenue MoM %]`,
`[Revenue YoY %]`, `[Revenue Rolling 3M]` and check the **2018-08** row:
838,576.64 / -3.38% / 51.18% / 2,562,607.96.

Troubleshooting:

| Symptom | Likely cause |
|---|---|
| Total Revenue is 13,591,643.70 | the `is_delivered = 1` filter is missing (that is revenue for all statuses) |
| MoM / YoY are blank everywhere | `dim_date[date]` or `purchase_date` is Text, or relationship 1/2 is missing |
| Late Delivery % is far too low | `is_late` was imported as Text or True/False instead of Whole number |
| Cohort matrix shows dates as rows | `cohort_month` was auto-converted to Date; set it back to Text |
| Late Delivery % does not change with a category slicer | expected: use `Late Delivery % (Product View)` |

Delete the validation page (or hide it) when everything matches.

## Step 7 - Build the pages

Canvas: 16:9 (1280 x 720). On every page: a title text box top-left, and
**Filters pane > Filters on this page** as stated. Use cards across the top, the main
story chart in the widest slot, supporting charts below.

### Page 1 - Executive Overview

Question it answers: *how big is the business, is it growing, and is it healthy?*

Page filter: `dim_date[is_analysis_window]` = 1 (complete months only).
Note: with this filter the cards show Jan-2017..Aug-2018 (revenue 13,181,027.13, orders
96,211), not the all-time totals from step 6 - that is intended.

```
+----------------------------------------------------------------------------------+
| Olist Marketplace - Executive Overview            [Year slicer] [Region slicer]  |
+-------------+-------------+-------------+-------------+-------------+------------+
| Total       | Total       | AOV         | Active      | Late        | Avg Review |
| Revenue     | Orders      |             | Customers   | Delivery %  | Score      |
+-------------+-------------+-------------+-------------+-------------+------------+
|                                                    |                             |
|  A. Line: Total Revenue by year_month              |  C. Bar: Total Revenue by   |
|     (+ Revenue Rolling 3M as 2nd line, optional)   |     state (Top 10)          |
|                                                    |                             |
+----------------------------------------------------+-----------------------------+
|  B. Column: Revenue MoM % by year_month            |  D. Bar: Delivered Orders   |
|     (conditional colour: negative = red)           |     by payment_type         |
+----------------------------------------------------+-----------------------------+
```

| Visual | Type | Fields |
|---|---|---|
| Cards (6) | Card | Total Revenue, Total Orders, AOV, Active Customers, Late Delivery %, Avg Review Score |
| A | Line chart | X: `dim_date[year_month]`; Y: `[Total Revenue]` |
| B | Clustered column | X: `dim_date[year_month]`; Y: `[Revenue MoM %]`; Format > Columns > Colour > fx > Rules: < 0 red |
| C | Clustered bar | Y: `dim_geography[state]`; X: `[Total Revenue]`; visual filter: Top N = 10 by Total Revenue |
| D | Clustered bar | Y: `fact_orders[payment_type]`; X: `[Delivered Orders]` |
| Slicers | Dropdown | `dim_date[year]`, `dim_geography[region]` |

### Page 2 - Customers & Retention

Question: *do customers come back, and who is worth the most?*

No date slicer on this page (it would cut cohorts in half).

```
+----------------------------------------------------------------------------------+
| Customers & Retention                                                            |
+----------------+----------------+----------------+----------------+--------------+
| Active         | Repeat         | Revenue per    | Avg Basket     |              |
| Customers      | Customer Rate  | Customer       | Size           |              |
+----------------+----------------+----------------+----------------+--------------+
|                                                                                  |
|  A. Matrix (heatmap): Cohort Retention %                                         |
|     rows = cohort_month, columns = months_since_first_order (1..12)              |
|                                                                                  |
+-----------------------------------------+----------------------------------------+
|  B. Bar: Active Customers and           |  C. Line: New Customers and            |
|     Total Revenue by rfm_segment        |     Returning Customers by year_month  |
+-----------------------------------------+----------------------------------------+
```

| Visual | Type | Fields and settings |
|---|---|---|
| Cards (4) | Card | Active Customers, Repeat Customer Rate, Revenue per Customer, Avg Basket Size |
| A | Matrix | Rows: `dim_customer[cohort_month]`; Columns: `fact_orders[months_since_first_order]`; Values: `[Cohort Retention %]`. Visual filters: `months_since_first_order` is >= 1 and <= 12; `cohort_month` is >= 2017-01 and <= 2018-08 (basic filtering: untick 2016, 2018-09, 2018-10 and blank). Format > Cell elements > Background colour > On (gradient). Turn off row and column subtotals. |
| B | Clustered bar | Y: `dim_customer[rfm_segment]`; X: `[Active Customers]`; add `[Total Revenue]` to Tooltips. (Or two bar charts side by side: one for customers, one for revenue.) Filter out "No delivered order". |
| C | Line chart | X: `dim_date[year_month]`; Y: `[New Customers]`, `[Returning Customers]`; visual filter `is_analysis_window` = 1 |

Check: cohort 2017-05 at month 1 = 0.46%; cohort 2017-11 at month 1 = 0.57%.

### Page 3 - Delivery & Satisfaction

Question: *are we keeping the delivery promise, and what does breaking it cost?*

Page filter: `dim_date[is_analysis_window]` = 1.

```
+----------------------------------------------------------------------------------+
| Delivery & Satisfaction                           [Region slicer] [Year slicer]  |
+-------------+-------------+-------------+-------------+-------------+------------+
| Late        | Avg         | Avg Review  | Low         | Avg Review  | Avg Review |
| Delivery %  | Delivery    | Score       | Review %    | - On Time   | - Late     |
|             | Days        |             |             |             |            |
+-------------+-------------+-------------+-------------+-------------+------------+
|  A. Column: Avg Review Score            |  B. Bar: Late Delivery % by state      |
|     by delivery_band                    |     (sorted descending)                |
+-----------------------------------------+----------------------------------------+
|  C. Line: Late Delivery % by year_month |  D. Column: Delivered Orders by        |
|                                         |     review_score, legend delivery_status|
+-----------------------------------------+----------------------------------------+
```

| Visual | Type | Fields and settings |
|---|---|---|
| Cards (6) | Card | Late Delivery %, Avg Delivery Days, Avg Review Score, Low Review %, Avg Review - On Time, Avg Review - Late |
| A | Clustered column | X: `fact_orders[delivery_band]`; Y: `[Avg Review Score]`; filter out blank band |
| B | Clustered bar | Y: `dim_geography[state]`; X: `[Late Delivery %]`; sort descending; add `[Delivered Orders]` to Tooltips |
| C | Line chart | X: `dim_date[year_month]`; Y: `[Late Delivery %]` |
| D | 100% stacked column | X: `fact_orders[delivery_status]` (filter out "Not delivered"); Legend: `fact_orders[review_score]`; Y: `[Delivered Orders]` |

Check: Late Delivery % for RJ = 12.11%; for 2018-03 = 18.96%; Avg Review - Late = 2.27;
Avg Review - On Time = 4.29.

### Page 4 - Products & Sellers

Question: *which categories and sellers carry the marketplace, and which ones hurt it?*

Use only sales measures and "(Product View)" measures here.

```
+----------------------------------------------------------------------------------+
| Products & Sellers                              [Category slicer] [Seller state] |
+----------------+----------------+----------------+----------------+--------------+
| Total Revenue  | Active Sellers | Items Sold     | Freight % of   |              |
|                |                |                | Revenue        |              |
+----------------+----------------+----------------+----------------+--------------+
|  A. Bar: Total Revenue by category      |  B. Table: category, Category Rank,    |
|     (Top 15)                            |     Total Revenue, Category Revenue    |
|                                         |     Share %, Pareto Cumulative %,      |
|                                         |     Avg Review (Product View)          |
+-----------------------------------------+----------------------------------------+
|  C. Table: top sellers - seller_id, seller_state, Total Revenue, Total Orders,   |
|     Late Delivery % (Product View), Avg Review (Product View)   (Top 20)         |
+----------------------------------------------------------------------------------+
```

| Visual | Type | Fields and settings |
|---|---|---|
| Cards (4) | Card | Total Revenue, Active Sellers, Items Sold, Freight % of Revenue |
| A | Clustered bar | Y: `dim_product[category]`; X: `[Total Revenue]`; Top N = 15 |
| B | Table | `dim_product[category]`, `[Category Rank]`, `[Total Revenue]`, `[Category Revenue Share %]`, `[Pareto Cumulative %]`, `[Avg Review (Product View)]`; sort by Category Rank; add data bars to Pareto Cumulative % |
| C | Table | `dim_seller[seller_id]`, `dim_seller[seller_state]`, `[Total Revenue]`, `[Total Orders]`, `[Late Delivery % (Product View)]`, `[Avg Review (Product View)]`; Top N = 20 by Total Revenue; conditional formatting on the late % column |
| Slicers | Dropdown | `dim_product[category]`, `dim_seller[seller_state]` |

Check: health_beauty revenue 1,233,131.72 and share 9.33%; watches_gifts Pareto
cumulative 18.15%; toys (rank 10) 62.43%; Active Sellers 2,970; top seller
`4869f7a5...` late rate 10.50%.

---

## Finishing

1. Give each page a one-sentence takeaway text box (use the findings in `../INSIGHTS.md`).
2. Save as `Olist_Analytics.pbix` in this folder.
3. Export a PDF (File > Export > PDF) or take screenshots for your portfolio / README.

## Questions you should be able to answer about your own report

* Why two fact tables, and why are they not related to each other?
* Why is `customer_unique_id`, not `customer_id`, the customer key?
* What does `CALCULATE` do in `[Total Revenue]`? What is filter context?
* Why does `[Repeat Customers]` need `VALUES` + `CALCULATE` (context transition)?
* Why does `[Revenue Rolling 3M]` use `month_index` instead of `DATESINPERIOD`?
* Why are there two late-delivery measures, and when do they differ?
* Why is `BLANK = 0` dangerous in DAX, and how do the 0/1 flag columns avoid it?
* How do you know your numbers are right? (You reconciled 56 values against SQL.)
