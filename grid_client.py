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
        self.net_count = 10 
        
    def get_last_price(self):
        ticker = bpx_pub.Ticker(self.symbol)
        lastPrice = ticker['lastPrice']

        # if self.debug:
        #     print("lastPrice", lastPrice)

        return float(lastPrice)
        
    def fillHistoryQuery(self, symbol, limit, offset):
        return self.client.fillHistoryQuery(symbol, limit, offset)

    def orderQuery(self, orderId):
        return self.client.orderQuery(self.symbol, orderId)

    def orderQueryAll(self):
        return self.client.orderQueryAll(self.symbol)

    def cancelAllOrders(self):
        return self.client.cancelAllOrders(self.symbol)

    def cancelOrder(self, orderId):
        # if self.debug:
        #     print("cancelOrder: ", orderId)
        return self.client.cancelOrder(self.symbol, orderId)

    def buy(self, sol_quantity, buy_price):
        # if self.debug:
        #     print("buy: ", sol_quantity, buy_price)
        # return self.client.ExeOrder("SOL_USDC", "Bid", "Limit", "GTC", str(sol_quantity), buy_price)
        return self.client.ExeLimitOrder(self.symbol, "Bid", "GTC", str(sol_quantity), buy_price)

    def sell(self, sol_quantity, sell_price):
        # if self.debug:
        #     print("sell: ", sol_quantity, sell_price)
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
        wen_balance = balance['WEN']['available']
        usdc_balance = balance['USDC']['available']

        if self.debug:
            print("sol_balance", sol_balance)
            print("wen_balance", wen_balance)

        if self.symbol == "SOL_USDC":
            balance_not_order = float(sol_balance)
        elif self.symbol == "WEN_USDC":
            balance_not_order = float(wen_balance)

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


    def init(self, symbol, netCount, netSpace, buyAmount, apiKey, apiSecret):
        self.symbol = symbol
        # 网格数
        self.net_count = netCount
        # 价格间隔 0.1美元
        self.net_space = netSpace
        # 买入的数量
        self.buy_amount = buyAmount

        # 初始化 BpxClient
        self.client = BpxClient()
        self.client.init(apiKey, apiSecret)

        # 策略运行初始价格
        self.init_price = self.get_last_price()
        if self.debug:
            print("init_price:", self.init_price)
        # self.init_price = 120
        # 当前价格
        self.price = self.init_price
        # 仓位状态字典
        self.pos_pair = dict()
        # 订单状态字典
        self.order_pair = dict()
        # 网格状态字典
        self.grids = dict()

    def keep_two_digits(self, num_str):
        keepNum = 2
        if (self.symbol != "SOL_USDC"):
            keepNum = 8
        dot_index = num_str.find('.')
        if dot_index != -1:
            return num_str[:dot_index+keepNum+1]
        else:
            return num_str
    
    def getLine(self, price):
        fline = ((price - self.init_price) / self.net_space) + (self.net_count / 2) 
        iline = int(fline)
        return iline

    # 初始化网格
    def init_grids(self):
        self.grids.clear()
        for i in range(self.net_count):
            price = self.keep_two_digits(str(self.init_price + i * self.net_space - int(self.net_count / 2) * self.net_space))
            self.grids[i] = {
                'grid_price': price,
                'price': price,
                'quantity': 0,
                'status': 'idle',
                'side': '',
                'id': ''
            }
            # self.grids[i] = None
        self.update_grids()

    def reset_grid(self, line):
        self.grids[line]["status"] = "idle"
        self.grids[line]["side"] = ""
        self.grids[line]["id"] = ""
        self.grids[line]["quantity"] = 0
        
    # 更新网格，根据 orders 的值，设置 grids 的值，已经存在的 grids 不会被覆盖
    def update_grids(self):
        print("--- update_grids --- ")
        # 获取 balance
        balance = self.client.balances()
        self.sol_balance = float(balance['SOL']['available'])
        self.wen_balance = float(balance['WEN']['available'])
        self.usdc_balance = float(balance['USDC']['available'])

        # 遍历网格存在的 orderid，如果获取不到说明该网格已成交或者取消
        for i in range(self.net_count):
            # 如果没有 orderid，则说明已经成交
            orderid = self.grids[i]["id"]
            if orderid != "":
                req = self.orderQuery(orderid)
                # print("update_grids", orderid, req)
                if(not req):
                    # 如果是买单成交，则应该挂卖单
                    if self.grids[i]["side"] == 'Bid':
                        # self.sell(self.buy_amount, self.grids[i]["grid_price"])
                        if self.debug:
                            print(" ------ 买单成交，挂高一级的卖单 ", i, self.grids[i]["grid_price"], self.now_time())
                        # 注意要挂高一级的卖单
                        self.grid_sell(i+1)
                        # 重置当前网格买单状态
                        self.reset_grid(i) 
                    # 如果是卖单成交，则应该将卖单设置为 idle，表示可以重新买入
                    elif self.grids[i]["side"] == 'Ask':
                        self.grids[i]["status"] = "idle"
                        self.grids[i-1]["status"] = "idle"
                        self.reset_grid(i) 

        orders = self.client.orderQueryAll(self.symbol)
        # 遍历 orders，并根据 price 计算在 grids 中的位置，根据位置设置 grids 的值
        for order in orders:
            price = float(self.keep_two_digits(str(order.get("price"))))
            if price is not None:
                line = self.getLine(price)
                # print("update_grids", line, price)
                if line >= 0 and line < self.net_count:
                    self.grids[line]["price"] = price
                    self.grids[line]["id"] = order['id']
                    self.grids[line]["quantity"] = order['quantity']
                    self.grids[line]["side"] = order['side']
                    self.grids[line]["status"] = order['status']

    # def check_grids(self):
    #     for i in range(self.net_count):
    #         if self.grids[i] is not None:
    #             if self.grids[i]["status"] == 'Filled':
    #                 # 如果是买单完成，则自动设置卖单
    #                 if self.grids[i]["side"] == 'Bid':
    #                     if self.sell(self.buy_amount, self.grids[i+1]["grid_price"]):
    #                         self.grids[i+1]["quantity"] = self.buy_amount
    #                         self.grids[i+1]["side"] = "Ask"
    #                         self.grids[i+1]["status"] = "new"
    #                 elif self.grids[i]["side"] == 'Ask': # 如果是卖单完成，则自动将买单设置为 none，表示可以重新买入
    #                     self.grids[i] = None
    #                     self.grids[i-1] = None
                        

    def now_time(self):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    # 取消比 price 低的，最低的买单
    def cancel_lowest_buy_order(self, price):
        # print("cancel_lowest_buy_order", price)
        for i in range(self.net_count):
            if self.grids[i] is not None:
                if self.grids[i]["side"] == 'Bid' and self.grids[i]["status"] == 'New':
                    if float(self.grids[i]["grid_price"]) < price:
                        if self.debug:
                            print(" ------ 取消买单 ", self.now_time(),i, self.price, self.grids[i])
                        req = self.cancelOrder(self.grids[i]["id"])
                        if req:
                            self.reset_grid(i)
                        # print("cancel_lowest_buy_order", req)
                        return True
        return False

    # 取消比 price 高的，最高的卖单,如果有取消的订单，则返回 True，否则返回 False
    def cancel_hightest_sell_order(self, price):
        # print("cancel_hightest_sell_order", price)
        for i in range(self.net_count - 1, -1, -1):
            if self.grids[i] is not None:
                if self.grids[i]["side"] == 'Ask' and self.grids[i]["status"] == 'New':
                    if float(self.grids[i]["grid_price"]) > price:
                        if self.debug:
                            print(" ------ 取消卖单", self.now_time(),i, self.price, self.grids[i])
                        req = self.cancelOrder(self.grids[i]["id"])
                        if req:
                            self.reset_grid(i)
                        # print("cancel_hightest_sell_order", req)
                        return True
        return False

    # 网格买入
    def grid_buy(self, line):
        # 判断网格上一个网格是否有卖单，如果有，则不进行买入
        if self.grids[line+1] is not None and self.grids[line+1]["side"] == 'Ask' and self.grids[line+1]["status"] == 'New':
            print(" ------ 上一个网格有卖单，不进行买入 ", self.now_time(), line, self.price, self.grids[line+1])
            return

        if(self.usdc_balance < self.buy_amount * float(self.grids[line]["grid_price"])):
            print(" USDC 余额不足，尝试取消低价买单 ", (self.grids[line]["grid_price"]))
            # 取消最低的买单,这样可能会有钱买当前价格的
            if(self.cancel_lowest_buy_order(float(self.grids[line]["grid_price"]))):
                # 休息一秒，等待执行完成
                time.sleep(1)

        price = float(self.grids[line]["grid_price"])
        if price > self.price:
            price = self.price
        # print("grid_buy:", line, self.buy_amount, price, self.now_time())
        if self.buy(self.buy_amount, price): 
            self.grids[line]["quantity"] = self.buy_amount
            self.grids[line]["side"] = "Bid"
            self.grids[line]["status"] = "New"
        else:
            self.idleTime -= 1
            # if self.debug:
            #     print(" USDC 余额不足", usdc_balance, self.buy_amount * float(self.grids[line]["grid_price"]), self.now_time())

    def grid_sell(self, line):

        if self.symbol == "SOL_USDC":
            if(self.sol_balance < self.buy_amount):
                print(" SOL 余额不足，尝试取消高价卖单", self.sol_balance, self.buy_amount)
                # 卖单，不考虑 sole 不足，取消最高的卖单的方式
                # if(self.cancel_hightest_sell_order(float(self.grids[line]["grid_price"]))):
                #     # 休息一秒，等待执行完成
                #     time.sleep(1)
                return
        elif self.symbol == "WEN_USDC":
            if(self.wen_balance < self.buy_amount):
                print(" WEN 余额不足，尝试取消高价卖单", self.sol_balance, self.buy_amount)
                return

        price = float(self.grids[line]["grid_price"])
        if price < self.price:
            price = self.price
        
        print("grid_sell:", line, self.buy_amount, price, self.now_time())

        if self.sell(self.buy_amount, price): 
            self.grids[line]["price"] = price
            self.grids[line]["quantity"] = self.buy_amount
            self.grids[line]["side"] = "Ask"
            self.grids[line]["status"] = "New"
        else:
            self.idleTime -= 1
            # if self.debug:
            #     print(" SOL 余额不足", self.now_time())

    def run_grid_strategy_v2(self):
        # 初始化网格状态
        self.init_grids()
        # 取消所有 orders
        # self.cancelAllOrders()
        first = True

        while True:

            try:
                # 更新当前价格以及新的网格位置
                self.price = self.get_last_price()

                line = self.getLine(self.price)

                print("----------------------------- start ", self.price, line, " -----------------------------" , self.now_time())

                self.update_grids()

                # 遍历 grids，打印 grids 的值
                if self.debug:
                    for i in range(self.net_count):
                        print(i, self.grids[i])
                        
                # # 保存旧价格以及旧的网格位置
                # old_price = self.price
                # oldLine = self.getLine(self.price)

                # if self.debug:
                #     # 打印当前时间和网格内容
                #     print(self.now_time(), "当前网格 ", line, self.price, self.init_price)

                # 遍历下面的网格，如果没有买入，则设置成买入
                for i in range(line-1, -1, -1):
                    if self.grids[i] is not None:
                        if self.grids[i]["status"] == 'idle':
                            # if self.debug:
                            #     print(" 应挂买单 ",i, self.price, self.grids[i], self.now_time())
                            self.grid_buy(i)
                        elif self.grids[i]["status"] == 'New':
                            if self.grids[i]["side"] == 'Ask':
                                # if self.debug:
                                #     print(" 卖单取消 ",i, self.price, self.grids[i], self.now_time())
                                self.cancelOrder(self.grids[i]["id"])
                            elif self.grids[i]["side"] == 'Bid':
                                if False and self.debug:
                                    print(" 已经挂单 ",i, self.price, self.grids[i], self.now_time())
                    else:
                        if self.debug:
                            print(" grids is null ", self.now_time(), i)

                # 卖单暂时只靠买单成交后挂卖单
                # for i in range(line+1, self.net_count):
                #     if self.grids[i] is not None:
                #         if self.grids[i]["status"] == 'idle':
                #             # if self.debug:
                #             #     print(" 无卖单应该卖出 ", self.now_time(),i, self.price, self.grids[i])
                #             self.grid_sell(i)
                #         elif self.grids[i]["status"] == 'New':
                #             if self.grids[i]["side"] == 'Bid':
                #                 # if self.debug:
                #                 #     print(" 卖单单应该取消 ", self.now_time(),i, self.price, self.grids[i])
                #                 self.cancelOrder(self.grids[i]["id"])
                #             elif self.grids[i]["side"] == 'Ask':
                #                 if False and self.debug:
                #                     print(" 已经挂单 ", self.now_time(),i, self.price, self.grids[i])
                #     else:
                #         if self.debug:
                #             print(" grids is null ",  self.now_time(), i)
            # 异常处理
            except Exception as e:
                print(e, end=" ") 

            # 长时间出现买不了、卖不掉，表示已经超过的网格太久，则应该重新考虑网格
            if self.idleTime <= 0:
                # self.resetInitPrice()
                print("idleTime is 0")
        
                print("----------------------------- end -----------------------------" , self.now_time())
            # 程序休息指定时间
            time.sleep(self.loopSleepTime)


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
        first = True
        # 根据现有的 order，设置 pos_pair
        try:
            self.update_pos_pair()
        except Exception as e:
            print("update_pos_pair: ", e)
        # 无限循环
        while True:

            # 保存旧价格以及旧的网格位置
            old_price = self.price
            oldLine = int((self.price - self.init_price) / self.net_space)

            try:

                # 更新当前价格
                self.price = self.get_last_price()
                # 当前价格所在网格线
                line = int((self.price - self.init_price) / self.net_space)
                # if self.debug:
                #     print("line:", line, self.price, self.init_price, self.idleTime)
                
                balance = self.client.balances()
                sol_balance = balance['SOL']['available']
                usdc_balance = balance['USDC']['available']

                if line > oldLine :
                    # 网格上升，表示价格上升，卖出
                    # if self.debug:
                    #     print("价格上涨", oldLine, line, old_price, self.price, self.init_price)
                    
                    # 如果下面那根网格线持有仓位，则优先进行平仓操作
                    if self.pos_pair.get(line-1) is not None:
                        # 卖出
                        # if self.debug:
                        #     print(" 卖出 ", line-1, self.pos_pair[line-1], self.price)
                        if float(sol_balance) > float(self.buy_amount):
                            if self.sell(self.buy_amount, self.price):    
                                # 仓位状态设置为空
                                self.pos_pair[line-1] = None
                        else:
                            self.idleTime -= 1

                            if self.debug:
                                print(" SOL 余额不足")
                elif line < oldLine or first:
                    # 网格降低，表示价格下跌，购买
                    if self.debug:
                        print("价格下跌", oldLine, line, old_price, self.price, self.init_price)

                    if self.pos_pair.get(line) is None:
                        # 如果当前网格线没有仓位，则进行开仓操作
                        # 买入
                        # if self.debug:
                        #     print(" 买入 ", line, self.buy_amount, self.price)
                        if float(usdc_balance) >= (float(self.buy_amount) * float(self.price)):
                            if self.buy(self.buy_amount, self.price):
                                # 仓位状态设置为非空
                                self.pos_pair[line] = self.buy_amount
                        else:
                            self.idleTime -= 1

                            if self.debug:
                                print(" USDC 余额不足")
                # else:
                    # 如果网格不变
                    # if self.debug:
                        # print("价格不变", oldLine, line, old_price, self.price, self.init_price)

                first = False
                # 长时间出现买不了、卖不掉，表示已经超过的网格太久，则应该重新考虑网格
                if self.idleTime <= 0:
                    self.resetInitPrice()
            
            # 异常处理
            except Exception as e:
                print(e, end=" ") 
            # 程序休息指定时间
            time.sleep(self.loopSleepTime)
    

    def show_history(self):
        offset = 0
        total_qulity = 0
        totol_value = 0
        while True:
            fillhistory = self.fillHistoryQuery(self.symbol, 100, offset)
            offset = offset + 1 * 100
            len = fillhistory.__len__()
            # print("len: ", len)

            # 遍历 fillhistory
            for fill in fillhistory:
                print(fill)
                print(fill["orderId"],fill["timestamp"],fill["timestamp"], fill["price"], fill["quantity"], fill["side"])
                total_qulity = total_qulity +  float(fill["quantity"])
                totol_value = totol_value + float(fill["price"]) * float(fill["quantity"])

            print("total_qulity: ", total_qulity)
            print("totol_value: ", totol_value)
            if fillhistory.__len__() < 100:
                break



# 程序入口
if __name__ == '__main__':
    # ddyy
    # API_KEY = "jM08Dj222CwbJAIfGBHBPMHs6vH7eplhNObbvESgcgQ="
    # API_SECRET = "KgwiuV1Yqq7CjKR+Ld75uoR4DsEs/3MRitjrL11qo5U="

    # 0xdy2  
    # API_KEY = "QPpfX1FbxiIOcRXqtxOLy5PztxvMhwezbx5e2uahzsc="
    # API_SECRET = "Vg/4iH1bcnnnrEsa9n6ioAz78mp3fjrdi6FVoWGor6A="

    # 911
    API_KEY = "Sp98NS9+X8ptk7dWQw8GLbcbFMrKCvXWhhu8y2tGAmc="
    API_SECRET = "mwSbxcTpUTkPtz3FgyX3vaUS4A128cOgbsXESqSeBwc="

    # 911-2
    # API_KEY = "HGFaCwGWTXZmbA8XkbOjSvWTutdnV7ddWiWeYT3Vgg4="
    # API_SECRET = "JXiVZJ24944nyVojK0lc5EZR1M2k7Efevh1FRRrg1WA="


    # dy99
    # API_KEY = "l+qyNWH02EpHz1yHMSdKAgHvXXJlkS4Ehr+eUCCoFGc="
    # API_SECRET = "JHQyrb5lagaoLdpirG6y3XcCdOnGiFsYaOCszwCs2Og="

    # 网格数
    netCount = 31
    # 间隔 0.1 u, 买卖手续费大概是 0.09%
    netSpace = 0.0000006 
    # 每个网格交易 0.2 sol
    buyAmount = 20000

    gridClient = GridClient()
    # WEN_USDC
    # SOL_USDC

    gridClient.init("WEN_USDC", netCount, netSpace, buyAmount, API_KEY, API_SECRET)
    gridClient.run_grid_strategy_v2()

    # gridClient.run_grid_strategy()
    # gridClient.sell(buyAmount, 113.33)
    # gridClient.cancelAllOrders()
    # gridClient.run_grid_strategy_v2()
    # gridClient.show_history()
    # gridClient.init_grids()
    # print(gridClient.orderQuery("112164969405284352"))
    
