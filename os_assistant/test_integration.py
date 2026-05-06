import sys
import os

# Add root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.memory import Memory
from agent.self_evolution import SelfEvolutionEngine
from agent.host_control import HostController

def run_tests():
    print("--- Running OS Assistant Integration Tests ---")
    
    # 1. Test Memory (Mem0 check)
    print("\n[1] Testing Memory & Mem0 Initialization...")
    try:
        memory = Memory()
        stats = memory.get_stats()
        print(f"Memory Stats: {stats}")
        if stats.get('mem0_active'):
            print("[SUCCESS] Mem0 is ACTIVE")
        else:
            print("[WARNING] Mem0 is INACTIVE (Might be missing API keys or chroma setup in .env)")
    except Exception as e:
        print(f"[ERROR] Memory init failed: {e}")
        return

    # 2. Test Self-Evolution Engine
    print("\n[2] Testing Self-Evolution Engine (Hot Reload)...")
    try:
        evo = SelfEvolutionEngine(memory=memory)
        
        # Write a dummy skill
        code = """def run(**kwargs):
    return "Hello from " + kwargs.get('name', 'World')
"""
        res_create = evo.create_and_load_skill("test_skill", code)
        print(f"Create Skill: {res_create}")
        if res_create.get('success'):
            print("[SUCCESS] Skill Created & Compiled Successfully")
        else:
            print("[ERROR] Skill Creation Failed")
            
        res_exec = evo.execute_skill("test_skill", {"name": "AI OS"})
        print(f"Execute Skill: {res_exec}")
        if res_exec.get('result') == 'Hello from AI OS':
            print("[SUCCESS] Skill Executed & Returned correct value")
        else:
            print("[ERROR] Skill Execution Failed")
            
    except Exception as e:
        print(f"[ERROR] Self-Evolution failed: {e}")

    # 3. Test HostController
    print("\n[3] Testing HostController (PowerShell)...")
    try:
        res_ps = HostController.run_powershell("Write-Output 'PowerShell is alive'")
        print(f"PowerShell Output: {res_ps}")
        if res_ps.get('success') and 'PowerShell is alive' in res_ps.get('output', ''):
            print("[SUCCESS] PowerShell Sub-Agent Working")
        else:
            print("[ERROR] PowerShell Execution Failed")
    except Exception as e:
        print(f"[ERROR] HostController failed: {e}")

    print("\n--- ALL TESTS COMPLETED ---")

if __name__ == "__main__":
    run_tests()
