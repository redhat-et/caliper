import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import pandas as pd
import psycopg2
from plotly import express as px
from plotly import graph_objects as go
import numpy as np


# for debugging dataframes printed to console
pd.set_option('min_rows', 10)
pd.set_option('max_rows', 100)
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

    value_columns = ['avg_value', 'q95_value', 'min_value', 'max_value']
    for v in value_columns:
        df[v] = df[v].astype('float')
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


def trim_and_group(df, op='avg_value'):
    new_df = df[['version', 'metric', 'namespace', op, 'range']].copy(deep=True)
    new_df = new_df.groupby(by=['version', 'range', 'metric', 'namespace']).sum()  # sum values of each namespace
    new_df.sort_values(by=[op], inplace=True)
    new_df.reset_index(inplace=True)
    return new_df


def get_range(df=pd.DataFrame()):
    ret = df.loc[[0], ['range']].squeeze()
    return ret


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
        color='namespace',
    )
    fig.update_yaxes(
        go.layout.YAxis(
            # ticksuffix='Mb',
            # tickformat=':f',
            range=[0, y_max],
            fixedrange=True,
        ))
    fig.update_xaxes({
        'title': 'OCP Versions'
    })
    # r = get_range(df)
    fig.update_layout(
        go.Layout(
            title='Memory usage by namespace over TIME',
        )
    )
    return fig


def generate_cpu_value_fig(df=pd.DataFrame(), op='avg_value', y_max=0.0):
    fig = px.bar(
        data_frame=df,
        x='version',
        y=op,
        color='namespace'
    )
    fig.update_yaxes(go.layout.YAxis(
        ticksuffix='ns',
        title='OCP Namespaces',
        range=[0, y_max],
        fixedrange=True,
    ))
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


#
# def debug():
#     op = 'avg_value'
#     df_mem = get_mem_metrics()
#     mem_max = get_max(df_mem)
#     print(type(mem_max))
#     print("max value: \n{}".format(mem_max))
#     df_mem = trim_and_group(df_mem, op)
#     fig = generate_mem_value_fig(df=df_mem.iloc[0, 0], op=op)
#     fig.show()


if __name__ == '__main__':
    # debug()
    app.run_server(debug=True)
