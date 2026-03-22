"""
examples/11_skill_creator_test.py
---------------------------------
Test if models can CREATE skills autonomously using the skill-creator guidance.

This test does NOT provide the skill content - the model must generate it.
The skill-creator skill provides instructions on how to create skills.
The model uses write_file to create the skill.

Models that WORK with tool calling:
- functiongemma:270m (270M) - FAST, reliable
- qwen2.5:0.5b (494M) - Good reliability  
- granite4:350m (352M) - Works

Run: python examples/11_skill_creator_test.py

With CLI:
  agentnova test 11
  agentnova test 11 --acp
  agentnova test 11 --use-mf-sys --model qwen2.5-coder:0.5b

Written by VTSTech — https://www.vts-tech.org — https://github.com/VTSTech/AgentNova
"""

import os
import sys
import time
import shutil
import yaml
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentnova.skills import SkillLoader, SkillRegistry
from agentnova import Agent, get_default_client, AGENTNOVA_BACKEND, StepResult
from agentnova.tools.builtins import make_builtin_registry
from agentnova.model_discovery import pick_best_model, get_available_models
from agentnova.shared_args import add_shared_args, parse_shared_args

# Parse CLI args (with env var fallbacks)
parser = argparse.ArgumentParser(description="AgentNova Skill Creator Test")
add_shared_args(parser)
args = parser.parse_args()
config = parse_shared_args(args)

# Check for optional ACP support
USE_ACP = config.acp
if USE_ACP:
    try:
        from agentnova.acp_plugin import ACPPlugin
    except ImportError:
        print("⚠️ ACP requested but ACPPlugin not available")
        USE_ACP = False

# Check for debug mode
DEBUG = config.debug

BACKEND_NAME = AGENTNOVA_BACKEND.upper()


# Configuration - models discovered dynamically
MODEL_ORDER = []  # Will be populated from available models

# Models known to work well with tools (for reference)
PREFERRED_TOOL_MODELS = ["functiongemma:270m", "qwen2.5:0.5b", "granite4:350m", "llama3.2:1b", "qwen2.5:1.5b"]

# Skill to create - we describe WHAT we want, not the content
SKILL_REQUESTS = [
    {
        "name": "file-converter",
        "task": "Create a skill that helps convert files between formats like CSV, JSON, HTML, and Markdown.",
        "expected_sections": ["format", "convert", "file"],
    },
    {
        "name": "text-analyzer",
        "task": "Create a skill that analyzes text for word count, character count, and sentiment.",
        "expected_sections": ["text", "count", "analyze"],
    },
]

VERBOSE = os.environ.get("AGENTNOVA_VERBOSE", "1") == "1"
TIMEOUT = int(os.environ.get("AGENTNOVA_TIMEOUT", "120"))


def print_step(step: StepResult, indent="  "):
    """Print step information with full details."""
    if step.type == "tool_call":
        print(f"{indent}🔧 TOOL CALL: {step.tool_name}")
        if step.tool_args:
            print(f"{indent}   Arguments:")
            for k, v in step.tool_args.items():
                v_str = repr(v)
                # Show full content, no truncation
                print(f"{indent}     {k}: {v_str}")
    elif step.type == "tool_result":
        print(f"{indent}📦 RESULT: [{len(step.content)} chars]")
        for line in step.content.split('\n'):
            print(f"{indent}   {line}")
    elif step.type == "final":
        print(f"{indent}💬 FINAL ANSWER: [{len(step.content)} chars]")
        for line in step.content.split('\n'):
            print(f"{indent}   {line}")


def validate_skill(content: str, skill_name: str, expected_sections: list) -> dict:
    """Validate a skill file and return validation results."""
    result = {
        "valid": False,
        "has_frontmatter": False,
        "has_name": False,
        "has_description": False,
        "has_instructions": False,
        "frontmatter_valid": False,
        "name_matches": False,
        "has_relevant_content": False,
        "errors": [],
        "content_length": len(content),
    }
    
    if not content.strip().startswith("---"):
        result["errors"].append("Missing YAML frontmatter")
        return result
    
    result["has_frontmatter"] = True
    parts = content.split("---", 2)
    
    if len(parts) < 3:
        result["errors"].append("Missing closing ---")
        return result
    
    frontmatter_text = parts[1].strip()
    body = parts[2].strip() if len(parts) > 2 else ""
    
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        if not isinstance(frontmatter, dict):
            result["errors"].append(f"Frontmatter is not a dict")
            return result
        
        result["frontmatter_valid"] = True
        
        if "name" in frontmatter and frontmatter["name"]:
            result["has_name"] = True
            if frontmatter["name"] == skill_name:
                result["name_matches"] = True
            else:
                result["errors"].append(f"Name mismatch: got '{frontmatter['name']}', expected '{skill_name}'")
        else:
            result["errors"].append("Missing 'name'")
        
        if "description" in frontmatter and frontmatter["description"]:
            result["has_description"] = True
        else:
            result["errors"].append("Missing 'description'")
            
    except yaml.YAMLError as e:
        result["errors"].append(f"YAML error: {e}")
    
    # Check body content
    if body and len(body) > 50:
        result["has_instructions"] = True
    else:
        result["errors"].append("Body too short or missing")
    
    # Check for relevant content
    body_lower = body.lower()
    sections_found = []
    for section in expected_sections:
        if section.lower() in body_lower:
            sections_found.append(section)
    
    if sections_found:
        result["has_relevant_content"] = True
        result["sections_found"] = sections_found
    else:
        result["errors"].append(f"No relevant content found (expected: {expected_sections})")
    
    result["valid"] = (
        result["has_frontmatter"] and 
        result["has_name"] and 
        result["has_description"] and 
        result["has_instructions"]
    )
    
    return result


def test_model_with_skill(client, model: str, skill_request: dict, skills_dir: str, skill_creator_instructions: str, acp=None) -> dict:
    """Test if a model can CREATE a skill autonomously."""
    
    skill_name = skill_request["name"]
    task = skill_request["task"]
    expected_sections = skill_request["expected_sections"]
    
    skill_dir = os.path.join(skills_dir, skill_name)
    skill_path = os.path.join(skill_dir, "SKILL.md")
    
    # Clean up previous attempt
    if os.path.exists(skill_dir):
        shutil.rmtree(skill_dir)
    os.makedirs(skill_dir, exist_ok=True)
    
    # Create per-model ACP instance if ACP is enabled
    model_acp = None
    if USE_ACP and acp is None:
        model_short = model.split(':')[0]
        model_acp = ACPPlugin(
            agent_name="AgentNova",
            model_name=model_short,
            debug=DEBUG,
        )
    elif acp:
        model_acp = acp
    
    # Create agent with write_file tool
    tools = make_builtin_registry().subset(["write_file"])
    
    # System prompt includes skill-creator instructions
    system_prompt = f"""You are a skill creator. You create skill files using the write_file tool.

## How to Create Skills

{skill_creator_instructions[:2000]}

## Your Task

Create a skill file at: {skill_path}

The skill must have:
1. YAML frontmatter with 'name' and 'description'
2. Markdown body with instructions

Use the write_file tool to create the file."""

    # Combine step callbacks for verbose and ACP
    def on_step_callback(s):
        if VERBOSE:
            print_step(s, "    ")
        if model_acp:
            model_acp.on_step(s)

    agent = Agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        max_steps=5,
        client=client,
        model_options={
            "temperature": 0.0,      # Deterministic
            "num_ctx": 2048,         # Enough for skill creation
            "num_predict": 1024,     # Enough for skill content
        },
        on_step=on_step_callback,
    )
    
    # PROMPT: Just ask for the skill, DON'T provide content!
    prompt = f"""Create the {skill_name} skill.

Task: {task}

Write a complete SKILL.md file to: {skill_path}

Include:
- YAML frontmatter with name and description
- Instructions in markdown

Call write_file now."""

    start = time.time()
    steps_info = []
    tool_calls = []
    
    try:
        result = agent.run(prompt)
        elapsed = time.time() - start
        
        # Log to ACP
        if model_acp:
            model_acp.log_user_message(prompt)
            model_acp.log_assistant_message(result.final_answer)
        
        # Collect step info
        for s in result.steps:
            if s.type == "tool_call":
                tool_calls.append(s.tool_name)
                steps_info.append({
                    "type": "tool_call",
                    "tool": s.tool_name,
                    "args": dict(s.tool_args or {}),
                })
            elif s.type == "tool_result":
                steps_info.append({
                    "type": "tool_result",
                    "content": str(s.content),
                })
        
        # Check if file was created
        if not os.path.exists(skill_path):
            return {
                "model": model,
                "skill": skill_name,
                "success": False,
                "elapsed": elapsed,
                "steps": len(result.steps),
                "steps_info": steps_info,
                "tool_calls": tool_calls,
                "error": "File not created",
                "final_answer": result.final_answer,
            }
        
        # Read and validate
        with open(skill_path, encoding='utf-8') as f:
            content = f.read()
        
        validation = validate_skill(content, skill_name, expected_sections)
        
        return {
            "model": model,
            "skill": skill_name,
            "success": validation["valid"],
            "elapsed": elapsed,
            "steps": len(result.steps),
            "steps_info": steps_info,
            "tool_calls": tool_calls,
            "file_exists": True,
            "validation": validation,
            "content": content,
            "final_answer": result.final_answer,
        }
            
    except Exception as e:
        elapsed = time.time() - start
        import traceback
        return {
            "model": model,
            "skill": skill_name,
            "success": False,
            "elapsed": elapsed,
            "steps": 0,
            "steps_info": steps_info,
            "tool_calls": tool_calls,
            "error": f"{type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc(),
        }


def main():
    print("⚛️ AgentNova R02.3 - Skill Creator Test (Autonomous Creation)")
    print("=" * 60)
    print("Testing if models can CREATE skills autonomously.")
    print("The skill content is NOT provided - models must generate it!")
    print("Working models: functiongemma:270m, qwen2.5:0.5b, granite4:350m")
    print(f"Verbose: {VERBOSE}, Timeout: {TIMEOUT}s")
    if USE_ACP:
        print(f"ACP: enabled")
    print("=" * 60)
    
    # Initialize ACP if enabled
    main_acp = None
    if USE_ACP:
        main_acp = ACPPlugin(
            agent_name="AgentNova",
            model_name="skill_creator_test",
            debug=DEBUG,
        )
    
    # Load skill-creator instructions
    loader = SkillLoader()
    try:
        skill_creator = loader.load("skill-creator")
        skill_creator_instructions = skill_creator.instructions
        print(f"\n📚 Loaded skill-creator: {len(skill_creator_instructions)} chars")
    except Exception as e:
        print(f"\n⚠️ Could not load skill-creator: {e}")
        print("   Using fallback instructions...")
        skill_creator_instructions = """
Skills have YAML frontmatter with name and description.
The body contains markdown instructions.
Structure:
---
name: skill-name
description: What the skill does
---
# Skill Title
Instructions here.
"""
    
    client = get_default_client()
    
    if not client.is_running():
        print(f"❌ {BACKEND_NAME} is not running!")
        if AGENTNOVA_BACKEND == "bitnet":
            print("   Start llama-server from bitnet.cpp directory")
        else:
            print("   Start with: ollama serve")
        return False
    
    available = client.list_models()
    print(f"\nAvailable models: {len(available)}")
    
    # Find models to test (prefer tool-supporting models)
    models_to_test = []
    for m in PREFERRED_TOOL_MODELS:
        for avail in available:
            if m.split(":")[0] in avail or m in avail:
                if avail not in models_to_test:
                    models_to_test.append(avail)
                    break
    
    # If no preferred models, use any available
    if not models_to_test:
        models_to_test = available[:5]
    
    print(f"Testing order: {models_to_test}")
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    skills_dir = os.path.join(base_dir, "agentnova", "skills")
    
    # Test each skill request with each model until success
    results = []
    all_success = True
    
    for skill_request in SKILL_REQUESTS:
        print(f"\n{'='*60}")
        print(f"🎯 Skill: {skill_request['name']}")
        print(f"   Task: {skill_request['task']}")
        print("=" * 60)
        
        skill_success = False
        
        for model in models_to_test:
            print(f"\n{'='*40}")
            print(f"🧪 Model: {model}")
            print("=" * 40)
            
            result = test_model_with_skill(
                client, model, skill_request, skills_dir, skill_creator_instructions
            )
            results.append(result)
            
            if result.get("success"):
                print(f"\n✅ SUCCESS!")
                print(f"   Time: {result['elapsed']:.1f}s")
                print(f"   Steps: {result['steps']}")
                print(f"   Tools used: {result.get('tool_calls', [])}")
                if result.get("validation"):
                    v = result["validation"]
                    print(f"   Validation: name={v['has_name']}, desc={v['has_description']}, body={v['has_instructions']}")
                    if v.get("sections_found"):
                        print(f"   Relevant sections: {v['sections_found']}")
                if result.get("content"):
                    print(f"\n📄 Created skill ({len(result['content'])} chars):")
                    print("-" * 40)
                    print(result["content"])
                    print("-" * 40)
                skill_success = True
                break
            else:
                print(f"\n❌ Failed")
                if result.get("error"):
                    print(f"   Error: {result['error']}")
                print(f"   Time: {result.get('elapsed', 0):.1f}s")
                print(f"   Steps: {result.get('steps', 0)}")
                print(f"   Tools used: {result.get('tool_calls', [])}")
                if result.get("validation"):
                    v = result["validation"]
                    print(f"   Validation: name={v['has_name']}, desc={v['has_description']}, body={v['has_instructions']}")
                    if v.get("errors"):
                        print(f"   Errors: {v['errors']}")
                if result.get("content"):
                    print(f"   File content ({len(result['content'])} chars):")
                    for line in result["content"].split("\n"):
                        print(f"     {line}")
        
        if not skill_success:
            all_success = False
            print(f"\n❌ No model could create skill: {skill_request['name']}")
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print("=" * 60)
    
    for r in results:
        status = "✅" if r.get("success") else "❌"
        time_str = f"{r.get('elapsed', 0):.1f}s"
        tools = r.get("tool_calls", [])
        tools_str = f" [{', '.join(tools)}]" if tools else ""
        skill = r.get("skill", "?")
        print(f"\n  {status} {r['model']:<35} {skill:<20} {time_str:>8}{tools_str}")
        
        if r.get("error") and not r.get("success"):
            print(f"      Error: {r['error']}")
        if r.get("validation"):
            v = r["validation"]
            print(f"      Validation: name={v['has_name']}, desc={v['has_description']}, body={v['has_instructions']}")
            if v.get("errors"):
                print(f"      Errors: {v['errors']}")
    
    # Check final results
    print(f"\n{'='*60}")
    print("📁 Final Skill Files")
    print("=" * 60)
    
    for skill_request in SKILL_REQUESTS:
        skill_path = os.path.join(skills_dir, skill_request["name"], "SKILL.md")
        if os.path.exists(skill_path):
            with open(skill_path, encoding='utf-8') as f:
                content = f.read()
            print(f"\n✅ {skill_request['name']}/SKILL.md ({len(content)} chars)")
        else:
            print(f"\n❌ {skill_request['name']}/SKILL.md - NOT CREATED")
    
    if not all_success:
        print("\n💡 Tips:")
        print("   - Use functiongemma:270m, qwen2.5:0.5b, or granite4:350m")
        print("   - These models support native tool calling")
        print("   - Increase timeout: AGENTNOVA_TIMEOUT=300")
        print("   - Enable verbose: AGENTNOVA_VERBOSE=1")
    
    return all_success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
