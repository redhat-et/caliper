import os

import dash
import dash_core_components as dcc
import dash_html_components as html
import numpy
import pandas as pd
import psycopg2
import semver
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


def order_versions():
    versions = []
    try:
        v = semver.VersionInfo.parse('4.6.0')
        versions.append(str(v))
        # inc minor ver
        for i in range(1):
            # inc patch ver
            for k in range(20):
                v = v.bump_patch()
                versions.append(str(v))
            v = v.replace(patch=0)
            v = v.bump_minor()
            versions.append(str(v))
    except Exception as e:
        print(f"exception: {e}")
        pass
    return versions


def df_mem_bytes_to_gigabytes(df):
    for v in value_columns:
        df[v] = df[v] / 10.0 ** 9
    return df


def assign_groupings(df=pd.DataFrame()):
    groups = numpy.empty(len(df), dtype=object)
    try:
        df.insert(len(df.columns), 'group', groups)
    except KeyError as e:
        print(f"dataframe exception: {e}")
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
    SELECT * FROM caliper_metrics WHERE metric = 'container_memory_bytes';
    """
    df = executeQuery(query_mem)
    df = df_mem_bytes_to_gigabytes(df)
    return df


def get_cpu_metrics():
    query_cpu = """
    SELECT * FROM caliper_metrics WHERE metric = 'cpu_usage_ratio';
    """
    df = executeQuery(query_cpu)
    for v in value_columns:
        df[v] = df[v] * 100
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


def color_map(df=pd.DataFrame(), by='') -> dict:
    cm = {}
    colors = px.colors.qualitative.G10
    try:
        grp = df.groupby(by=by, as_index=True, sort=True)
    except Exception as e:
        raise KeyError(f'color_map.dataframe.groupby: {type(e)}: input value {e} raised exception')
    i = 0
    for g in grp.groups:
        cm[g] = colors[i]
        i += 1
    return cm


def pod_max(df=pd.DataFrame(), op='', by='') -> pd.DataFrame():
    return df.groupby(by=['version', by, op], sort=True, as_index=True).max(numeric_only=True).reset_index()



def pod_min(df=pd.DataFrame()) -> pd.DataFrame(): return


def pod_avg(df=pd.DataFrame()) -> pd.DataFrame(): return


def pod_q95(df=pd.DataFrame()) -> pd.DataFrame(): return


op_map = {
    'max': pod_max,
    'min': pod_min,
    'avg': pod_avg,
    'q95': pod_q95,
}


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
        color_discrete_map=color_map(df, by='group'),
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
    try:
        cm = color_map(df, by='group')
        groups = df.groupby(by='group', sort=True)
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
    except Exception as e:
        raise Exception(f'line_fig: {e}')

    return fig


def bar_group_fig(df=pd.DataFrame(), op='', y_max=0.0, title='', y_title='', x_title='', tick_suffix=''):
    df = df[['version', 'group', 'namespace', 'pod', op]]
    df = df.groupby(by=['version', 'group']).max().reset_index()

    y_max = pad_range(df[op].max())

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
    try:
        cm = color_map(df, by='group')
        versions = pd.unique(df['version'])
        for name, group in df.groupby(by='group', sort=True):
            fig.add_trace(
                go.Bar(
                    name=name,
                    x=versions,
                    y=group[op],
                    legendgroup=1,
                    marker={'color': cm[name]}
                )
            )
    except Exception as e:
        print(f'bar_group_fig: {e}')
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
    ]),
    html.Div(children=[
        dcc.Graph(id='memory-graph'),
        dcc.RadioItems(id='memory-op-radio', value='q95_value', options=radio_options),
    ]),
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
    try:
        df_mem = get_mem_metrics()
        y_max = pad_range(get_max_bar_height(df_mem))
        trim_and_group(df_mem, op)
        return bar_group_fig(df=df_mem, op=op, y_max=y_max, title='test grouping', tick_suffix='Gb',
                             y_title='memory', x_title='OCP Version')
    except Exception as e:
        print(f'mem_group: got exception type {type(e)}:\n{e}')


@app.callback(
    Output(component_id='memory-graph', component_property='figure'),
    Input(component_id='memory-op-radio', component_property='value')
)
def mem_response(op):
    try:
        df_mem = get_mem_metrics()
        y_max = pad_range(get_max_bar_height(df_mem))
        df_mem = trim_and_group(df_mem, op=op)
        return bar_fig(df=df_mem, op=op, y_max=y_max, title='Net Memory Usage By Version', suffix='Gb',
                       y_title='Memory (Gb)',
                       x_title='OCP Version')
    except Exception as e:
        print(f'mem_response: got exception type {type(e)}:\n{e}')


@app.callback(
    Output(component_id='cpu-graph', component_property='figure'),
    Input(component_id='cpu-op-radio', component_property='value')
)
def cpu_response(op):
    try:
        df_cpu = get_cpu_metrics()
        y_max = pad_range(get_max_bar_height(df_cpu))
        df_cpu = trim_and_group(df_cpu, op)
        return bar_fig(df_cpu, op, y_max, title='CPU % by OCP Version', suffix='%',
                       y_title='Net CPU Time in Hours', x_title='OCP Versions', legend_title='')
    except Exception as e:
        print(f'cpu_response: got exception type {type(e)}:\n{e}')


@app.callback(
    Output(component_id='mem-line', component_property='figure'),
    Input(component_id='mem-line-input', component_property='value')
)
def mem_line_response(op):
    try:
        df_mem = get_mem_metrics()
        df_mem = trim_and_group(df_mem, op)
        y_max = pad_range(df_mem['max_value'].max())
        return line_fig(df=df_mem, op=op, y_max=y_max, tick_suffix='Gb', title='Memory Trends by Version',
                        y_title='Net Memory Consumed in Gigabytes', x_title='OCP Version')
    except Exception as e:
        print(f'mem_line_response: got exception type {type(e)}:\n{e}')


@app.callback(
    Output(component_id='cpu-line', component_property='figure'),
    Input(component_id='cpu-line-input', component_property='value')
)
def cpu_line_response(op):
    try:
        df_mem = get_cpu_metrics()
        df_mem = trim_and_group(df_mem, op)
        y_max = pad_range(df_mem['max_value'].max())
        return line_fig(df=df_mem, op=op, y_max=y_max, tick_suffix='%', title='CPU % Trends by Version',
                        y_title='Net CPU Time in Hours', x_title='OCP Version')
    except Exception as e:
        print(f'cpu_line_response: got exception type {type(e)}:\n{e}')


if __name__ == '__main__':
    app.run_server(debug=True, port=8050, host='0.0.0.0')
