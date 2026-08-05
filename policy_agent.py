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

POLICY RULES (EC_POLICY_V2):
1. canceled_order_paid / unavailable_order_paid -> Responsible: platform (OLIST_PLATFORM), Action: issue_full_refund.
2. late_delivery_seller -> Responsible: violating sellers, Action: refund_freight, review_seller_handoff.
3. late_delivery_logistics -> Responsible: logistics_provider (LOGISTICS_PROVIDER), Action: refund_freight, review_carrier_delay.
4. valid_split_payment -> Responsible: None, Action: explain_valid_split_payment (NO verify_payment_allocation).
5. unsupported_late_claim -> Responsible: None, Action: reject_late_refund.

CRITICAL INSTRUCTIONS AGAINST HALLUCINATIONS:
- Look at "delivery_variance_hours" in the context. If it is a NEGATIVE number (e.g. -166.52), it means the package was delivered EARLY. You MUST NOT select late_delivery_seller or late_delivery_logistics.
- If the customer makes a claim but no rules are violated, set primary_issue to "unsupported_late_claim" or "no_issue_found", case_status to "no_action", recommended_refund_brl to 0.0, and resolution_actions to [].

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