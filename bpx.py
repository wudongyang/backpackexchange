import base64
import json
import time
import requests
from cryptography.hazmat.primitives.asymmetric import ed25519


class BpxClient:
    url = 'https://api.backpack.exchange/'
    private_key: ed25519.Ed25519PrivateKey

    def __init__(self):
        self.debug = False
        self.proxies = {
            'http': '',
            'https': ''
        }
        self.api_key = ''
        self.api_secret = ''
        self.window = 5000

    def init(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.private_key = ed25519.Ed25519PrivateKey.from_private_bytes(
            base64.b64decode(api_secret)
        )

    # capital
    def balances(self):
        return requests.get(url=f'{self.url}api/v1/capital', proxies=self.proxies,
                            headers=self.sign('balanceQuery', {})).json()

    def deposits(self):
        return requests.get(url=f'{self.url}wapi/v1/capital/deposits', proxies=self.proxies,
                            headers=self.sign('depositQueryAll', {})).json()

    def depositAddress(self, chain: str):
        params = {'blockchain': chain}
        return requests.get(url=f'{self.url}wapi/v1/capital/deposit/address', proxies=self.proxies, params=params,
                            headers=self.sign('depositAddressQuery', params)).json()

    def withdrawals(self, limit: int, offset: int):
        params = {'limit': limit, 'offset': offset}
        return requests.get(url=f'{self.url}wapi/v1/capital/withdrawals', proxies=self.proxies, params=params,
                            headers=self.sign('withdrawalQueryAll', params)).json()

    # history

    def orderHistoryQuery(self, symbol: str, limit: int, offset: int):
        params = {'symbol': symbol, 'limit': limit, 'offset': offset}
        return requests.get(url=f'{self.url}wapi/v1/history/orders', proxies=self.proxies, params=params,
                            headers=self.sign('orderHistoryQueryAll', params)).json()

    def fillHistoryQuery(self, symbol: str, limit: int, offset: int):
        params = {'limit': limit, 'offset': offset}
        if len(symbol) > 0:
            params['symbol'] = symbol
        return requests.get(url=f'{self.url}wapi/v1/history/fills', proxies=self.proxies, params=params,
                            headers=self.sign('fillHistoryQueryAll', params)).json()

    # order

    def sign(self, instruction: str, params: dict):

        if self.debug:
            print(f'Instruction: {instruction}')
            print(f'Params: {params}')
        sign_str = f"instruction={instruction}" if instruction else ""
        sorted_params = "&".join(
            f"{key}={value}" for key, value in sorted(params.items())
        )
        if sorted_params:
            sign_str += "&" + sorted_params
        ts = int(time.time() * 1e3)

        sign_str += f"&timestamp={ts}&window={self.window}"
        signature_bytes = self.private_key.sign(sign_str.encode())
        encoded_signature = base64.b64encode(signature_bytes).decode()

        # if self.debug:
        #     print(f'Waiting Sign Str: {sign_str}')
        #     print(f"Signature: {encoded_signature}")

        headers = {
            "X-API-Key": self.api_key,
            "X-Signature": encoded_signature,
            "X-Timestamp": str(ts),
            "X-Window": str(self.window),
            "Content-Type": "application/json; charset=utf-8",
        }
        return headers

    def orderQuery(self, symbol: str, orderId: str):
        params = {'symbol': symbol, 'orderId': orderId}
        return requests.get(url=f'{self.url}api/v1/order', proxies=self.proxies, params=params,
                            headers=self.sign('orderQuery', params)).json()
    
    def orderQueryAll(self, symbol: str):
        params = {'symbol': symbol}
        return requests.get(url=f'{self.url}api/v1/orders', proxies=self.proxies, params=params,
                            headers=self.sign('orderQueryAll', params)).json()

    def cancelOrder(self, symbol: str, orderId: str):
        params = {'symbol': symbol, 'orderId': orderId}
        return requests.delete(url=f'{self.url}api/v1/order', proxies=self.proxies, data=json.dumps(params),
                               headers=self.sign('orderCancel', params)).json()
    
    def cancelAllOrders(self, symbol: str):
        params = {'symbol': symbol}
        return requests.delete(url=f'{self.url}api/v1/orders', proxies=self.proxies, data=json.dumps(params),
                               headers=self.sign('orderCancelAll', params)).json()

    def ExeOrder(self, symbol, side, orderType, timeInForce, quantity, price):
        params = {
            'symbol': symbol,
            'side': side,
            'orderType': orderType,
            'timeInForce': timeInForce,
            'quantity': quantity,
            'price': price
        }

        req = requests.post(url=f'{self.url}api/v1/order', proxies=self.proxies, data=json.dumps(params),
                             headers=self.sign('orderExecute', params))
        if req.ok:
            if self.debug:
                print("请求成功", req.text)
            return True
        else:
            if self.debug:
                print("请求失败", req.text)
            return False
    
    def ExeLimitOrder(self, symbol, side, timeInForce, quantity, price):
        return self.ExeOrder(symbol,side,"Limit",timeInForce, quantity, price)
    
    # 不好用
    def ExeMarketOrder(self, symbol, side, timeInForce, quantity):
        return self.ExeOrder(symbol,side,"Market",timeInForce, quantity)
