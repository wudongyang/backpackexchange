# 简单的网格交易代码
# 参考：https://juejin.cn/post/7182780998176735292
from bpx import BpxClient
import bpx_pub
import time

MAX_IDLE_TIME = 20

# 调用 backpack 的 api，实现网格交易，暂时 SOL_USDC 是写死的
class GridClient:
    
    def __init__(self):
        self.debug = True
        # 循环间隔时间
        self.loopSleepTime = 1
        # 长时间不买卖就说明超出网格太久，则应该重新考虑网格
        self.idleTime = MAX_IDLE_TIME
        self.symbol = "SOL_USDC"
        # 网格数量，默认 10
        self.num_space = 10 
        
    def get_last_price(self):
        ticker = bpx_pub.Ticker(self.symbol)
        lastPrice = ticker['lastPrice']

        # if self.debug:
        #     print("lastPrice", lastPrice)

        return float(lastPrice)
        
    def orderQueryAll(self):
        return self.client.orderQueryAll(self.symbol)

    def cancelAllOrders(self):
        return self.client.cancelAllOrders(self.symbol)

    def buy(self, sol_quantity, buy_price):
        if self.debug:
            print("buy: ", sol_quantity, buy_price)
        # return self.client.ExeOrder("SOL_USDC", "Bid", "Limit", "GTC", str(sol_quantity), buy_price)
        return self.client.ExeLimitOrder(self.symbol, "Bid", "GTC", str(sol_quantity), buy_price)

    def sell(self, sol_quantity, sell_price):
        if self.debug:
            print("sell: ", sol_quantity, sell_price)
        # return self.client.ExeOrder("SOL_USDC", "Ask", "Limit", "GTC", str(sol_quantity), sell_price)
        return self.client.ExeLimitOrder(self.symbol, "Ask", "GTC", str(sol_quantity), sell_price)

    def resetInitPrice(self):
        self.idleTime = MAX_IDLE_TIME
        # 取消所有订单
        req = self.cancelAllOrders()
        # 重新设置策略运行初始价格
        old_price = self.init_price
        self.init_price = self.get_last_price()
        self.pos_pair.clear()
        if self.debug:
            print("req:", req)
            print("resetInitPrice:", self.init_price)

        balance = self.client.balances()
        sol_balance = balance['SOL']['available']
        usdc_balance = balance['USDC']['available']

        if self.debug:
            print("sol_balance", sol_balance)

        balance_not_order = float(sol_balance)

        if self.debug:
            print("balance_not_order", balance_not_order)
        i = 0
        while balance_not_order > float(self.buy_amount):
            self.pos_pair[i-1] = self.buy_amount
            i = i - 1
            balance_not_order = balance_not_order - float(self.buy_amount)

            if self.debug:
                print("balance_not_order", balance_not_order)
        
        if self.debug:
            print(self.pos_pair)


    def init(self, symbol, netSpace, buyAmount, apiKey, apiSecret):
        self.symbol = symbol
        # 价格间隔 0.1美元
        self.net_space = netSpace
        # 买入的数量
        self.buy_amount = buyAmount

        # 初始化 BpxClient
        self.client = BpxClient()
        self.client.init(apiKey, apiSecret)

        # 策略运行初始价格
        self.init_price = self.get_last_price()
        # self.init_price = 120
        # 当前价格
        self.price = self.init_price
        # 仓位状态字典
        self.pos_pair = dict()
        # 订单状态字典
        self.order_pair = dict()

    def update_pos_pair(self):
        orders = self.client.orderQueryAll(self.symbol)
        # 遍历 orders，并根据 price 计算在 pos_pair 中的位置，根据位置设置 pos_pair 的值
        for order in orders:
            price = order.get("price")
            if price is not None:
                line = int((float(price) - self.init_price) / self.net_space)
                self.pos_pair[line] = order.get("quantity")
                self.order_pair[line] = {
                     'price': order['price'],
                     'id': order['id'],
                     'quantity': order['quantity'],
                     'side': order['side'],
                     'status': order['status']
                     }
        print(self.pos_pair)
        print(self.order_pair)

    
    

    def run_grid_strategy(self):
        self.pos_pair.clear()
        # 根据现有的 order，设置 pos_pair
        self.update_pos_pair()
        # 无限循环
        while True:
            # 当前价格所在网格线
            line = int((self.price - self.init_price) / self.net_space)
            if self.debug:
                print("line:", line, self.price, self.init_price, self.idleTime)
            
            balance = self.client.balances()
            sol_balance = balance['SOL']['available']
            usdc_balance = balance['USDC']['available']

            try:
                # 如果下面那根网格线持有仓位，则优先进行平仓操作
                if self.pos_pair.get(line-1) is not None:
                    # 卖出
                    if self.debug:
                        print(" 卖出 ", line-1, self.pos_pair[line-1], self.price)
                    if float(sol_balance) > float(self.buy_amount):
                        if self.sell(self.buy_amount, self.price):    
                            # 仓位状态设置为空
                            self.pos_pair[line-1] = None
                    else:
                        self.idleTime -= 1

                        if self.debug:
                            print(" SOL 余额不足")
                elif self.pos_pair.get(line) is None:
                    # 如果当前网格线没有仓位，则进行开仓操作
                    # 买入
                    if self.debug:
                        print(" 买入 ", line, self.buy_amount, self.price)
                    if float(usdc_balance) >= (float(self.buy_amount) * float(self.price)):
                        if self.buy(self.buy_amount, self.price):
                            # 仓位状态设置为非空
                            self.pos_pair[line] = self.buy_amount
                    else:
                        self.idleTime -= 1

                        if self.debug:
                            print(" USDC 余额不足")
                
                # 更新当前价格
                self.price = self.get_last_price()

                if self.idleTime <= 0:
                    self.resetInitPrice()
            
                # 异常处理
            except Exception as e:
                print(e) 
            # 程序休息指定时间
            time.sleep(self.loopSleepTime)
    
# 程序入口
if __name__ == '__main__':
    API_KEY = "="
    API_SECRET = "="
    
    # 间隔 0.1 u
    netSpace = 0.1 
    # 每个网格交易 0.2 sol
    buyAmount = 0.2

    gridClient = GridClient()
    
    gridClient.init("SOL_USDC", netSpace, buyAmount, API_KEY, API_SECRET)
    gridClient.run_grid_strategy()
    # gridClient.sell(buyAmount, 113.33)
    # gridClient.cancelAllOrders()
    # gridClient.update_pos_pair()
    
