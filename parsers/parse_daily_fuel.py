"""
parse_daily_fuel.py
Parses the daily "REPORT OF COAL/FUEL OIL POSITION" sheet (Sheet1 of the
WhatsApp-collected workbook) into daily_fuel rows, applying the same
reconciliation check used in Step 3 of the build plan:
    opening + receipt - consumption == closing  (flag if not)

Usage:
    python parse_daily_fuel.py <path-to-xlsx> > ../data/daily_fuel.json
"""
import sys
import json
import openpyxl

PLANT_MAP = {
    "ANPARA": "Anpara",
    "OBRA**": "Obra B",
    "OBRA-C": "Obra C",
    "OBRA-C".upper(): "Obra C",
    "H'GANJ ##": "Harduaganj",
    "PARICHHA": "Parichha",
    "JAWAHARPUR": "Jawaharpur",
    "PANKI": "Panki Extn",
}

FUEL_MAP = {
    "COAL": "COAL",
    "LDO": "LDO",
    "FO": "LSHS",
    "LSHS": "LSHS",
}


def normalize_plant(name):
    if not name:
        return None
    key = str(name).strip().upper()
    for k, v in PLANT_MAP.items():
        if k in key:
            return v
    return str(name).strip()


def normalize_fuel(item_label):
    if not item_label:
        return None
    label = str(item_label).strip().upper()
    if "COAL" in label:
        return "COAL"
    if "LDO" in label:
        return "LDO"
    if "LSHS" in label or label.startswith("FO"):
        return "LSHS"
    return None


def parse(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Sheet1"]
    rows = list(ws.iter_rows(values_only=True))

    # report date sits near top ("Reporting date", col J row 7 per inspection)
    report_date = None
    for row in rows[:8]:
        for i, v in enumerate(row):
            if v == "Reporting date" and i + 1 < len(row):
                report_date = row[i + 1]

    records = []
    current_plant = None
    for row in rows[10:]:
        plant_raw = row[2]
        sl_raw = row[1]
        if str(sl_raw or "").strip().upper() == "TOTAL" or str(plant_raw or "").strip().upper() == "TOTAL":
            current_plant = None  # stop attributing rows to a plant once we hit the TOTAL block
            continue
        if plant_raw:
            current_plant = plant_raw

        item = row[3]
        fuel_type = normalize_fuel(item)
        if not fuel_type or not current_plant:
            continue

        monthly_linkage = row[4]
        opening = row[5]
        receipt = row[6]
        consumption = row[7]
        closing = row[8]
        days_stock = row[9]
        rakes = row[18] if len(row) > 18 else None
        generation_mu = row[15] if len(row) > 15 else None
        plf_pct = row[16] if len(row) > 16 else None

        recon_flag = False
        recon_delta = None
        if all(v is not None for v in (opening, receipt, consumption, closing)):
            expected_closing = opening + receipt - consumption
            recon_delta = round(expected_closing - closing, 3)
            recon_flag = abs(recon_delta) > 1  # >1 MT/KL tolerance

        records.append({
            "plant": normalize_plant(current_plant),
            "report_date": str(report_date),
            "fuel_type": fuel_type,
            "monthly_linkage": monthly_linkage,
            "opening_balance": opening,
            "receipt": receipt,
            "consumption_release": consumption,
            "closing_balance": closing,
            "days_stock_cover": days_stock,
            "rakes_received": rakes,
            "generation_mu": generation_mu,
            "plf_pct": plf_pct,
            "reconciliation_flag": recon_flag,
            "reconciliation_delta": recon_delta,
        })

    return records


if __name__ == "__main__":
    path = sys.argv[1]
    out = parse(path)
    print(json.dumps(out, indent=2, default=str))
