import json
import pandas as pd
from datetime import datetime
from extractor import OlistDatabase
from policy_agent import BaseLLMAgent

class DeliveryAgent(BaseLLMAgent):
    """Delivery Agent: tính delivery variance và seller handoff variance (Python) và suy luận lỗi (LLM)."""
    def __init__(self, db: OlistDatabase):
        super().__init__()
        self.db = db
        
    def process(self, order_id: str) -> dict:
        # Python Logic
        order_row = self.db.df_orders[self.db.df_orders["order_id"] == order_id]
        if order_row.empty: return {}
        order = order_row.iloc[0]
        
        items = self.db.df_items[self.db.df_items["order_id"] == order_id]
        
        delivered_at = order["order_delivered_customer_date"]
        estimated_delivery_at = order["order_estimated_delivery_date"]
        carrier_handoff_at = order["order_delivered_carrier_date"]
        
        delivery_variance_hours = None
        if pd.notna(delivered_at) and pd.notna(estimated_delivery_at):
            dt_deliv = datetime.strptime(str(delivered_at), "%Y-%m-%d %H:%M:%S")
            dt_estim = datetime.strptime(str(estimated_delivery_at), "%Y-%m-%d %H:%M:%S")
            delivery_variance_hours = round((dt_deliv - dt_estim).total_seconds() / 3600.0, 2)
            
        seller_limits = {}
        for _, item in items.iterrows():
            s_id = item["seller_id"]
            limit_at = item["shipping_limit_date"]
            if pd.notna(limit_at):
                dt = datetime.strptime(str(limit_at), "%Y-%m-%d %H:%M:%S")
                if s_id not in seller_limits or dt < seller_limits[s_id]:
                    seller_limits[s_id] = dt
                    
        seller_handoff_analysis = []
        late_handoff_seller_ids = []
        
        # We need a stable order of sellers. So we will collect from item list sequentially, ignoring duplicates.
        seen_sellers = set()
        for _, item in items.iterrows():
            s_id = item["seller_id"]
            if s_id in seen_sellers:
                continue
            seen_sellers.add(s_id)
            
            limit_dt = seller_limits.get(s_id)
            handoff_variance_hours = 0.0
            late_handoff = False
            
            if pd.notna(carrier_handoff_at) and limit_dt is not None:
                dt_handoff = datetime.strptime(str(carrier_handoff_at), "%Y-%m-%d %H:%M:%S")
                handoff_variance_hours = round((dt_handoff - limit_dt).total_seconds() / 3600.0, 2)
                if handoff_variance_hours > 0:
                    late_handoff = True
                    late_handoff_seller_ids.append(s_id)
                    
            seller_handoff_analysis.append({
                "seller_id": s_id,
                "shipping_limit_at": limit_dt.strftime("%Y-%m-%d %H:%M:%S") if limit_dt else None,
                "handoff_variance_hours": handoff_variance_hours,
                "late_handoff": late_handoff
            })
            
        delivery_analysis = {
            "delivered_at": str(delivered_at) if pd.notna(delivered_at) else None,
            "estimated_delivery_at": str(estimated_delivery_at) if pd.notna(estimated_delivery_at) else None,
            "carrier_handoff_at": str(carrier_handoff_at) if pd.notna(carrier_handoff_at) else None,
            "delivery_variance_hours": delivery_variance_hours,
            "seller_handoff_analysis": seller_handoff_analysis,
            "late_handoff_seller_ids": late_handoff_seller_ids
        }
        
        # LLM Logic: call OpenRouter to analyze fault
        sys_prompt = "You are the Delivery Analyst Agent. Based on the delivery variance and seller handoff hours, provide a short text concluding if there is a late delivery, and who is at fault (seller or logistics). CRITICAL NOTE: Negative (-) variance hours means EARLY delivery (NOT late). Positive (+) variance hours means LATE delivery."
        llm_analysis = self._call_llm(sys_prompt, json.dumps(delivery_analysis), json_mode=False)
        
        return {
            "delivery_analysis": delivery_analysis,
            "fault_analysis_text": llm_analysis
        }
