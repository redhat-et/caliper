import os
import semver
import dash
import dash_core_components as dcc
import dash_html_components as html
import numpy
import pandas as pd
import psycopg2
import yaml
from dash.dependencies import Input, Output
from dotenv import load_dotenv
from plotly import express as px
from plotly import graph_objects as go

# for debugging dataframes printed to console
pd.set_option('min_rows', 10)
pd.set_option('max_rows', 500)
pd.set_option('display.max_columns', 20)
pd.set_option('display.width', 1098)

load_dotenv()
pg_host = os.getenv('PGHOST')
pg_port = os.getenv('PGPORT')
pg_database = os.getenv('PGDATABASE')
pg_user = os.getenv('PGUSER')
pg_password = os.getenv('PGPASSWORD')
conn = psycopg2.connect(
    host=pg_host,
    port=pg_port,
    database=pg_database,
    user=pg_user,
    password=pg_password
)

with open('component-mappings.yaml', 'r') as file:
    group_config = yaml.load(file, Loader=yaml.FullLoader)
    file.close()

value_columns = ['q95_value', 'avg_value', 'min_value', 'max_value']


def db_numeric_to_float(df):
    for v in value_columns:
        df[v] = df[v].astype('float')
    df = assign_groupings(df)
    return df


def version_order():
    order_versions = []
    try:
        v = semver.VersionInfo.parse('4.6.0')
        order_versions.append(str(v))
        # inc minor ver
        for i in range(1):
            # inc patch ver
            for k in range(20):
                v = v.bump_patch()
                order_versions.append(str(v))
            v = v.replace(patch=0)
            v = v.bump_minor()
            order_versions.append(str(v))
    except Exception as e:
        print(f"exception: {e}")
        pass
    return order_versions


def df_mem_bytes_to_gigabytes(df):
    for v in value_columns:
        df[v] = df[v] / 10.0 ** 9
    return df


def df_seconds_to_hours(df):
    for v in value_columns:
        df[v] = df[v] / (60 * 60)
    return df


def assign_groupings(df=pd.DataFrame()):
    groups = numpy.empty(len(df), dtype=object)
    df.insert(len(df.columns), 'group', groups)
    for grp, namespaces in group_config.items():
        for ns in namespaces:
            df.loc[df['namespace'] == ns, ['group']] = grp
    return df


def executeQuery(query):
    cur = conn.cursor()
    cur.execute(query)
    desc = cur.description
    columns = [col[0] for col in desc]
    rows = [row for row in cur.fetchall()]
    df = pd.DataFrame([[c for c in r] for r in rows])
    df.rename(inplace=True, columns=dict(enumerate(columns)))
    df = db_numeric_to_float(df)
    return df


def sort_by_version(df=pd.DataFrame()) -> pd.DataFrame:
    df['version'] = df['version'].map(semver.parse_version_info)
    df.sort_values(by='version', inplace=True)
    df['version'] = df['version'].astype(dtype=str)
    return df


def get_mem_metrics():
    query_mem = """
    SELECT * FROM collated_metrics WHERE metric = 'container_memory_bytes';
    """
    df = executeQuery(query_mem)
    df = df_mem_bytes_to_gigabytes(df)
    return df


def get_cpu_metrics():
    query_cpu = """
    SELECT * FROM collated_metrics WHERE metric = 'cpu_usage_ratio';
    """
    df = executeQuery(query_cpu)
    df = df_seconds_to_hours(df)
    return df


def trim_and_group(df, op=''):
    df = df.groupby(by=['version', 'group'], sort=True, as_index=False).sum()
    df = df.groupby(by=['version'], sort=True, as_index=False).apply(
        lambda frame: frame.sort_values(by=[op], inplace=False))
    df.reset_index(inplace=True)
    return df


def get_max_bar_height(df=pd.DataFrame()):
    df_summed = df.groupby(by=['version']).sum()
    m = max(df_summed.select_dtypes(include='float64').max())
    return m


def pad_range(r=0):
    return r * 1.1


def color_map(df=pd.DataFrame()):
    cm = {}
    colors = px.colors.qualitative.G10
    grp = df.groupby(by='group', as_index=True, sort=True)
    i = 0
    for g in grp.groups:
        cm[g] = colors[i]
        i += 1
    return cm


def pod_max(df=pd.DataFrame(), op='') -> pd.DataFrame():
    grp = df.groupby(by=['version', 'node'], sort=True, as_index=True).max(numeric_only=True)
    # print(grp)
    return

def pod_min(df=pd.DataFrame()) -> pd.DataFrame(): return


def pod_avg(df=pd.DataFrame()) -> pd.DataFrame(): return


def pod_q95(df=pd.DataFrame()) -> pd.DataFrame(): return


def operators(df=pd.DataFrame()) -> pd.DataFrame(): return


def bar_fig(df=pd.DataFrame(), op='', y_max=0.0, title='', y_title='', x_title='', suffix='', legend_title=''):
    df['version'] = df['version'].map(semver.parse_version_info)
    df.sort_values(by=['version'], inplace=True)
    df['version'] = df['version'].astype(dtype=str)
    fig = px.bar(
        data_frame=df,
        x='version',
        y=['group', op],
        color='group',
        title=title,
        color_discrete_map=color_map(df),
    )
    fig.update_yaxes(
        go.layout.YAxis(
            title=y_title,
            ticksuffix=suffix,
            range=[0, y_max],
            fixedrange=True,
        ))
    fig.update_xaxes(go.layout.XAxis(
        title=x_title,
    ))
    fig.update_layout(
        go.Layout(
            legend=go.layout.Legend(
                title=legend_title,
                traceorder='reversed',
            ),
        )
    )
    return fig


def line_fig(df=pd.DataFrame(), op='', y_max=0.0, title='', y_title='', x_title='', tick_suffix=''):
    fig = go.Figure()
    fig.update_layout({
        "title": title,
        "legend": {
            "traceorder": 'grouped+reversed',
        },
    })
    fig.update_yaxes({
        "title": y_title,
        "ticksuffix": tick_suffix,
        "fixedrange": True,
        "range": [0, y_max]
    })
    fig.update_xaxes({
        "title": x_title
    })

    groups = df.groupby(by='group', sort=True)
    cm = color_map(df)
    for name, g in groups:
        g['version'] = g['version'].map(semver.parse_version_info)
        g.sort_values(by='version', inplace=True)
        g['version'] = g['version'].astype(str)
        fig.add_trace(
            go.Scatter(
                name=name,
                x=g['version'],
                y=g[op],
                legendgroup=1,
                marker={'color': cm[name]},
            )
        )

    return fig


def bar_group_fig(df=pd.DataFrame(), op='', y_max=0.0, group='', title='', y_title='', x_title='', tick_suffix=''):
    return go.Figure()

    fig = go.Figure()
    fig.update_layout({
        'title': title,
        'barmode': 'group'
    })
    fig.update_yaxes(
        {
            'title': y_title,
            'ticksuffix': tick_suffix,
            'fixedrange': True,
            'range': [0, y_max]
        }
    )
    fig.update_xaxes({
        'title': x_title
    })

    groups = df.groupby(by=group, sort=True)
    for n, g in groups:
        g.sort_values(by=op, ascending=False)
    for n, g in groups:
        fig.add_trace(
            go.Bar(
                name=n,
                x=g['']
            )
        )

    return fig


radio_options = [
    {'label': '95th-%', 'value': 'q95_value'},
    {'label': 'Average', 'value': 'avg_value'},
    {'label': 'Min', 'value': 'min_value'},
    {'label': 'Max', 'value': 'max_value'},
]

app = dash.Dash(__name__, external_stylesheets=['./style.css'])
app.layout = html.Div(children=[
    html.H1(children='Caliper - Basic Dashboard'),
    html.H2(children='Net Resource Usage by an Idle 6 Node Cluster, Span 10min'),
    html.Div(children=[
        dcc.Graph(id='mem-group'),
        dcc.RadioItems(id='memory-group-op-radio', value='q95_value', options=radio_options),
    ]
    ),
    html.Div(children=[
        dcc.Graph(id='memory-graph'),
        dcc.RadioItems(id='memory-op-radio', value='q95_value', options=radio_options),
    ]
    ),
    html.Div(children=[
        dcc.Graph(id='cpu-graph'),
        dcc.RadioItems(id='cpu-op-radio', value='q95_value', options=radio_options)
    ]),
    html.Div(children=[
        dcc.Graph(id='mem-line'),
        dcc.RadioItems(id='mem-line-input', value='q95_value', options=radio_options)
    ]),
    html.Div(children=[
        dcc.Graph(id='cpu-line'),
        dcc.RadioItems(id='cpu-line-input', value='q95_value', options=radio_options)
    ])
])


@app.callback(
    Output(component_id='mem-group', component_property='figure'),
    Input(component_id='memory-group-op-radio', component_property='value')
)
def mem_group(op):
    df_mem = get_mem_metrics()
    y_max = pad_range(get_max_bar_height(df_mem))
    return bar_group_fig(df=df_mem, op=op, y_max=y_max, group='node', title='test grouping', tick_suffix='Gb',
                         y_title='memory', x_title='OCP Version')


@app.callback(
    Output(component_id='memory-graph', component_property='figure'),
    Input(component_id='memory-op-radio', component_property='value')
)
def mem_response(op):
    df_mem = get_mem_metrics()
    y_max = pad_range(get_max_bar_height(df_mem))
    df_mem = trim_and_group(df_mem, op=op)
    return bar_fig(df=df_mem, op=op, y_max=y_max, title='Total memory consumed', suffix='Gb', y_title='Memory (Gb)',
                   x_title='OCP Version')


@app.callback(
    Output(component_id='cpu-graph', component_property='figure'),
    Input(component_id='cpu-op-radio', component_property='value')
)
def cpu_response(op):
    df_cpu = get_cpu_metrics()
    y_max = pad_range(get_max_bar_height(df_cpu))
    df_cpu = trim_and_group(df_cpu, op)
    return bar_fig(df_cpu, op, y_max, title='Cluster CPU Time by OCP Version', suffix='Hrs',
                   y_title='Net CPU Time in Hours', x_title='OCP Versions', legend_title='')


@app.callback(
    Output(component_id='mem-line', component_property='figure'),
    Input(component_id='mem-line-input', component_property='value')
)
def mem_line_response(op):
    df_mem = get_mem_metrics()
    df_mem = trim_and_group(df_mem, op)
    y_max = pad_range(df_mem['max_value'].max())
    return line_fig(df=df_mem, op=op, y_max=y_max, tick_suffix='Gb', title='Memory Usage Trends by OCP Version',
                    y_title='Net Memory Consumed in Gigabytes', x_title='OCP Version')


@app.callback(
    Output(component_id='cpu-line', component_property='figure'),
    Input(component_id='cpu-line-input', component_property='value')
)
def mem_line_response(op):
    try:
        df_mem = get_cpu_metrics()
        df_mem = trim_and_group(df_mem, op)
        y_max = pad_range(df_mem['max_value'].max())
    except Exception as e:
        print(e)
        pass
    return line_fig(df=df_mem, op=op, y_max=y_max, tick_suffix='Hrs', title='CPU Time Trends by OCP Version',
                    y_title='Net CPU Time in Hours', x_title='OCP Version')


if __name__ == '__main__':
    app.run_server(debug=True, port=8050, host='0.0.0.0')

# Graph ideas
# Top 5 offenders
# by instance groupings
# group operators and workloads
