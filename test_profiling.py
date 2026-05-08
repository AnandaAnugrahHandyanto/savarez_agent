import sys
sys.path.insert(0, '.')
from profiling import Profiler, get_profiler, ProfilingStats

# Test 1: Basic profiler creation
p = get_profiler()
print("✓ Profiler created")

# Test 2: Record timings
p.record_tool_timing('test_tool', 1.5)
p.record_tool_timing('test_tool', 2.0)
p.record_api_timing(0.5)
print("✓ Timings recorded")

# Test 3: Get statistics
stats = p.get_statistics()
assert stats['tools']['test_tool']['call_count'] == 2
assert stats['api_calls']['call_count'] == 1
print("✓ Statistics correct")

# Test 4: Reset
p.reset()
stats = p.get_statistics()
assert stats['tools'] == {}
print("✓ Reset works")

# Test 5: safe_print
from safe_print import safe_print
safe_print("✓ safe_print works")
print("✓ safe_print imported")

print("\nAll tests passed!")
