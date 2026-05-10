import sys
import json
import os

sys.stdout.reconfigure(encoding="utf-8")

REPORT_PATH = "./reports/report.json"
WEIGHTED_REPORT_PATH = "./reports/weighted_report.json"

def print_report():
    if not os.path.exists(REPORT_PATH):
        print(f"Report not found at {REPORT_PATH}. Run analysis.py first.")
        return

    weighted_report = {}
    if os.path.exists(WEIGHTED_REPORT_PATH):
        with open(WEIGHTED_REPORT_PATH, "r", encoding="utf-8") as f:
            weighted_report = json.load(f)

    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        r = json.load(f)

    print("\n==================== PATENT REPORT ====================")
    print(f"  Total Patents : {r['total_patents']:,}")
    print(f"  Peak Year     : {r['peak_year']['year']} ({r['peak_year']['patents']:,} patents)\n")

    #  Top Inventors 
    print("\n  Top Inventors (Raw patent count):")
    for i, row in enumerate(r["top_inventors"], 1):
        print(f"    {i:>2}. {row['name']} — {int(row['patents']):,}")

    #  Weighted Inventors (H-Index) 
    if weighted_report.get("weighted_inventors_hindex"):
        print("\n  Weighted Inventors (H-Index):")
        for i, row in enumerate(weighted_report["weighted_inventors_hindex"], 1):
            raw_patents = int(row.get('patents', 0))
            print(
                f"    {i:>2}. {row['name']} — h-index {int(row['h_index']):,} | "
                f"total citations: {int(row.get('total_citations', 0)):,} | "
                f"avg citations: {float(row.get('avg_citations', 0)):.2f} [{raw_patents:,} raw]"
            )

    #  Top Companies 
    print("\n  Top Companies (Raw patent count):")
    for i, row in enumerate(r["top_companies"], 1):
        print(f"    {i:>2}. {row['name']} — {int(row['patents']):,}")

    #  Weighted Companies (Citation Impact) 
    if weighted_report.get("weighted_companies_citations"):
        print("\n  Weighted Companies (Citation Impact):")
        for i, row in enumerate(weighted_report["weighted_companies_citations"], 1):
            raw_patents = int(row.get('patent_count', 0))
            print(
                f"    {i:>2}. {row['name']} — "
                f"total citations: {int(row.get('total_citations', 0)):,} | "
                f"avg citations/patent: {float(row.get('avg_citations_per_patent', 0)):.2f} | "
                f"max single-patent citations: {int(row.get('max_single_patent_citations', 0)):,} [{raw_patents:,} raw]"
            )

    #  Top Countries 
    print("\n  Top Countries:")
    for i, row in enumerate(r["top_countries"], 1):
        share = float(row["share"]) * 100
        print(f"    {i:>2}. {row['country']} — {int(row['patents']):,} ({share:.1f}%)")

    #  Patent Growth (last 5 years) 
    print("\n  Patent Growth (last 5 years on record):")
    trends = r["yearly_trends"]
    for row in trends[-5:]:
        pct = row.get("growth_pct")
        patents = int(row["patents"])
        year    = int(row["year"])
        if pct is not None and str(pct) != "nan":
            arrow = "▲" if float(pct) > 0 else "▼"
            print(f"    {year}: {patents:,}  {arrow} {abs(float(pct))}%")
        else:
            print(f"    {year}: {patents:,}")

    #  Solo vs Team 
    print("\n  Solo vs Team Patents:")
    for row in r["solo_vs_team"]:
        print(f"    {row['inventor_type']}: {int(row['patents']):,} ({row['share_pct']}%)")

    #  Top Company Per Decade 
    print("\n  Top Company Per Decade (1900s onwards):")
    for row in r["top_company_per_decade"]:
        if int(row["decade"]) >= 1900:
            print(f"    {int(row['decade'])}s: {row['company_name']} — {int(row['patents']):,}")

    #  Top Inventor Per Country 
    print("\n  Top Inventor Per Country (top 20):")
    for row in r["top_inventor_per_country"]:
        print(f"    {row['country']:<4} {row['inventor_name']} — {int(row['patents']):,}")

    #  Top Inventor-Company Pairs 
    print("\n  Top Inventor-Company Pairs:")
    for i, row in enumerate(r["inventor_company_pairs"], 1):
        print(f"    {i:>2}. {row['inventor_name']} @ {row['company_name']}")
        print(f"        Shared: {int(row['shared_patents']):,}  |  "
              f"Inventor total: {int(row['inventor_patents']):,}  |  "
              f"Company total: {int(row['company_patents']):,}")
        
    CPC_LABELS = {
        "A": "Human Necessities",
        "B": "Operations & Transport",
        "C": "Chemistry & Metallurgy",
        "D": "Textiles & Paper",
        "E": "Fixed Constructions",
        "F": "Mechanical Engineering",
        "G": "Physics",
        "H": "Electricity",
        "Y": "New Technologies",
    }

    print("\n  Patents by Technology Section:")
    for row in r["cpc_sections"]:
        label = CPC_LABELS.get(row["cpc_section"], row["cpc_section"])
        print(f"    {row['cpc_section']} — {label:<25} {int(row['patents']):>10,}")

    print("\n  Top Company per Technology Section:")
    for row in r["cpc_top_companies"]:
        label = CPC_LABELS.get(row["cpc_section"], row["cpc_section"])
        print(f"    {row['cpc_section']} — {label:<25} {row['company_name']} ({int(row['patents']):,})")

    print("\n=======================================================")
    print(f"  Source: {REPORT_PATH}")
    print("=======================================================\n")

if __name__ == "__main__":
    print_report()