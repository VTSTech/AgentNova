"""
⚛️ AgentNova R02 — Enhanced Orchestrator with Parallel Execution

Enhanced orchestrator with:
  • True parallel execution mode (all agents run simultaneously)
  • Result merging with attribution
  • ACP integration for multi-agent tracking
  • Timeout handling per agent
  • Fault tolerance (continue if one agent fails)

Written by VTSTech — https://www.vts-tech.org
"""

from __future__ import annotations

import concurrent.futures
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from .agent import Agent, AgentRun
from .tools import ToolRegistry


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT CARD
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AgentCard:
    """
    Describes an agent in the orchestrator.
    
    Parameters
    ----------
    name : str
        Unique identifier for this agent
    agent : Agent
        The AgentNova Agent instance
    description : str
        What this agent specializes in (used for routing)
    tools : ToolRegistry | None
        Optional tools subset for this agent (overrides agent's tools)
    priority : int
        Priority for routing (higher = more likely to be chosen)
    timeout : float
        Maximum seconds this agent can run (default: 60)
    fallback : bool
        If True, this agent runs when others fail
    """
    name: str
    agent: Agent
    description: str
    tools: ToolRegistry | None = None
    priority: int = 1
    timeout: float = 60.0
    fallback: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR RESULT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class OrchestratorResult:
    """Result from orchestrator execution."""
    mode: str  # "router" | "pipeline" | "parallel"
    chosen_agent: str | None = None  # For router mode
    agents_used: list[str] = field(default_factory=list)
    final_answer: str = ""
    agent_results: dict[str, str] = field(default_factory=dict)  # agent_name -> result
    agent_times: dict[str, float] = field(default_factory=dict)  # agent_name -> seconds
    total_ms: float = 0.0
    success: bool = True
    error: str = ""
    
    def print_summary(self):
        """Print a summary of the orchestration."""
        print(f"\n{'='*60}")
        print(f"ORCHESTRATOR RESULT ({self.mode} mode)")
        print(f"{'='*60}")
        print(f"Agents used: {', '.join(self.agents_used)}")
        if self.chosen_agent:
            print(f"Primary agent: {self.chosen_agent}")
        for agent_name, result in self.agent_results.items():
            elapsed = self.agent_times.get(agent_name, 0)
            preview = result[:100] + "..." if len(result) > 100 else result
            print(f"\n[{agent_name}] ({elapsed:.1f}s):")
            print(f"  {preview}")
        print(f"\nTotal time: {self.total_ms/1000:.1f}s")
        print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

class Orchestrator:
    """
    Multi-agent orchestrator with three execution modes.
    
    Modes:
    -------
    router : Router model picks the best agent for the task
    pipeline : Agents run sequentially, each receives previous output
    parallel : All agents run simultaneously, results merged
    
    Parameters
    ----------
    agents : list[AgentCard]
        List of agent cards describing available agents
    router_model : str | None
        Model to use for routing decisions (required for router mode)
    mode : str
        Execution mode: "router", "pipeline", or "parallel"
    on_step : Callable | None
        Callback for step events (ACP integration)
    merge_strategy : str
        How to combine parallel results: "concat", "first", "vote", "best"
    timeout : float
        Global timeout for entire orchestration (seconds)
    """
    
    def __init__(
        self,
        agents: list[AgentCard],
        router_model: str | None = None,
        mode: Literal["router", "pipeline", "parallel"] = "router",
        on_step: Callable | None = None,
        merge_strategy: Literal["concat", "first", "vote", "best"] = "concat",
        timeout: float = 120.0,
    ):
        self.agents = {a.name: a for a in agents}
        self.agent_list = agents
        self.router_model = router_model
        self.mode = mode
        self.on_step = on_step
        self.merge_strategy = merge_strategy
        self.timeout = timeout
        
        # Thread-local storage for ACP integration
        self._thread_local = threading.local()
        self._lock = threading.Lock()
    
    def run(self, user_input: str) -> OrchestratorResult:
        """
        Run the orchestrator on user input.
        
        Dispatches to the appropriate mode handler.
        """
        start_time = time.perf_counter()
        
        result = OrchestratorResult(mode=self.mode)
        
        try:
            if self.mode == "router":
                result = self._run_router(user_input, result)
            elif self.mode == "pipeline":
                result = self._run_pipeline(user_input, result)
            elif self.mode == "parallel":
                result = self._run_parallel(user_input, result)
            else:
                result.error = f"Unknown mode: {self.mode}"
                result.success = False
        except Exception as e:
            result.error = str(e)
            result.success = False
        
        result.total_ms = (time.perf_counter() - start_time) * 1000
        return result
    
    # ------------------------------------------------------------------ #
    #  ROUTER MODE                                                        #
    # ------------------------------------------------------------------ #
    
    def _run_router(self, user_input: str, result: OrchestratorResult) -> OrchestratorResult:
        """
        Use router model to pick the best agent for the task.
        """
        if not self.router_model:
            # Fallback: pick first agent
            chosen = self.agent_list[0].name
        else:
            chosen = self._select_agent_with_llm(user_input)
        
        result.chosen_agent = chosen
        result.agents_used = [chosen]
        
        # Run the chosen agent
        card = self.agents[chosen]
        start = time.perf_counter()
        
        try:
            run = card.agent.run(user_input)
            result.final_answer = run.final_answer
            result.agent_results[chosen] = run.final_answer
            result.agent_times[chosen] = time.perf_counter() - start
            result.success = run.success
        except Exception as e:
            result.agent_results[chosen] = f"[Error] {e}"
            result.agent_times[chosen] = time.perf_counter() - start
            result.success = False
            
            # Try fallback agents if available
            for fallback_card in self.agent_list:
                if fallback_card.fallback and fallback_card.name != chosen:
                    try:
                        run = fallback_card.agent.run(user_input)
                        result.final_answer = run.final_answer
                        result.agent_results[fallback_card.name] = run.final_answer
                        result.agents_used.append(fallback_card.name)
                        result.success = True
                        break
                    except:
                        continue
        
        return result
    
    def _select_agent_with_llm(self, user_input: str) -> str:
        """
        Use the router model to select the best agent.
        
        Returns the name of the selected agent.
        """
        from .core.ollama_client import OllamaClient
        
        client = OllamaClient()
        
        # Build agent descriptions
        agent_descs = "\n".join(
            f"- {card.name}: {card.description}"
            for card in self.agent_list
        )
        
        router_prompt = f"""You are an agent router. Select the best agent for this task.

Available agents:
{agent_descs}

User request: {user_input}

Reply with ONLY the agent name (nothing else). Pick the most suitable agent."""

        try:
            response = client.chat(
                model=self.router_model,
                messages=[{"role": "user", "content": router_prompt}],
                options={"num_predict": 20, "temperature": 0.1}
            )
            content = response.get("message", {}).get("content", "").strip().lower()
            
            # Match to agent names
            for name in self.agents:
                if name.lower() in content:
                    return name
            
            # Fallback to first
            return self.agent_list[0].name
            
        except Exception:
            return self.agent_list[0].name
    
    # ------------------------------------------------------------------ #
    #  PIPELINE MODE                                                      #
    # ------------------------------------------------------------------ #
    
    def _run_pipeline(self, user_input: str, result: OrchestratorResult) -> OrchestratorResult:
        """
        Run agents sequentially, each receiving the previous output.
        """
        current_input = user_input
        accumulated_results = []
        
        for card in self.agent_list:
            start = time.perf_counter()
            
            # Include previous results in context
            if accumulated_results:
                enhanced_input = f"{current_input}\n\n[Previous output: {accumulated_results[-1]}]"
            else:
                enhanced_input = current_input
            
            try:
                run = card.agent.run(enhanced_input)
                agent_result = run.final_answer
                result.success = run.success
            except Exception as e:
                agent_result = f"[Error in {card.name}]: {e}"
                result.success = False
            
            elapsed = time.perf_counter() - start
            result.agent_results[card.name] = agent_result
            result.agent_times[card.name] = elapsed
            result.agents_used.append(card.name)
            accumulated_results.append(agent_result)
        
        # Final answer is the last agent's output
        result.final_answer = accumulated_results[-1] if accumulated_results else ""
        
        return result
    
    # ------------------------------------------------------------------ #
    #  PARALLEL MODE                                                      #
    # ------------------------------------------------------------------ #
    
    def _run_parallel(self, user_input: str, result: OrchestratorResult) -> OrchestratorResult:
        """
        Run all agents in parallel and merge results.
        """
        results_map = {}
        times_map = {}
        errors_map = {}
        
        def run_single_agent(card: AgentCard):
            """Run a single agent and store result."""
            start = time.perf_counter()
            try:
                run = card.agent.run(user_input)
                with self._lock:
                    results_map[card.name] = run.final_answer
                    times_map[card.name] = time.perf_counter() - start
            except Exception as e:
                with self._lock:
                    errors_map[card.name] = str(e)
                    times_map[card.name] = time.perf_counter() - start
        
        # Run all agents concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.agent_list)) as executor:
            futures = [executor.submit(run_single_agent, card) for card in self.agent_list]
            
            # Wait for all with timeout
            done, not_done = concurrent.futures.wait(
                futures, 
                timeout=self.timeout,
                return_when=concurrent.futures.ALL_COMPLETED
            )
            
            # Cancel any still running
            for future in not_done:
                future.cancel()
        
        # Collect results
        for card in self.agent_list:
            if card.name in results_map:
                result.agent_results[card.name] = results_map[card.name]
                result.agents_used.append(card.name)
            elif card.name in errors_map:
                result.agent_results[card.name] = f"[Error] {errors_map[card.name]}"
            result.agent_times[card.name] = times_map.get(card.name, 0)
        
        # Merge results according to strategy
        result.final_answer = self._merge_results(results_map)
        result.success = len(results_map) > 0
        
        return result
    
    def _merge_results(self, results: dict[str, str]) -> str:
        """
        Merge parallel results according to strategy.
        """
        if not results:
            return "[No results from any agent]"
        
        if self.merge_strategy == "first":
            return list(results.values())[0]
        
        elif self.merge_strategy == "concat":
            parts = []
            for name, output in results.items():
                parts.append(f"[{name}]:\n{output}")
            return "\n\n---\n\n".join(parts)
        
        elif self.merge_strategy == "vote":
            # Simple voting: most common answer wins
            from collections import Counter
            # Normalize and count
            normalized = [r.strip().lower()[:100] for r in results.values()]
            counts = Counter(normalized)
            most_common = counts.most_common(1)[0][0]
            # Return original (non-normalized) version
            for r in results.values():
                if r.strip().lower()[:100] == most_common:
                    return r
            return list(results.values())[0]
        
        elif self.merge_strategy == "best":
            # Pick longest substantive answer
            best = max(results.values(), key=lambda x: len(x.strip()))
            return best
        
        else:
            return list(results.values())[0]
