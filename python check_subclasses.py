import sqlite3
import pandas as pd

conn = sqlite3.connect("patents.db")
df = pd.read_sql_query("""
    SELECT cpc_subclass, cpc_section, COUNT(DISTINCT patent_id) AS patents
    FROM cpc_detail
    GROUP BY cpc_subclass, cpc_section
    ORDER BY patents DESC
    LIMIT 20;
""", conn)
conn.close()
print(df.to_string())