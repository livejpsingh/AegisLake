import duckdb
import pandas as pd
import numpy as np

print("NumPy version:", np.__version__)
print("Pandas version:", pd.__version__)
print("DuckDB version:", duckdb.__version__)

con = duckdb.connect()
res = con.execute("SELECT 42 AS test").fetchall()
print("DuckDB query result:", res)
