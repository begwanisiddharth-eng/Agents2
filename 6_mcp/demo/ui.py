import gradio as gr
from demo.util import Color
import pandas as pd
from backend.trading_floor import Names, LastNames, ShortModelNames
import plotly.express as px
from backend.accounts import Account
from backend.database import ReadLog


Mapper = {
    "trace": Color.WHITE,
    "agent": Color.CYAN,
    "function": Color.GREEN,
    "generation": Color.YELLOW,
    "response": Color.MAGENTA,
    "account": Color.RED
}

class Trader:
    def __init__(self, Name:str, LastName: str, ModelName: str):
        self.Name = Name
        self.LastName = LastName
        self.ModelName = ModelName
        self.account = Account.Get(Name)

    def Reload(self):
        self.account = Account.Get(self.Name)

    def GetTitle(self) -> str:
        return f"<div style='text-align: center; font-size: 34px;'>{self.Name}<span style='color:#ccc; font-size:24px;'> ({self.ModelName}) - {self.LastName}</span></div>"

    def GetStrategy(self) -> str:
        return self.account.GetStrategy()

    def GetPortfolioValueDf(self) -> pd.DataFrame:
        df = pd.DataFrame(self.account.portfolio_value_time_series, columns = ["DateTime", "Value"])
        df["DateTime"] = pd.to_datetime(df["DateTime"])
        return df

    def GetPortfolioValueChart(self):
        Df = self.GetPortfolioValueDf()
        Fig = px.line(Df, x="DateTime", y="Value")
        Margin = dict[str,int](l=40, r=20, t=20, b=40)
        Fig.update_layout(
            height=300,
            margin=Margin,
            xaxis_title=None,
            yaxis_title=None,
            paper_bgcolor="#bbb",
            plot_bgcolor = "#dde"
        )
        Fig.update_xaxes(tickformat="%m/%d",tickangle=45, tickfont=dict(size=8))
        Fig.update_yaxes(tickfont=dict(size=8), tickformat=",.0f")
        return Fig

    def GetHoldingsDf(self) -> pd.DataFrame:
        """Convert holdings to DataFrame for display"""
        Holdings = self.account.GetHoldings()
        if not Holdings:
            return pd.DataFrame(columns=["Symbol","Quantity"])
        df = pd.DataFrame(
            [{"Symbol":Symbol, "Quantity": Quantity} for Symbol, Quantity in Holdings.items()]
        )
        return df

    def GetTransactionsDf(self) -> pd.DataFrame:
        """Convert transactions to DataFrame for display"""
        Transactions = self.account.ListTransactions()
        if not Transactions:
            return pd.DataFrame(columns=["Timestamp", "Symbol", "Quantity", "Price", "Rationale"])
        return pd.DataFrame(Transactions)

    def GetPortfolioValue(self) -> str:
        """Calculate total portfolio value based on current prices"""
        PortfolioValue = self.account.CalculatePortfolioValue() or 0.0
        PnL = self.account.CalculateProfitLoss(PortfolioValue) or 0.0
        Color = "green" if PnL >=0 else "red"
        Sign = "+" if PnL >=0 else "-"
        return f"<div style='text-align: center;background-color:{Color};'><span style='font-size:32px'>Rs.{PortfolioValue:,.0f}</span><span style='font-size:24px'>&nbsp;&nbsp;&nbsp;{Sign}Rs.{abs(PnL):,.0f}</span></div>"

    def GetLogs(self, Previous=None) -> str:
        Logs = ReadLog(self.Name,LastN=13)
        Response = ""
        for Log in Logs:
            Timestamp, Type, Message = Log
            color = Mapper.get(Type, Color.WHITE).value
            Response += f"<span style='color:{color}'>{Timestamp} : [{Type}] {Message}</span><br/>"
        Response = f"<div style='height:250px; overflow-y:auto;'>{Response}</div>"
        if Response != Previous:
            return Response
        return gr.update()

class TraderView:
    def __init__(self, trader:Trader):
        self.trader=trader
        self.PortfolioValue = None
        self.Chart = None
        self.HoldingsTable = None
        self.TransactionsTable = None

    def MakeUI(self):
        with gr.Column():
            gr.HTML(self.trader.GetTitle())
            with gr.Row():
                self.PortfolioValue = gr.HTML(self.trader.GetPortfolioValue)
            with gr.Row():
                self.Chart = gr.Plot(
                    self.trader.GetPortfolioValueChart, container=True, show_label=False
                )
            with gr.Row(variant="panel"):
                self.Log = gr.HTML(self.trader.GetLogs)
            with gr.Row():
                self.HoldingsTable = gr.DataFrame(
                    value = self.trader.GetHoldingsDf,
                    label = "Holdings",
                    headers = ["Symbol","Quantity"],
                    row_count=5,
                    column_count=2,
                    max_height=300,
                    elem_classes=["dataframe-fix-small"]
                )
            with gr.Row():
                self.TransactionsTable = gr.DataFrame(
                    value = self.trader.GetTransactionsDf,
                    label = "Recent Transactions",
                    headers = ["Timestamp", "Symbol", "Quantity", "Price", "Rationale"],
                    row_count = 5,
                    column_count = 5,
                    max_height = 300,
                    elem_classes = ["dataframe-fix"]
                )
        Timer = gr.Timer(value=60)
        Timer.tick(
            fn = self.Refresh,
            inputs = [],
            outputs = [
                self.PortfolioValue,
                self.Chart,
                self.HoldingsTable,
                self.TransactionsTable
            ],
            show_progress = "hidden",
            queue = False
        )
        LogTimer = gr.Timer(value=0.5)
        LogTimer.tick(
            fn = self.trader.GetLogs,
            inputs = [self.Log],
            outputs = [self.Log],
            show_progress = "hidden",
            queue=False
        )


    def Refresh(self):
        self.trader.Reload()
        return (
            self.trader.GetPortfolioValue(),
            self.trader.GetPortfolioValueChart(),
            self.trader.GetHoldingsDf(),
            self.trader.GetTransactionsDf()
        )
    
## Main UI construction
##
## MakeUI() has no return statement, and CreateUI() never collects anything from it, yet the UI still
## gets built. That works because every Gradio component registers itself the moment it is constructed,
## as a side effect of its own __init__, rather than being returned and assembled by the caller.
##
## `with gr.Blocks(...) as UI:` below opens the root context and makes UI the currently-active Blocks.
## For each trader, traderView.MakeUI() is then called while still inside that with block. Inside
## MakeUI(), every gr.Column(), gr.Row(), gr.HTML(...), gr.Plot(...) and gr.DataFrame(...) it constructs
## sees that the root context is still UI, since Python has not exited the `with gr.Blocks(...)` block -
## it is just deeper in the call stack - so each one wires itself into UI's component tree the instant
## it is created.
##
## Once every MakeUI() call has finished and the with block exits, UI already contains everything.
## `return UI` at the end just hands back the object that was silently accumulating components the
## whole time; it does not assemble anything itself.
def CreateUI():
    """Create the main Gradio UI for the trading simulation"""

    traders = [
        Trader(TraderName, LastName, ModelName)
        for TraderName, LastName, ModelName in zip(Names,LastNames,ShortModelNames)
    ]
    traderViews = [TraderView(trader) for trader in traders]

    with gr.Blocks(title="Traders", fill_width=True) as UI:
        with gr.Row():
            for traderView in traderViews:
                traderView.MakeUI()

    return UI

