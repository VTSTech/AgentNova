"""
examples/10_skills_demo.py
--------------------------
Demonstrate the Agent Skills system.

This demo shows:
1. Discovering skills (loading metadata)
2. Disclosing available skills as catalog (tier 1)
3. Agent using write_file tool to CREATE a new skill AUTONOMOUSLY

The skill content is NOT provided - the agent generates it!

Use --acp or AGENTNOVA_ACP=1 for ACP integration.
Use --use-mf-sys or AGENTNOVA_USE_MF_SYS=1 for Modelfile system prompts.

Run: python examples/10_skills_demo.py

With CLI:
  agentnova test 10
  agentnova test 10 --acp --debug

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

import os
import sys
import time
import shutil
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova.skills import SkillLoader, SkillRegistry
from agentnova import (
    Agent,
    get_default_client,
    get_available_models,
    get_system_prompt,
    get_tool_support,  # Tool support detection
    AGENTNOVA_BACKEND,
    StepResult,
)
from agentnova.tools.builtins import make_builtin_registry
from agentnova.model_discovery import pick_best_model, get_available_models
from agentnova.shared_args import add_shared_args, parse_shared_args

# Parse CLI args (with env var fallbacks)
parser = argparse.ArgumentParser(description="AgentNova Skills Demo")
add_shared_args(parser)
args = parser.parse_args()
config = parse_shared_args(args)

# Check for flags from config
USE_ACP = config.acp
DEBUG = config.debug
USE_MF_SYS = config.use_modelfile_system

# Import ACP if needed
if USE_ACP:
    try:
        from agentnova import ACPPlugin
    except ImportError:
        print("⚠️ ACP requested but ACPPlugin not available")
        USE_ACP = False

BACKEND_NAME = AGENTNOVA_BACKEND.upper()


def make_step_printer(acp=None):
    """Create a step printer function that optionally forwards to ACP."""
    def print_step(step: StepResult):
        if step.type == "tool_call":
            args = ", ".join(f"{k}={v}" for k, v in (step.tool_args or {}).items())
            print(f"    🔧 {step.tool_name}({args})")
        elif step.type == "tool_result":
            preview = step.content[:80] + "..." if len(step.content) > 80 else step.content
            print(f"    📦 → {preview}")
        
        # Forward to ACP if enabled
        if acp:
            acp.on_step(step)
    
    return print_step


def main():
    print("⚛️ AgentNova R02 - Skills Demo")
    print("=" * 60)
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    skills_dir = os.path.join(base_dir, "agentnova", "skills")
    
    # ========================================
    # STEP 1: DISCOVER skills
    # ========================================
    print("\n📦 Step 1: Discovering skills...")
    loader = SkillLoader()
    skills = loader.list_skills()
    print(f"   Found {len(skills)} skill(s): {skills}")
    
    skill_creator = loader.load("skill-creator")
    print(f"   ✓ Loaded: {skill_creator.name}")
    print(f"   ✓ Description: {skill_creator.description[:60]}...")
    print(f"   ✓ Instructions: {len(skill_creator.instructions)} chars")
    print(f"   ✓ Has scripts/: {skill_creator.scripts_dir is not None}")
    print(f"   ✓ Has references/: {skill_creator.references_dir is not None}")
    print(f"   ✓ Has assets/: {skill_creator.assets_dir is not None}")
    
    # Show what's in the scripts directory
    if skill_creator.scripts_dir:
        scripts = list(skill_creator.scripts_dir.glob("*.py"))
        print(f"   ✓ Scripts: {[s.name for s in scripts[:3]]}...")
    
    # ========================================
    # STEP 2: DISCLOSE catalog (tier 1)
    # ========================================
    print("\n" + "=" * 60)
    print("📋 Step 2: Building skill catalog (tier 1)")
    print("   (Only name + description - NOT full instructions)")
    print("=" * 60)
    
    registry = SkillRegistry()
    registry.add(skill_creator)
    
    catalog = registry.to_system_prompt_addition()
    print(f"   Catalog size: {len(catalog)} chars")
    print("   Preview (first 10 lines):")
    for line in catalog.split("\n")[2:12]:
        print(f"      {line[:60]}")
    
    # ========================================
    # STEP 3: CREATE AGENT with TOOLS
    # ========================================
    print("\n" + "=" * 60)
    print("🤖 Step 3: Creating Agent with tools")
    print("=" * 60)
    
    client = get_default_client()
    
    if not client.is_running():
        print(f"   ❌ {BACKEND_NAME} is not running!")
        if AGENTNOVA_BACKEND == "bitnet":
            print("   Start llama-server from bitnet.cpp directory")
        else:
            print("   Start with: ollama serve")
        return
    
    models = client.list_models()
    print(f"   Models: {len(models)} available")
    
    # Pick best model dynamically
    model = pick_best_model(preferred=config.model, client=client)
    if not model:
        model = models[0] if models else None
    
    if not model:
        print("   ❌ No models available!")
        return
    
    print(f"   Using: {model}")
    print(f"   Tool support: {get_tool_support(model, client)}")
    
    # Initialize ACP if enabled
    acp = None
    if USE_ACP:
        acp = ACPPlugin(
            agent_name="AgentNova-SkillsDemo",
            model_name=model,
            debug=DEBUG,
        )
        print(f"   ACP URL: {acp.base_url}")
        bootstrap = acp.bootstrap(claim_primary=False)
        print(f"   ACP Status: {'connected' if bootstrap.get('status') else 'unavailable'}")
    
    if DEBUG:
        print(f"   Debug: enabled")
    
    tools = make_builtin_registry().subset(["write_file"])
    tool_names = [t.name for t in tools.all()]
    print(f"   Tools: {tool_names}")
    
    # Create agent with skill-creator instructions in system prompt
    skill_creator_brief = """
## Creating Skills

Skills are markdown files with YAML frontmatter:

---
name: skill-name
description: What the skill does and when to use it
---

# Skill Title

Instructions for using the skill.
"""
    
    agent = Agent(
        model=model,
        tools=tools,
        system_prompt=get_system_prompt(
            model,
            client=client,
            default_prompt="You create skill files using the write_file tool.\n\n" + skill_creator_brief,
        ),
        max_steps=5,
        on_step=make_step_printer(acp),
        debug=DEBUG,
        client=client,
        model_options={
            "temperature": 0.0,      # Deterministic
            "num_ctx": 2048,        # Enough for skill creation
            "num_predict": 1024,    # Enough for skill content
        },
    )
    
    # ========================================
    # STEP 4: AGENT CREATES SKILL AUTONOMOUSLY
    # ========================================
    print("\n" + "=" * 60)
    print("🔨 Step 4: Agent creates a skill file AUTONOMOUSLY")
    print("   (Agent generates the content - NOT provided in prompt!)")
    print("=" * 60)
    
    skill_dir = os.path.join(skills_dir, "demo-skill")
    skill_path = os.path.join(skill_dir, "SKILL.md")
    
    # Clean up previous run
    if os.path.exists(skill_dir):
        shutil.rmtree(skill_dir)
    
    os.makedirs(skill_dir, exist_ok=True)
    
    # PROMPT: Ask for a skill, but don't provide the content!
    prompt = f"""Create a skill named 'demo-skill' at: {skill_path}

The skill should help with basic text operations like:
- Counting words and characters
- Converting case (uppercase, lowercase)
- Finding and replacing text

Write a complete SKILL.md file with:
1. YAML frontmatter (name and description)
2. Markdown instructions

Use write_file to create the file."""
    
    print(f"   Target: {skill_path}")
    print(f"   Prompt: Create a demo-skill for text operations")
    print("   Running agent...")
    
    if acp:
        acp.log_user_message(prompt)
    
    start = time.time()
    try:
        result = agent.run(prompt)
        elapsed = time.time() - start
        
        print(f"\n   ⏱️ Completed in {elapsed:.1f}s")
        print(f"   Steps: {len(result.steps)}")
        
        if acp:
            acp.log_assistant_message(result.final_answer)
    except Exception as e:
        elapsed = time.time() - start
        print(f"   ⚠️ Error after {elapsed:.1f}s: {type(e).__name__}")
        print(f"   Error: {e}")
    
    # ========================================
    # STEP 5: VERIFY FILE
    # ========================================
    print("\n" + "=" * 60)
    print("📁 Step 5: Verifying file creation")
    print("=" * 60)
    
    if os.path.exists(skill_path):
        print("   ✅ FILE CREATED!")
        with open(skill_path, encoding='utf-8') as f:
            content = f.read()
        print(f"   Size: {len(content)} chars")
        print("   Content:")
        print("   " + "-" * 50)
        for line in content.split("\n"):
            print(f"   {line}")
        print("   " + "-" * 50)
    else:
        print("   ❌ File not found - agent may have failed to create it")
        return
    
    # ========================================
    # STEP 6: LOAD NEW SKILL
    # ========================================
    print("\n" + "=" * 60)
    print("📚 Step 6: Loading the newly created skill")
    print("=" * 60)
    
    loader = SkillLoader()
    skills = loader.list_skills()
    print(f"   Available skills: {skills}")
    
    demo_skill = loader.load("demo-skill")
    if demo_skill:
        print(f"   ✓ Loaded: {demo_skill.name}")
        print(f"   ✓ Description: {demo_skill.description}")
    else:
        print("   ⚠️ Could not load demo-skill")
        return
    
    # ========================================
    # STEP 7: TEST SKILL
    # ========================================
    print("\n" + "=" * 60)
    print("🧪 Step 7: Testing Agent with the new skill")
    print("=" * 60)
    
    test_registry = SkillRegistry()
    test_registry.add(demo_skill)
    
    test_agent = Agent(
        model=model,
        tools=None,
        system_prompt=get_system_prompt(
            model,
            client=client,
            default_prompt="You help with demos." + test_registry.to_system_prompt_addition(),
        ),
        max_steps=2,
        on_step=make_step_printer(acp),
        debug=DEBUG,
        client=client,
        model_options={
            "temperature": 0.3,     # Some creativity for demo
            "num_ctx": 512,         # Small context
            "num_predict": 256,     # Moderate response
        },
    )
    
    question = "What can the demo-skill help me with?"
    print(f"   Question: {question}")
    
    if acp:
        acp.log_user_message(question)
    
    try:
        response = test_agent.chat(question)
        print(f"\n   Response: {response}")
        if acp:
            acp.log_assistant_message(response)
    except Exception as e:
        print(f"   ⚠️ Error: {type(e).__name__}")
    
    # ========================================
    # SUMMARY
    # ========================================
    if acp:
        print("\n--- Session complete ---")
        tokens = acp.get_session_tokens()
        print(f"   Session tokens: {tokens}")
    
    print("\n" + "=" * 60)
    print("✅ Skills demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
