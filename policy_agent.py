import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

class BaseLLMAgent:
    """Base class for API calls."""
    def __init__(self, model_name="meta-llama/llama-3.1-8b-instruct"):
        self.model_name = model_name
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    def _call_llm(self, system_prompt: str, user_content: str, json_mode: bool = True):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/K4-Day9-Multi-Agent",
            "X-Title": "Olist 7-Agent Architecture"
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.0
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
            
        try:
            response = requests.post(self.url, headers=headers, json=payload)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"].strip()
                if json_mode:
                    if content.startswith("```"):
                        lines = content.splitlines()
                        content = "\n".join([line for line in lines if not line.startswith("```")]).strip()
                    return json.loads(content)
                return content
            return {"error": response.text} if json_mode else f"Error: {response.text}"
        except Exception as e:
            return {"error": str(e)} if json_mode else f"Exception: {str(e)}"

class PolicyAgent(BaseLLMAgent):
    """Policy Agent: áp dụng EC_POLICY_V2, xác định taxonomy, responsibility, refund và actions."""
    def process(self, customer_req: dict, context_data: dict) -> dict:
        sys_prompt = """
You are the Policy Agent. Your task is to output a STRICT JSON object resolving the case based on context data and delivery analysis.
You are the Policy Agent. Your task is to output a STRICT JSON object resolving the case.

POLICY RULES (EC_POLICY_V2) - MATCH EXACTLY (DO NOT INVENT ANYTHING):
1. If order canceled and payment > 0:
   primary_issue: "canceled_order_paid", cause_code: "ORDER_CANCELED_AFTER_PAYMENT", responsible: "platform" (OLIST_PLATFORM), action: "issue_full_refund"
2. If order unavailable and payment > 0:
   primary_issue: "unavailable_order_paid", cause_code: "ORDER_UNAVAILABLE_AFTER_PAYMENT", responsible: "platform" (OLIST_PLATFORM), action: "issue_full_refund"
3. If delivery_variance_hours > 0 (LATE) AND seller late_handoff is true:
   primary_issue: "late_delivery_seller", cause_code: "SELLER_HANDOFF_AFTER_LIMIT", responsible: "seller" (violating seller_id), actions: "refund_freight", "review_seller_handoff"
4. If delivery_variance_hours > 0 (LATE) AND no seller late_handoff:
   primary_issue: "late_delivery_logistics", cause_code: "CARRIER_DELIVERED_AFTER_ESTIMATE", responsible: "logistics_provider" (LOGISTICS_PROVIDER), actions: "refund_freight", "review_carrier_delay"
5. If split payment (>=2 payments) AND reconciled is true:
   primary_issue: "valid_split_payment", cause_code: "MULTIPLE_PAYMENTS_RECONCILED", responsible: null, action: "explain_valid_split_payment"
6. If delivery_variance_hours <= 0 (EARLY/ON TIME) or no other rule matches:
   primary_issue: "unsupported_late_claim", cause_code: "DELIVERY_WITHIN_ESTIMATE", responsible: null, action: "reject_late_refund"

CRITICAL: YOU MUST ONLY USE THE EXACT STRINGS ABOVE FOR primary_issue, cause_code, and resolution_actions! Do NOT use "early_delivery_seller" or "issue_partial_refund". If responsible is null, leave responsible_parties empty [].
Secondary Issues (append in this exact order if condition met):
1. multi_item_order: >= 2 item rows.
2. multi_seller_order: >= 2 different sellers.
3. split_payment: >= 2 payment rows.
4. repeat_customer: >= 2 related orders.
5. multiple_categories: >= 2 categories.

JSON SCHEMA REQUIREMENT (DO NOT INCLUDE Context data blocks, the Python Verifier will append them):
{
  "case_assessment": {
    "primary_issue": "string",
    "secondary_issues": ["string"],
    "case_status": "action_required or no_action",
    "confidence": 0.95
  },
  "root_cause_analysis": {
    "ranked_causes": [{"cause_code": "string", "rank": 1}],
    "responsible_parties": [{"party_type": "string", "party_id": "string"}]
  },
  "evidence_ids": ["string"],
  "financial_resolution": {
    "currency": "BRL",
    "recommended_refund_brl": 0.0
  },
  "resolution_actions": ["string"]
}
"""
        payload = {
            "customer_request": customer_req,
            "context_data": context_data
        }
        return self._call_llm(sys_prompt, json.dumps(payload), json_mode=True)