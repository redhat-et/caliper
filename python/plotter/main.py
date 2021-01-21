import dash
import dash_core_components as dcc
import dash_html_components as html
import numpy
import pandas as pd
import psycopg2
import yaml
from dash.dependencies import Input, Output
from plotly import express as px
from plotly import graph_objects as go

# for debugging dataframes printed to console
pd.set_option('min_rows', 10)
pd.set_option('max_rows', 500)
pd.set_option('display.max_columns', 20)
pd.set_option('display.width', 1098)

# TODO
# grouping, Y-axis value, x-axis ordering, hard-min/max

conn = psycopg2.connect(
    host="localhost",
    port="5432",
    database="metric_data",
    user="promtop",
    password="password"
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


def get_max(df=pd.DataFrame()):
    df_summed = df.groupby(by=['version']).sum()
    m = max(df_summed.select_dtypes(include='float64').max())
    return m


def pad_range(r=0):
    return r * 1.1


def generate_mem_value_fig(df=pd.DataFrame(), op='avg_value', y_max=0.0):
    fig = px.bar(
        data_frame=df,
        x='version',
        y=op,
        color='group',
        title='OCP Memory Usage by Groupings vs OCP Version',
    )
    fig.update_yaxes(
        go.layout.YAxis(
            title='Net Memory Usage by Component: Gigabytes',
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


def generate_cpu_value_fig(df=pd.DataFrame(), op='avg_value', y_max=0.0):
    fig = px.bar(
        data_frame=df,
        x='version',
        y=op,
        color='group',
        title='CPU Usage by Time vs OCP Version'
    )
    fig.update_yaxes(go.layout.YAxis(
        ticksuffix='hrs',
        title='Net CPU Time by Component in Hours',
        range=[0, y_max],
        fixedrange=True,
    ))
    fig.update_xaxes({
        'title': 'OCP Versions'
    })
    fig.update_layout(
        {
            'legend': {
                'traceorder': 'reversed',
            },
        }
    )
    return fig


def generate_mem_line(df=pd.DataFrame()):
    fig = go.Figure()
    fig.update_layout(go.Layout(
        title='95th Quantile of Memory Usage Trends by Version',
        legend=go.layout.Legend(
            traceorder='grouped+reversed',
        )
    ))
    fig.update_xaxes(go.layout.XAxis(
        title='OCP Version'
    ))
    fig.update_yaxes(go.layout.YAxis(
        title='Net Memory Consumed by Component in Gigabytes',
        ticksuffix='Gb'
    ))

    groups = df.groupby(by='group', sort=True)
    for n, g in groups:
        g.sort_values(by='q95_value', ascending=False)
    for name, g in groups:
        fig.add_trace(
            go.Scatter(
                name=name,
                x=g['version'],
                y=g['q95_value'],
                legendgroup=1,
            )
        )

    return fig


radio_options = [
    {'label': 'Average', 'value': 'avg_value'},
    {'label': '95th-%', 'value': 'q95_value'},
    {'label': 'Min', 'value': 'min_value'},
    {'label': 'Max', 'value': 'max_value'},
]

app = dash.Dash(__name__)
app.layout = html.Div(children=[
    html.H1(children='Caliper'),
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
        dcc.Input(id='mem-line-input', value='q95_value', type='hidden', )
    ])
])


@app.callback(
    Output(component_id='memory-graph', component_property='figure'),
    Input(component_id='memory-op-radio', component_property='value')
)
def mem_response(op):
    df_mem = get_mem_metrics()
    y_max = pad_range(get_max(df_mem))
    df_mem = trim_and_group(df_mem, op=op)
    return generate_mem_value_fig(df_mem, op=op, y_max=y_max)


@app.callback(
    Output(component_id='cpu-graph', component_property='figure'),
    Input(component_id='cpu-op-radio', component_property='value')
)
def cpu_response(op):
    df_cpu = get_cpu_metrics()
    y_max = pad_range(get_max(df_cpu))
    df_cpu = trim_and_group(df_cpu, op)
    return generate_cpu_value_fig(df_cpu, op, y_max)


@app.callback(
    Output(component_id='mem-line', component_property='figure'),
    Input(component_id='mem-line-input', component_property='value')
)
def mem_line_response(op):
    df_mem = get_mem_metrics()
    df_mem = trim_and_group(df_mem, op)
    return generate_mem_line(df_mem)


def debug():
    op = 'avg_value'
    df_mem = get_mem_metrics()
    mem_max = pad_range(get_max(df_mem))
    df_mem = trim_and_group(df_mem, op)
    fig = generate_mem_value_fig(df=df_mem, op=op, y_max=mem_max)
    fig.show()


if __name__ == '__main__':
    # debug()
    app.run_server(debug=True)
