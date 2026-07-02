"""
parse_cost_dynamics.py
Parses "VC for last 5 months for UNL and IPPs.xlsx" -> Sheet2 ("Coal Cost Dynamics")
into cost_inputs rows: landed cost, GCV, variable cost per plant/company,
using the most recent period block in the sheet (April 2026 block in this file).

The sheet has three repeating column blocks for different periods (end of March,
April 1, end of April). We pull the most recent ("At the end of April 2026") block.

Usage:
    python parse_cost_dynamics.py <path-to-xlsx> > ../data/cost_inputs.json
"""
import sys
import json
import openpyxl


def parse(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Sheet2"]
    rows = list(ws.iter_rows(values_only=True))

    header = rows[3]  # row with column names (0-indexed row 3 per inspection)
    data_rows = rows[4:]

    # "At the end of April 2026" block columns (13-22, 0-indexed) per inspected header:
    # 13 Total Coal Stock(MT) 14 Amount 15 Rate in stock 16 VC
    # 17 Rate of Coal(Rs/MT) 18 Premium% 19 Distance(km) 20 Freight Rate 21 Landed Cost 22 GCV 23 VC(approx)
    idx_plant = 0
    idx_linkage_type = 1
    idx_company = 2
    idx_acq = 3
    idx_landed_cost_end_apr = 21
    idx_gcv = 22
    idx_vc_end_apr = 23
    idx_planned_supply = 25

    records = []
    current_plant = None
    for row in data_rows:
        plant = row[idx_plant]
        if plant and str(plant).strip():
            current_plant = str(plant).strip().rstrip("*").strip()
        company = row[idx_company]
        if not company or not current_plant:
            continue
        landed_cost = row[idx_landed_cost_end_apr]
        gcv = row[idx_gcv]
        vc = row[idx_vc_end_apr]
        if landed_cost is None and vc is None:
            continue
        records.append({
            "plant": current_plant,
            "company": str(company).strip(),
            "linkage_type": row[idx_linkage_type],
            "landed_cost_rs_mt": landed_cost,
            "gcv_kcal_kg": gcv,
            "variable_cost_rs_kwh": vc,
            "period": "End of April 2026",
            "source": "VC for last 5 months for UNL and IPPs.xlsx, Sheet2",
        })

    return records


if __name__ == "__main__":
    path = sys.argv[1]
    out = parse(path)
    print(json.dumps(out, indent=2, default=str))
