import subprocess
import sys

# We want to run the interactive script and feed inputs in code to simulate full execution
# We will test two modes:
# 1. Classical step-by-step input
# 2. Advanced Multi-step batch selection ("1, 1, 1, 1, 5" in a single line!)

def run_test(test_name, inputs):
    print(f"\n==================================================")
    print(f"[RUN] TEST: {test_name}")
    print(f"==================================================")
    proc = subprocess.Popen(
        [sys.executable, 'examples/demo_interactive.py'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8'
    )
    stdout_out, stderr_out = proc.communicate(input="".join(inputs))
    print("=== CLI STDOUT ===")
    print(stdout_out)
    if stderr_out:
        print("=== CLI STDERR ===")
        print(stderr_out)

# Run Test 1: Classical step-by-step
run_test("Classical Step-by-step", [
    "Create E MS Installatie FP\n",  # Start
    "1\n",                           # Installatie -> Rail FP
    "1\n",                           # Rail FP -> Veld FP
    "1\n",                           # Veld FP -> Geleider
    "1\n",                           # Geleider -> Eindsluiting FP
    "5\n"                            # Exit (DONE option on the 5th menu)
])

# Run Test 2: Advanced Batch Multi-select
run_test("Advanced Batch Multi-select", [
    "Create E MS Installatie FP\n",  # Start
    "1, 1, 1, 1, 5\n"                # Input the entire cascading path at once!
])

