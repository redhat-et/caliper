import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import pandas as pd
import psycopg2
from plotly import express as px

# for debugging dataframes printed to console
pd.set_option('min_rows', 10)
pd.set_option('max_rows', 20)
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


def executeQuery(query):
    cur = conn.cursor()
    cur.execute(query)
    desc = cur.description
    columns = [col[0] for col in desc]
    rows = [row for row in cur.fetchall()]
    df = pd.DataFrame([[c for c in r] for r in rows])
    df.rename(inplace=True, columns=dict(enumerate(columns)))
    return df


def get_mem_metrics():
    query_mem = """
    SELECT * FROM collated_metrics WHERE metric = 'container_memory_usage_bytes';
    """
    return executeQuery(query_mem)


def get_cpu_metrics():
    query_cpu = """
    SELECT * FROM collated_metrics WHERE metric = 'container_cpu_usage_seconds_total';
    """
    return executeQuery(query_cpu)


def trim_and_group(df, value):
    new_df = df[['version', 'metric', 'namespace', value, 'range']].copy(deep=True)
    new_df = new_df.groupby(by=['version', 'metric', 'namespace', 'range']).agg({value: 'sum'})  # sum values of each namespace
    new_df.sort_values(by=[value], inplace=True)
    new_df.reset_index(inplace=True)
    return new_df


def get_metric():
    print()


def get_range(df=pd.DataFrame()):
    ret = df.loc[[0], ['range']].squeeze()
    return ret


def generate_mem_value_fig(df=pd.DataFrame(), op='', y_max=100):
    fig = px.bar(
        data_frame=df,
        x='version',
        y=op,
        color='namespace',
        range_y=[0, y_max]
    )
    fig.update_yaxes({
        'ticksuffix': 'Mb',
        'title': 'OCP Namespaces',
    })
    fig.update_xaxes({
        'title': 'OCP Versions'
    })
    r = get_range(df)
    fig.update_layout(
        {'title': 'Memory Usage by Namespace over {}'.format(r)}
    )
    return fig


def generate_cpu_value_fig(df=pd.DataFrame(), op=''):
    fig = px.bar(
        data_frame=df,
        x='version',
        y=op,
        color='namespace'
    )
    fig.update_yaxes({
        'ticksuffix': 'ns',
        'title': 'OCP Namespaces'
    })
    fig.update_xaxes({
        'title': 'OCP Versions'
    })
    r = get_range(df)
    fig.update_layout(
        {'title': 'CPU Usage by Namespace over {}'.format(r)}
    )
    return fig


radio_options = [
    {'label': 'Average', 'value': 'avg_value'},
    {'label': '95th-%', 'value': 'q95_value'},
    {'label': 'Min', 'value': 'min_value'},
    {'label': 'Max', 'value': 'max_value'},
    {'label': 'Instant', 'value': 'inst_value'},
]

app = dash.Dash(__name__)
app.layout = html.Div(children=[
    html.H1(children='Caliper'),
    html.Div(children=[
            dcc.Graph(id='memory-graph'),
            dcc.RadioItems(id='memory-op-radio', value='avg_value', options=radio_options),
        ]
    ),
    html.Div(children=[
        dcc.Graph(id='cpu-graph'),
        dcc.RadioItems(id='cpu-op-radio', value='avg_value', options=radio_options)
    ])
])


@app.callback(
    Output(component_id='memory-graph', component_property='figure'),
    Input(component_id='memory-op-radio', component_property='value')
)
def mem_response(op):
    df_mem = get_mem_metrics()
    df_mem = trim_and_group(df_mem, op)
    fig = generate_mem_value_fig(df_mem, op)
    return fig


@app.callback(
    Output(component_id='cpu-graph', component_property='figure'),
    Input(component_id='cpu-op-radio', component_property='value')
)
def cpu_response(op):
    df_cpu = get_cpu_metrics()
    df_cpu = trim_and_group(df_cpu, op)
    fig = generate_cpu_value_fig(df_cpu, op)
    return fig


def debug():
    op = 'avg_value'
    df_mem = get_mem_metrics()
    df_mem = trim_and_group(df_mem, op)
    fig = generate_mem_value_fig(df_mem, op)
    fig.show()


if __name__ == '__main__':
    # debug()
    app.run_server(debug=True)
