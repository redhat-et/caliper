import dash
import dash_core_components as dcc
import dash_html_components as html
import numpy
import pandas as pd
import psycopg2
import yaml
import os
from dotenv import load_dotenv
from dash.dependencies import Input, Output
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


def get_mem_metrics():
    query_mem = """
    SELECT * FROM collated_metrics WHERE metric = 'container_memory_usage_bytes';
    """
    df = executeQuery(query_mem)
    df = df_mem_bytes_to_gigabytes(df)
    return df


def get_cpu_metrics():
    query_cpu = """
    SELECT * FROM collated_metrics WHERE metric = 'container_cpu_usage_seconds_total';
    """
    df = executeQuery(query_cpu)
    df = df_seconds_to_hours(df)
    return df


def trim_and_group(df, op='avg_value'):
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


def generate_mem_bar_fig(df=pd.DataFrame(), op='q95_value', y_max=0.0):
    fig = px.bar(
        data_frame=df,
        x='version',
        y=['group', op],
        color='group',
        title='Cluster Memory Usage by OCP Version',
        color_discrete_map=color_map(df),
    )
    fig.update_yaxes(
        go.layout.YAxis(
            title='Net Memory Usage by Groups In Gigabytes',
            ticksuffix='Gb',
            range=[0, y_max],
            fixedrange=True,
        ))
    fig.update_xaxes(go.layout.XAxis(
        title='OCP Versions',
    ))
    fig.update_layout(
        go.Layout(
            legend=go.layout.Legend(
                title='OCP Component Groups',
                traceorder='reversed',
            ),
        )
    )
    return fig


def generate_cpu_bar_fig(df=pd.DataFrame(), op='q95_value', y_max=0.0):
    fig = px.bar(
        data_frame=df,
        x='version',
        y=op,
        color='group',
        title='Cluster CPU Time by OCP Version',
        color_discrete_map=color_map(df),
    )
    fig.update_yaxes(go.layout.YAxis(
        ticksuffix='hs',
        title='Net CPU Time in Hours',
        range=[0, y_max],
        fixedrange=True,
    ))
    fig.update_xaxes({
        'title': 'OCP Versions'
    })
    fig.update_layout(
        go.Layout(
            legend=go.layout.Legend(
                title='OCP Component Groups',
                traceorder='reversed',
            )
        )
    )
    return fig


def generate_mem_line(df=pd.DataFrame(), op='q95_value', y_max=0.0):
    fig = go.Figure()
    fig.update_layout({
        "title": 'Memory Usage Trends by OCP Version',
        "legend": {
            "traceorder": 'grouped+reversed',
        },
    })
    fig.update_yaxes({
        "title": 'Net Memory Consumed in Gigabytes',
        "ticksuffix": 'Gb',
        "fixedrange": True,
        "range": [0, y_max]
    })
    fig.update_xaxes({
        "title": 'OCP Version'
    })

    groups = df.groupby(by='group', sort=True)
    for n, g in groups:
        g.sort_values(by=op, ascending=False)
    cm = color_map(df)
    for name, g in groups:
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


def generate_cpu_line(df=pd.DataFrame(), op='q95_value', y_max=0.0):
    fig = go.Figure()
    fig.update_layout({
        "title": 'CPU Time Trends by OCP Version',
        "legend": {
            "traceorder": 'grouped+reversed',
        }
    })
    fig.update_yaxes({
        "title": 'Net CPU Time in Hours',
        "ticksuffix": 'hs',
        "fixedrange": True,
        "range": [0, y_max]
    })
    fig.update_xaxes({
        "title": 'OCP Version'
    })

    groups = df.groupby(by='group', sort=True)
    for n, g in groups:
        g.sort_values(by=op, ascending=False)
    cm = color_map(df)
    for name, g in groups:
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


radio_options = [
    {'label': '95th-%', 'value': 'q95_value'},
    {'label': 'Average', 'value': 'avg_value'},
    {'label': 'Min', 'value': 'min_value'},
    {'label': 'Max', 'value': 'max_value'},
]

app = dash.Dash(__name__)
app.layout = html.Div(children=[
    html.H1(children='Caliper - Basic Dashboard'),
    html.H2(children='Net Resource Usage by an Idle 6 Node Cluster, Span 10min'),
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
    Output(component_id='memory-graph', component_property='figure'),
    Input(component_id='memory-op-radio', component_property='value')
)
def mem_response(op):
    df_mem = get_mem_metrics()
    y_max = pad_range(get_max_bar_height(df_mem))
    df_mem = trim_and_group(df_mem, op=op)
    return generate_mem_bar_fig(df_mem, op=op, y_max=y_max)


@app.callback(
    Output(component_id='cpu-graph', component_property='figure'),
    Input(component_id='cpu-op-radio', component_property='value')
)
def cpu_response(op):
    df_cpu = get_cpu_metrics()
    y_max = pad_range(get_max_bar_height(df_cpu))
    df_cpu = trim_and_group(df_cpu, op)
    return generate_cpu_bar_fig(df_cpu, op, y_max)


@app.callback(
    Output(component_id='mem-line', component_property='figure'),
    Input(component_id='mem-line-input', component_property='value')
)
def mem_line_response(op):
    df_mem = get_mem_metrics()
    df_mem = trim_and_group(df_mem, op)
    y_max = pad_range(df_mem['max_value'].max())
    return generate_mem_line(df_mem, op, y_max)


@app.callback(
    Output(component_id='cpu-line', component_property='figure'),
    Input(component_id='cpu-line-input', component_property='value')
)
def mem_line_response(op):
    df_mem = get_cpu_metrics()
    df_mem = trim_and_group(df_mem, op)
    y_max = pad_range(df_mem['max_value'].max())
    return generate_cpu_line(df_mem, op, y_max)


if __name__ == '__main__':
    app.run_server(debug=True, port=8050, host='0.0.0.0')
