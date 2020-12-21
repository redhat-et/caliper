from itertools import groupby
import plotly.graph_objects as go
import pandas as pd
import plotly.express as px
import psycopg2

# import plotly.graph_objects as go

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_colwidth", None)

conn = psycopg2.connect(
    host="localhost",
    port="5432",
    database="metric_data",
    user="promtop",
    password="password"
)
cur = conn.cursor()

# query = """
#     SELECT version, metric, label_app, AVG(value) AS total FROM metrics
#     WHERE aggregator_code = 'AVG' AND metric = 'container_cpu_usage_seconds_total'
#     GROUP BY version, label_app, metric
#     ORDER BY version, total DESC;
#     """

query = """
    SELECT version, label_app, value FROM metrics
    WHERE aggregator_code = 'AVG' AND metric = 'container_cpu_usage_seconds_total'
    ORDER BY version, label_app, value;
"""

cur.execute(query)
desc = cur.description

columns = [col[0] for col in desc]
rows = [row for row in cur.fetchall()]

# labeledRows = list(dict(zip(columns, r)) for r in rows)
labelRowPct = []
for k, g in groupby(
        sorted(rows, key=lambda a: a[columns.index("version")]),
        key=lambda a: a[columns.index("version")]):
    # if k not in labelRowPct:
    #     labelRowPct[k] = []
    grp = list(g)
    groupTotal = sum([v[columns.index("value")] for v in grp])
    for k2, g2 in groupby(grp, key=lambda a: a[1]):
        print(k2)
        pct = (sum(n[2] for n in g2) / groupTotal) * 100
        ent = {
            "version": k,
            "value": round(pct, ndigits=2),
            "label_app": str(k2)
        }
        labelRowPct.append(ent)

print(labelRowPct)
df = pd.DataFrame(data=labelRowPct)
df.sort_values(by="value", inplace=True, ascending=False)
fig = px.bar(df,
             title="OCP Versions vs % CPU consumption in nanoseconds per app-label",
             width=1500,
             color="label_app",
             x="version",
             y="value",
             range_y=(0, 100),
             labels=dict(
                 version="OCP Version",
                 value="% of Total CPU Usage in Nanoseconds",
                 valueSuffix="%",
             )
             )
fig.update_yaxes(showticksuffix="all", ticksuffix="%")
fig.show()
