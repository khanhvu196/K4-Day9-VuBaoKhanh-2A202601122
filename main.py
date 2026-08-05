import os
import json
from coordinator import CoordinatorAgent

def main():
    input_dir = "input"
    output_dir = "output"
    trace_file = "logging/trace.jsonl"
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs("logging", exist_ok=True)

    print("[INFO] Khởi tạo hệ thống 7-Agent Architecture chuẩn BTC...")
    coordinator = CoordinatorAgent()

    with open(trace_file, "w", encoding="utf-8") as f_trace:
        for i in range(1, 51):
            case_id = f"EC_{i:03d}"
            input_path = os.path.join(input_dir, f"{case_id}.json")
            output_path = os.path.join(output_dir, f"{case_id}.json")

            if not os.path.exists(input_path):
                continue

            print(f"[*] Đang xử lý case {case_id}...")
            with open(input_path, "r", encoding="utf-8") as f_in:
                case_input = json.load(f_in)
            
            final_json = coordinator.process_case(case_input)
            
            if "error" in final_json:
                print(f"[LỖI] {case_id}: {final_json['error']}")
                continue
                
            final_json["case_id"] = case_id
            
            with open(output_path, "w", encoding="utf-8") as f_out:
                json.dump(final_json, f_out, ensure_ascii=False, indent=2)

            trace_entry = {
                "case_id": case_id,
                "status": "success",
                "architecture": "BTC 7-Agent Architecture",
                "primary_issue": final_json.get("case_assessment", {}).get("primary_issue"),
                "responsible_parties": final_json.get("root_cause_analysis", {}).get("responsible_parties")
            }
            f_trace.write(json.dumps(trace_entry, ensure_ascii=False) + "\n")

    print(f"\n[HOÀN TẤT] Xử lý xong 50 cases với kiến trúc 7-Agent thành công!")

if __name__ == "__main__":
    main()