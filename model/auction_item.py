from dataclasses import dataclass


@dataclass
class AuctionItem:
    """單一拍賣品項的資料結構"""
    shop_name: str
    item_name: str
    timestamp: str
    price: int
    quantity: int
    trade_type: str
    
    def __dict__(self):
        """返回字典格式，供 Pandas 轉換使用"""
        return {
            'shop_name': self.shop_name,
            'item_name': self.item_name,
            'timestamp': self.timestamp,
            'price': self.price,
            'quantity': self.quantity,
            'trade_type': self.trade_type,
        }