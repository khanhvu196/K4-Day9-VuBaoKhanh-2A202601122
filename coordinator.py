import json
from extractor import OlistDatabase, CustomerAgent, OrderProductAgent, PaymentAgent
from delivery_agent import DeliveryAgent
from policy_agent import PolicyAgent
from verifier import VerifierAgent

class CoordinatorAgent:
    """Coordinator Agent: nhận case, giao việc và tổng hợp output."""
    def __init__(self):
        self.db = OlistDatabase(data_dir="data")
        self.customer_agent = CustomerAgent(self.db)
        self.order_product_agent = OrderProductAgent(self.db)
        self.payment_agent = PaymentAgent(self.db)
        self.delivery_agent = DeliveryAgent(self.db)
        self.policy_agent = PolicyAgent()
        self.verifier_agent = VerifierAgent()

    def process_case(self, case_input: dict) -> dict:
        order_id = case_input.get("customer_request", {}).get("claimed_order_id")
        if not order_id:
            return {"error": "Missing claimed_order_id"}

        # Handoff 1: Customer Agent
        customer_ctx = self.customer_agent.process(order_id)
        
        # Handoff 2: Order & Product Agent
        order_prod_ctx = self.order_product_agent.process(order_id)
        
        # Handoff 3: Payment Agent
        payment_ctx = self.payment_agent.process(order_id)
        
        # Handoff 4: Delivery Agent (Python + LLM)
        delivery_ctx = self.delivery_agent.process(order_id)
        
        # Ghép các entities của order_prod và payment
        affected_entities = order_prod_ctx.get("affected_entities", {})
        affected_entities["payment_ids"] = payment_ctx.get("payment_ids", [])
        
        # Đóng gói dữ liệu bối cảnh để đưa vào Policy Agent
        
        secondary_issues = []
        if len(order_prod_ctx.get("affected_entities", {}).get("item_ids", [])) >= 2:
            secondary_issues.append("multi_item_order")
        if len(order_prod_ctx.get("affected_entities", {}).get("seller_ids", [])) >= 2:
            secondary_issues.append("multi_seller_order")
        if len(payment_ctx.get("payment_ids", [])) >= 2:
            secondary_issues.append("split_payment")
        if len(customer_ctx.get("related_order_ids", [])) > 0:
            secondary_issues.append("repeat_customer")
        if len(order_prod_ctx.get("product_context", {}).get("category_names", [])) >= 2:
            secondary_issues.append("multiple_categories")
            
        full_context = {
            "order_status": order_prod_ctx.get("order_status"),
            "affected_entities": affected_entities,
            "customer_context": customer_ctx,
            "product_context": order_prod_ctx.get("product_context", {}),
            "payment_reconciliation": payment_ctx.get("payment_reconciliation", {}),
            "delivery_analysis": delivery_ctx.get("delivery_analysis", {}),
            "delivery_fault_analysis": delivery_ctx.get("fault_analysis_text", ""),
            "pre_calculated_secondary_issues": secondary_issues
        }

        # Handoff 5: Policy Agent (LLM)
        raw_json = self.policy_agent.process(case_input.get("customer_request", {}), full_context)
        if "error" in raw_json:
            return raw_json
        
        # Handoff 6: Verifier Agent (Python Guardrail)
        final_json = self.verifier_agent.verify(raw_json, full_context)
        return final_json
