"""
parse_fsa.py
Deterministic parser for "FSA and Bridge Linkage Details" workbook.
Output matches `constraints_registry` schema (without DB-generated uuids).

Usage:
    python parse_fsa.py <path-to-xlsx> > ../data/constraints_registry.json
"""
import sys
import json
import openpyxl


def parse(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Sheet1"]
    rows = list(ws.iter_rows(values_only=True))

    records = []
    current_fsa_plant = None
    current_bridge_plant = None

    for row in rows[4:]:  # skip title/header rows
        fsa_plant, fsa_company, fsa_acq = row[0], row[1], row[2]
        br_plant, br_company, br_qty, br_remarks = row[3], row[4], row[5], row[6]

        # FSA side
        if fsa_plant and "Total" not in str(fsa_plant):
            current_fsa_plant = str(fsa_plant).strip()
        if fsa_company and fsa_acq is not None and current_fsa_plant:
            records.append({
                "plant": current_fsa_plant,
                "company": str(fsa_company).strip(),
                "linkage_type": "FSA",
                "acq_lac_mt": float(fsa_acq),
                "valid_to": None,
                "source_clause": "FSA and Bridge Linkage Details 2026-27, Sheet1",
            })

        # Bridge linkage side
        if br_plant and "Total" not in str(br_plant):
            current_bridge_plant = str(br_plant).strip()
        if br_company and br_qty is not None and current_bridge_plant:
            valid_to = None
            if br_remarks and "Valid till" in str(br_remarks):
                valid_to = str(br_remarks).split("Valid till")[-1].strip()
            records.append({
                "plant": current_bridge_plant,
                "company": str(br_company).strip(),
                "linkage_type": "BRIDGE_LINKAGE",
                "acq_lac_mt": float(br_qty),
                "valid_to": valid_to,
                "source_clause": str(br_remarks) if br_remarks else None,
            })

    return records


if __name__ == "__main__":
    path = sys.argv[1]
    out = parse(path)
    print(json.dumps(out, indent=2))
