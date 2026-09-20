from pydantic import BaseModel
import json
from dotenv import load_dotenv
from datetime import datetime
from .market import GetSharePrice
from .database import WriteAccount, ReadAccount, WriteLog

load_dotenv(override=True)

InitialBalance = 1000000.0
Spread = 0.002

class Transaction (BaseModel):
    symbol: str
    quantity: int
    price: float
    timestamp: str
    rationale: str

    def Total(self) -> float:
        return self.quantity*self.price
    
    def __repr__(self):
        return f"{abs(self.quantity)} shares of {self.symbol} at {self.price} each"

class Account(BaseModel):
    name: str
    balance: float
    strategy: str
    holdings: dict[str,int]
    transactions: list[Transaction]
    portfolio_value_time_series: list[tuple[str,float]]

    @classmethod
    def Get(cls, Name: str):
        ## cls is the class itself, the way self is the instance. 
        ## It is a naming convention, and Python fills it in automatically for methods decorated with @classmethod
        ## When you call Account.Get("Warren"), Python passes Account (the class, not an object) as cls. 
        ## So cls(**Fields) means exactly Account(**Fields). In this implementation, it functions as an alternative
        ## constructor for Account
        Fields = ReadAccount(Name.lower())
        if not Fields:
            Fields = {
                "name": Name.lower(),
                "balance": InitialBalance,
                "strategy": "",
                "holdings": {},
                "transactions": [],
                "portfolio_value_time_series": []
            }
            WriteAccount(Name, Fields)
        return cls(**Fields)

    def Save(self):
        WriteAccount(self.name.lower(), self.model_dump())
        ## self.model_dump() returns a new plain Python dict of the BaseModel's fields. The keys are
        ## the field names and the values are the field values. Changing the dict does not change
        ## the class instance. If a value is itself a BaseModel instance, it is also converted to a dict.
        ## For instance, transactions in Account is a list of Transaction objects, and it becomes
        ## a list of dicts, one per Transaction. Other types stay as Python types, so
        ## portfolio_value_time_series stays a list of tuples. Methods are ignored, only fields
        ## are included. An example of the output:
        ## {'name': 'warren', 'balance': 973500.0, 'strategy': 'value', 'holdings': {'HEROMOTOCO': 5},
        ##  'transactions': [{'symbol': 'HEROMOTOCO', 'quantity': 5, 'price': 5300.0,
        ##                    'timestamp': '2026-09-19 10:00:00', 'rationale': 'cheap'}],
        ##  'portfolio_value_time_series': [('2026-09-19 10:00:00', 1000000.0)]}
        ## JSON does not have a tuple type, and hence tuples get converted into lists
        ## Therefore, json.dumps on the model_dump output above gives a long text string:
        ## {"name": "warren", "balance": 973500.0, "strategy": "value", "holdings": {"HEROMOTOCO": 5}, "transactions": [{"symbol": "HEROMOTOCO", "quantity": 5, "price": 5300.0, "timestamp": "2026-09-19 10:00:00", "rationale": "cheap"}], "portfolio_value_time_series": [["2026-09-19 10:00:00", 1000000.0]]}
        ## json.dumps also converts single-quotation marks into double quotation marks
        ## Running json.loads on that string gives a dict back, but the inner item is now a list, not a tuple. 
        ## It doesn't matter here, because cls(**Fields) which is equivalent to Account(**Fields) rebuilds the model, 
        ## and Pydantic converts that inner list back into a tuple to match list[tuple[str, float]].

    def Reset(self, Strategy: str=""):
        self.balance = InitialBalance
        self.strategy = Strategy
        self.holdings = {}
        self.transactions = []
        self.portfolio_value_time_series = []
        self.Save()

    def Deposit(self, Amount: float):
        """ Deposit funds into the account. """
        if Amount <=0:
            raise ValueError("Deposit amount must be positive")
        self.balance +=Amount
        print (f"Deposited Rs.{Amount}. New balance: Rs.{self.balance}")
        self.Save()

    def Withdraw(self, Amount:float):
        """Withdraw funds from the account, ensuring it doesn't go negative"""
        if Amount > self.balance:
            raise ValueError("Insufficient funds for withdrawal")
        if Amount <=0:
            raise ValueError("Withdrawal must be positive")
        self.balance -=Amount
        print (f"Withdrew Rs.{Amount}. New balance: Rs.{self.balance}")
        self.Save()

    def BuyShares(self, Symbol: str, Quantity: int, Rationale: str) -> str:
        """Buy shares of a stock if sufficient funds are available"""
        if Quantity <= 0:
            raise ValueError("Quantity must be positive")
        Price = GetSharePrice(Symbol) ## Will raise an error if there is a Tapetide token and the symbol is not recognized, and the code will not proceed
        BuyPrice = Price *(1+Spread)
        TotalCost = BuyPrice * Quantity

        if TotalCost > self.balance:
            raise ValueError("Insufficient funds to buy shares")

        ## Update holdings
        self.holdings[Symbol] = self.holdings.get(Symbol,0) + Quantity
        Timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ## Record transaction
        transaction = Transaction(symbol=Symbol,quantity=Quantity,price=BuyPrice,timestamp=Timestamp,rationale=Rationale)
        self.transactions.append(transaction)
        ## Update balance
        self.balance -= TotalCost
        self.Save()
        WriteLog(self.name, "account", f"Bought {Quantity} of {Symbol}")
        return "Completed. Latest details:\n" + self.Report()

    def SellShares(self, Symbol: str, Quantity: int, Rationale: str) -> str:
        """Sell shares of a stock if the user has enough shares"""
        if Quantity <= 0:
            raise ValueError("Quantity must be positive")
        ## no change needed here for checking whether a symbol exists. A symbol that is not held, including an unknown one,
        ## is rejected by the check below before any price lookup. So GetSharePrice is only called for symbols we hold.
        if self.holdings.get(Symbol, 0) < Quantity:
            raise ValueError(f"Cannot sell {Quantity} shares of {Symbol}. Not enough shares held.")
        Price = GetSharePrice(Symbol)
        SellPrice = Price * (1-Spread)
        TotalProceeds = SellPrice * Quantity

        ## Update holdings and delete symbol if quantity has become 0
        self.holdings[Symbol] -= Quantity
        if self.holdings[Symbol] == 0:
            del self.holdings[Symbol]
        ## Update transactions
        Timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        transaction = Transaction(symbol=Symbol,quantity=-Quantity,price=SellPrice,timestamp=Timestamp,rationale=Rationale) 
        ## Negative quantity for sales
        self.transactions.append(transaction)
        ## Update balance
        self.balance += TotalProceeds
        self.Save()
        WriteLog(self.name, "account", f"Sold {Quantity} of {Symbol}")
        return "Completed. Latest details:\n" + self.Report()

    def CalculatePortfolioValue(self):
        """Calculate the total value of the user's portfolio"""
        TotalValue = self.balance
        for Symbol, Quantity in self.holdings.items():
            TotalValue += Quantity * GetSharePrice(Symbol)
        return TotalValue

    def CalculateProfitLoss(self, PortfolioValue: float):
        """ Calculate profit or loss from the initial spend 
        The profit and loss emerges entirely from buying and selling of shares, i.e.
        the current Stock portfolio value - what was spent in building the stock portfolio
        There is no interest on the deposits"""
        CurrentValue = PortfolioValue
        SpendOnShares = sum(Trade.Total() for Trade in self.transactions)
        return CurrentValue - SpendOnShares - self.balance ## since PortfolioValue contains the balance as well

    def GetHoldings(self):
        """Report the current holdings of the user"""
        return self.holdings

    def GetProfitLoss(self):
        """Report the user's profit or loss at any given point in time"""
        return self.CalculateProfitLoss(PortfolioValue = self.CalculatePortfolioValue())

    def ListTransactions(self):
        """List all transactions made by the user"""
        return [Trade.model_dump() for Trade in self.transactions]

    def Report (self) -> str:
        """ Return a json string representing the account """
        PortfolioValue = self.CalculatePortfolioValue()
        self.portfolio_value_time_series.append((datetime.now().strftime("%Y-%m-%d %H:%M:%S"), PortfolioValue))
        self.Save()
        PnL = self.CalculateProfitLoss(PortfolioValue = PortfolioValue)
        Data = self.model_dump()
        Data["total_portfolio_value"] = PortfolioValue ## A key is added to the model_dump above. Does not affect the Account instance
        Data["total_profit_loss"] = PnL ## A key is added to the model_dump above. Does not affect the Account instance
        WriteLog(self.name, "account", "Retrieved account details")
        return json.dumps(Data)

    def GetStrategy(self) -> str:
        """Return the strategy of the account"""
        WriteLog(self.name, "account", "Retrieved strategy")
        return self.strategy

    def ChangeStrategy(self, Strategy: str) -> str:
        """At your discretion, if you choose to, call this to change your investment strategy for the future"""
        self.strategy = Strategy
        self.Save()
        WriteLog(self.name, "account", "Changed strategy")
        return "Changed strategy"
