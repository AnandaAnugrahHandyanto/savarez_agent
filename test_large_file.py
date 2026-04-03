import os
import json
import logging
from tools.file_tools import (
    read_file_tool,
    read_file_range_tool,
    search_file_regex_tool
)

logging.basicConfig(level=logging.ERROR)

def run_test():
    # 1. Create a large file (> 50KB)
    test_file = "test_large_file.txt"
    log_file = "test_results.txt"
    f_log = open(log_file, "w", encoding="utf-8")
    def out(s):
        print(s)
        f_log.write(s + "\n")

    with open(test_file, "w") as f:
        # Create 1000 lines of 60 bytes each = 60KB
        for i in range(1, 1001):
            f.write(f"This is test line {i:04d} which is long enough to make 60B.\n")

    try:
        out("Test 1: Read without force (should block)")
        result1_json = read_file_tool(path=test_file, offset=1, limit=500, force=False)
        result1 = json.loads(result1_json)
        if "error" in result1 and "strict 50KB limit" in result1["error"]:
            out("  [PASS] Successfully blocked with 50KB limit error!")
        else:
            out(f"  [FAIL] Expected 50KB limit error, got: {result1}")

        out("\nTest 2: Read with force=True (should succeed)")
        result2_json = read_file_tool(path=test_file, offset=1, limit=500, force=True)
        result2 = json.loads(result2_json)
        if "content" in result2:
            out("  [PASS] Successfully read using force=True!")
            if "_hint" in result2 and "Consider using 'read_file_range'" in result2["_hint"]:
                out("  [PASS] Included proper large-file hint for new tools!")
            else:
                out(f"  [FAIL] Hint was missing or incorrect: {result2.get('_hint')}")
        else:
            out(f"  [FAIL] Expected content, got error: {result2}")

        out("\nTest 3: Read File Range Tool")
        result3_json = read_file_range_tool(path=test_file, start_line=50, end_line=60)
        result3 = json.loads(result3_json)
        if "content" in result3 and "This is test line 0050" in result3["content"]:
            out("  [PASS] Successfully read targeted range via read_file_range_tool")
        else:
            out(f"  [FAIL] Unexpected read_file_range result: {result3}")

        out("\nTest 4: Search File Regex Tool")
        result4_json = search_file_regex_tool(path=test_file, pattern="line 0999")
        result4 = json.loads(result4_json)
        if "matches" in result4 and any("line 0999" in m["content"] for m in result4["matches"]):
            out("  [PASS] Successfully searched the large file")
        else:
            out(f"  [FAIL] Unexpected search result: {result4}")

    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
        f_log.close()
            
if __name__ == "__main__":
    run_test()
