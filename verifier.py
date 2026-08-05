class VerifierAgent:
    """Verifier Agent: kiểm tra ID, số tiền, null handling, array limit và schema trước khi ghi file."""
    def verify(self, raw_json: dict, full_context: dict) -> dict:
        if not raw_json or "case_assessment" not in raw_json:
            return {"error": "Invalid JSON structure from Policy Agent"}
            
        final_json = raw_json.copy()
        
        # 1. Trám thêm Data (từ các Agents Python)
        entities = full_context.get("affected_entities", {})
        final_json["affected_entities"] = entities
        final_json["customer_context"] = full_context.get("customer_context", {})
        final_json["product_context"] = full_context.get("product_context", {})
        final_json["delivery_analysis"] = full_context.get("delivery_analysis", {})
        final_json["payment_reconciliation"] = full_context.get("payment_reconciliation", {})
        
        # 2. Lọc Evidence ảo giác
        valid_evs = set()
        valid_evs.update([f"order:{o}" for o in entities.get("order_ids", [])])
        valid_evs.update([f"item:{i}" for i in entities.get("item_ids", [])])
        valid_evs.update([f"seller:{s}" for s in entities.get("seller_ids", [])])
        valid_evs.update([f"payment:{p}" for p in entities.get("payment_ids", [])])
        
        valid_policies = [
            "policy:canceled_order_paid", "policy:unavailable_order_paid",
            "policy:late_delivery_seller", "policy:late_delivery_logistics",
            "policy:valid_split_payment", "policy:unsupported_late_claim",
            "policy:SELLER_HANDOFF_AFTER_LIMIT", "policy:CARRIER_DELIVERED_AFTER_ESTIMATE",
            "policy:ORDER_CANCELED_AFTER_PAYMENT", "policy:ORDER_UNAVAILABLE_AFTER_PAYMENT",
            "policy:MULTIPLE_PAYMENTS_RECONCILED", "policy:DELIVERY_WITHIN_ESTIMATE"
        ]
        valid_evs.update(valid_policies)
        
        raw_evs = final_json.get("evidence_ids", [])
        clean_evs = [e for e in raw_evs if e in valid_evs]
        final_json["evidence_ids"] = clean_evs[:20]
        
        # 3. Ép array limit
        if len(entities.get("order_ids", [])) > 5: entities["order_ids"] = entities["order_ids"][:5]
        if len(entities.get("item_ids", [])) > 5: entities["item_ids"] = entities["item_ids"][:5]
        if len(entities.get("seller_ids", [])) > 3: entities["seller_ids"] = entities["seller_ids"][:3]
        if len(entities.get("payment_ids", [])) > 5: entities["payment_ids"] = entities["payment_ids"][:5]
        
        cust_ctx = final_json.get("customer_context", {})
        if len(cust_ctx.get("related_order_ids", [])) > 5: cust_ctx["related_order_ids"] = cust_ctx["related_order_ids"][:5]
        
        prod_ctx = final_json.get("product_context", {})
        if len(prod_ctx.get("product_ids", [])) > 5: prod_ctx["product_ids"] = prod_ctx["product_ids"][:5]
        if len(prod_ctx.get("category_names", [])) > 5: prod_ctx["category_names"] = prod_ctx["category_names"][:5]
        
        root_cause = final_json.get("root_cause_analysis", {})
        if len(root_cause.get("ranked_causes", [])) > 3: root_cause["ranked_causes"] = root_cause["ranked_causes"][:3]
        if len(root_cause.get("responsible_parties", [])) > 3: root_cause["responsible_parties"] = root_cause["responsible_parties"][:3]
        
        actions = final_json.get("resolution_actions", [])
        if len(actions) > 5: final_json["resolution_actions"] = actions[:5]
        
        # 4. K4 business logic checks & Overrides
        # Override secondary_issues with pre-calculated ones to ensure perfect order
        if "case_assessment" not in final_json:
            final_json["case_assessment"] = {}
        final_json["case_assessment"]["secondary_issues"] = full_context.get("pre_calculated_secondary_issues", [])
        
        primary_issue = final_json.get("case_assessment", {}).get("primary_issue")
        if primary_issue == "valid_split_payment" and "verify_payment_allocation" in final_json.get("resolution_actions", []):
            final_json["resolution_actions"] = [a for a in final_json["resolution_actions"] if a != "verify_payment_allocation"]
            
        conf = final_json.get("case_assessment", {}).get("confidence", 0.95)
        final_json["case_assessment"]["confidence"] = max(0.0, min(1.0, float(conf)))
        
        # Đảm bảo recommended_refund_brl là float và làm tròn 2 chữ số
        if "financial_resolution" in final_json:
            refund = final_json["financial_resolution"].get("recommended_refund_brl", 0.0)
            try:
                final_json["financial_resolution"]["recommended_refund_brl"] = round(float(refund), 2)
            except (ValueError, TypeError):
                final_json["financial_resolution"]["recommended_refund_brl"] = 0.0
        
        # 5. Xử lý Null handling logic cho order ko có item
        if entities.get("item_ids") == []:
            final_json["payment_reconciliation"]["expected_total_brl"] = None
            final_json["payment_reconciliation"]["difference_brl"] = None
            final_json["payment_reconciliation"]["reconciled"] = None
            final_json["affected_entities"]["item_ids"] = []
            final_json["affected_entities"]["seller_ids"] = []
            final_json["product_context"]["product_ids"] = []
            final_json["product_context"]["category_names"] = []
            final_json["delivery_analysis"]["seller_handoff_analysis"] = []
            
        return final_json