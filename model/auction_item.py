# 檔案: model/auction_item.py
class AuctionItem:
    """單筆露天商店交易記錄的數據模型。"""
    def __init__(self, shop_name: str, item_name: str, slot: str, price: int, quantity: int, trade_type: str):
        self.shop_name = shop_name
        self.item_name = item_name
        self.slot = slot
        self.price = price
        self.quantity = quantity
        self.trade_type = trade_type