import os
import pandas as pd

class OlistDatabase:
    """Shared database to load CSVs once into RAM."""
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.df_orders = None
        self.df_customers = None
        self.df_items = None
        self.df_payments = None
        self.df_reviews = None
        self.df_products = None
        self.df_sellers = None
        self._load_raw_csvs()

    def _load_raw_csvs(self):
        try:
            self.df_orders = pd.read_csv(os.path.join(self.data_dir, "olist_orders_dataset.csv"))
            self.df_customers = pd.read_csv(os.path.join(self.data_dir, "olist_customers_dataset.csv"))
            self.df_items = pd.read_csv(os.path.join(self.data_dir, "olist_order_items_dataset.csv"))
            self.df_payments = pd.read_csv(os.path.join(self.data_dir, "olist_order_payments_dataset.csv"))
            self.df_reviews = pd.read_csv(os.path.join(self.data_dir, "olist_order_reviews_dataset.csv"))
            self.df_products = pd.read_csv(os.path.join(self.data_dir, "olist_products_dataset.csv"))
            self.df_sellers = pd.read_csv(os.path.join(self.data_dir, "olist_sellers_dataset.csv"))
            print("[OlistDatabase] Đã nạp thành công toàn bộ dữ liệu CSV.")
        except Exception as e:
            print(f"[OlistDatabase] [LỖI HỆ THỐNG] Không thể nạp CSDL: {e}")

class CustomerAgent:
    """Customer Agent: xác định customer identity và lịch sử order."""
    def __init__(self, db: OlistDatabase):
        self.db = db
    
    def process(self, order_id: str) -> dict:
        order_row = self.db.df_orders[self.db.df_orders["order_id"] == order_id]
        if order_row.empty: return {}
        
        customer_id = order_row.iloc[0]["customer_id"]
        cust_row = self.db.df_customers[self.db.df_customers["customer_id"] == customer_id]
        
        customer_unique_id = None
        related_order_ids = []
        if not cust_row.empty:
            customer_unique_id = cust_row.iloc[0]["customer_unique_id"]
            same_cust_ids = self.db.df_customers[self.db.df_customers["customer_unique_id"] == customer_unique_id]["customer_id"]
            related_orders = self.db.df_orders[self.db.df_orders["customer_id"].isin(same_cust_ids)]
            related_order_ids = related_orders["order_id"].tolist()
        
        return {
            "customer_unique_id": customer_unique_id,
            "related_order_ids": related_order_ids[:5]
        }

class OrderProductAgent:
    """Order & Product Agent: kiểm tra order, item, seller, product và category."""
    def __init__(self, db: OlistDatabase):
        self.db = db

    def process(self, order_id: str) -> dict:
        order_row = self.db.df_orders[self.db.df_orders["order_id"] == order_id]
        if order_row.empty: return {}
        
        order_status = order_row.iloc[0]["order_status"]
        items = self.db.df_items[self.db.df_items["order_id"] == order_id]
        
        item_ids, product_ids, category_names, seller_ids = [], [], [], []
        
        for _, item in items.iterrows():
            item_ids.append(f"{order_id}:{item['order_item_id']}")
            product_ids.append(item["product_id"])
            seller_ids.append(item["seller_id"])
            
            prod_row = self.db.df_products[self.db.df_products["product_id"] == item["product_id"]]
            if not prod_row.empty and pd.notna(prod_row.iloc[0]["product_category_name"]):
                category_names.append(prod_row.iloc[0]["product_category_name"])
                
        return {
            "order_status": order_status,
            "affected_entities": {
                "order_ids": [order_id],
                "item_ids": item_ids[:5],
                "seller_ids": list(set(seller_ids))[:3]
            },
            "product_context": {
                "product_ids": list(set(product_ids))[:5],
                "category_names": list(set(category_names))[:5]
            }
        }

class PaymentAgent:
    """Payment Agent: tổng hợp payment row và đối soát với item + freight."""
    def __init__(self, db: OlistDatabase):
        self.db = db

    def process(self, order_id: str) -> dict:
        items = self.db.df_items[self.db.df_items["order_id"] == order_id]
        payments = self.db.df_payments[self.db.df_payments["order_id"] == order_id]
        
        payment_ids = [f"{order_id}:{row['payment_sequential']}" for _, row in payments.iterrows()]
        payment_types = payments["payment_type"].unique().tolist()
        
        payment_total_brl = round(float(payments["payment_value"].sum()), 2)
        has_items = not items.empty
        if has_items:
            item_total_brl = round(float(items["price"].sum()), 2)
            freight_total_brl = round(float(items["freight_value"].sum()), 2)
            expected_total_brl = round(item_total_brl + freight_total_brl, 2)
            difference_brl = round(payment_total_brl - expected_total_brl, 2)
            reconciled = abs(difference_brl) <= 0.10
        else:
            item_total_brl = freight_total_brl = expected_total_brl = None
            difference_brl = None
            reconciled = None
            
        return {
            "payment_ids": payment_ids[:5],
            "payment_reconciliation": {
                "currency": "BRL",
                "item_total_brl": item_total_brl,
                "freight_total_brl": freight_total_brl,
                "expected_total_brl": expected_total_brl,
                "payment_total_brl": payment_total_brl,
                "difference_brl": difference_brl,
                "reconciled": reconciled,
                "payment_types": payment_types
            }
        }