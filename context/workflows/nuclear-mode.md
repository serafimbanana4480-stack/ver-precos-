---
description: Nuclear Mode - Ultimate autonomous project execution with multi-agent orchestration, parallel phase execution, intelligent dependency resolution, comprehensive quality gates, and real-time progress tracking
---

# Nuclear Mode Workflow

**Purpose:** Execute entire project milestones with maximum autonomy and sophistication. Combines autonomous phase execution, intelligent parallel orchestration, comprehensive quality gates, and advanced multi-agent coordination patterns from cutting-edge AI orchestration research.

## Core Principles

1. **Maximum Parallelism**: Execute independent phases in parallel using intelligent dependency analysis
2. **Comprehensive Quality Gates**: Verification, code review, security, UI review at every phase
3. **Intelligent Recovery**: Auto-retry with exponential backoff, fallback strategies, and graceful degradation
4. **Real-Time Orchestration**: Dashboard with live progress, agent coordination, and adaptive scheduling
5. **Multi-Agent Coordination**: Advanced patterns from multi-agent orchestration research (handoffs, shared state, conflict resolution)

## When to Use Nuclear Mode

- Complex milestones with 10+ phases
- Projects requiring maximum execution speed
- Scenarios where comprehensive quality gates are mandatory
- Teams comfortable with autonomous execution
- Production-grade deployments requiring full validation

## Nuclear Mode Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NUCLEAR MODE INIT                         │
│  Project analysis → Dependency graph → Execution plan       │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
   │ TRACK 1 │       │ TRACK 2 │       │ TRACK N │
   │ Phase 1 │       │ Phase 3 │       │ Phase 5 │
   │ → 2 → 4 │       │ → 6 → 8 │       │ → 7 → 9 │
   └────┬────┘       └────┬────┘       └────┬────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
              ┌────────────▼────────────┐
              │  ORCHESTRATION LAYER     │
              │  - Dependency tracking   │
              │  - Conflict resolution   │
              │  - Resource scheduling   │
              │  - Error recovery        │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   QUALITY GATES HUB     │
              │  - Verification         │
              │  - Code review          │
              │  - Security scan        │
              │  - UI review            │
              │  - Integration test      │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │     DASHBOARD           │
              │  Real-time progress     │
              │  Agent status           │
              │  Resource utilization   │
              │  Risk indicators        │
              └─────────────────────────┘
```

## Execution Steps

### Step 1: Initialization & Analysis

```bash
# Bootstrap nuclear mode
INIT=$(node "$HOME/.codeium/windsurf/get-shit-done/bin/gsd-tools.cjs" init nuclear-mode)
if [[ "$INIT" == @file:* ]]; then INIT=$(cat "${INIT#@file:}"); fi
```

**Parse from INIT:**
- `milestone_version`, `milestone_name`, `phase_count`
- `phases[]` with dependencies, complexity estimates
- `resource_profile` (available models, token budget)
- `quality_gate_config` (which gates enabled)
- `parallelism_config` (max concurrent agents, worktree strategy)

**Display nuclear mode banner:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ☢ NUCLEAR MODE ☢ — Ultimate Autonomous Execution
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 Milestone: {version} — {name}
 Phases: {phase_count} | Tracks: {track_count}
 Quality Gates: {gates_enabled}
 Max Parallel Agents: {max_parallel}
 Estimated Duration: {time_estimate}

 ⚠ Autonomous execution with comprehensive quality gates
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 2: Dependency Graph Analysis

**Build execution graph:**

```bash
# Analyze phase dependencies
GRAPH=$(node "$HOME/.codeium/windsurf/get-shit-done/bin/gsd-tools.cjs" dependency-analyze)
```

**Output:**
- Dependency matrix (which phases depend on which)
- Critical path identification
- Parallel execution tracks (independent phase groups)
- Risk assessment (high-risk phases, potential bottlenecks)

**Display execution plan:**
```
┌─────────────────────────────────────────────────────────────┐
│              EXECUTION GRAPH ANALYSIS                       │
├─────────────────────────────────────────────────────────────┤
│ Tracks: 3 parallel execution tracks                         │
│ Critical Path: 8 phases (estimated 4.2 hours)              │
│ Risk Factors: 2 high-complexity phases identified          │
├─────────────────────────────────────────────────────────────┤
│ Track 1: Phase 1 → 2 → 4 → 7 → 10                          │
│ Track 2: Phase 3 → 5 → 8 → 11                               │
│ Track 3: Phase 6 → 9 → 12 → 13                              │
├─────────────────────────────────────────────────────────────┤
│ Dependencies:                                               │
│   Phase 5 depends on: 1, 2                                 │
│   Phase 8 depends on: 3, 4                                 │
│   Phase 12 depends on: 7, 9                                │
└─────────────────────────────────────────────────────────────┘
```

### Step 3: Resource Allocation & Scheduling

**Allocate agents per track:**
- Each track gets dedicated executor agents
- Planner agents pooled and scheduled dynamically
- Quality gate agents (verifier, reviewer, security) shared across tracks
- Dashboard agent orchestrates everything

**Set adaptive scheduling:**
- High-priority phases get more resources
- Complex phases get larger context windows
- Risky phases get additional verification passes
- Bottleneck phases get pre-fetching of dependencies

### Step 4: Parallel Phase Execution

**For each track, execute phases in sequence:**

```bash
# Spawn track orchestrator (one per track)
Task(
  description="Nuclear Mode Track {track_num}",
  run_in_background=true,
  prompt="
    You are the Track {track_num} orchestrator in Nuclear Mode.
    
    Your responsibility: Execute phases [{phase_list}] in sequence
    while coordinating with other tracks via the orchestration layer.
    
    Track phases: {phase_list}
    Dependencies: {track_dependencies}
    
    For each phase:
    1. Wait for dependencies to complete (check orchestration layer)
    2. Run discuss-phase (if context not gathered)
    3. Run plan-phase with --auto flag
    4. Run execute-phase with --no-transition
    5. Run quality gates (verification, code-review, security, ui-review)
    6. Report completion to orchestration layer
    7. Proceed to next phase
    
    Quality gate sequence:
    - /gsd-verify-work (UAT verification)
    - /gsd-code-review (code quality)
    - /gsd-code-review-fix --auto (auto-fix issues)
    - /gsd-secure-phase (security threats)
    - /gsd-ui-review (frontend phases only)
    
    Error handling:
    - On verification failure: retry once, then escalate
    - On code review issues: auto-fix, re-verify
    - On security threats: block, report to dashboard
    - On dependency delay: wait with exponential backoff
    
    Communicate all status updates to orchestration layer via:
    node \"$HOME/.codeium/windsurf/get-shit-done/bin/gsd-tools.cjs\" nuclear-update
  "
)
```

**Orchestration layer coordinates:**
- Dependency satisfaction tracking
- Conflict detection (file modifications across tracks)
- Resource allocation adjustments
- Progress aggregation for dashboard

### Step 5: Real-Time Dashboard

**Dashboard updates every 30 seconds:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ☢ NUCLEAR MODE DASHBOARD ☢
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 Progress: ████████████░░░░░░░ 60% (8/13 phases)
 Elapsed: 2h 34m | Remaining: ~1h 45m | ETA: 4:19 PM
 
┌─────────────────────────────────────────────────────┐
│ TRACK STATUS                                          │
├─────────────────────────────────────────────────────┤
│ Track 1: ████████████░░░ 80% (4/5)  ◆ Executing P7 │
│ Track 2: ████████░░░░░░░ 50% (2/4)  ○ Waiting for P4│
│ Track 3: █████████░░░░░░ 60% (2/3)  ◆ Executing P9 │
├─────────────────────────────────────────────────────┤
│ AGENT POOL                                           │
│   Active: 6/8 agents | Idle: 2                         │
│   Planner: 2/3 | Executor: 3/4 | Verifier: 1/1       │
├─────────────────────────────────────────────────────┤
│ QUALITY GATES                                         │
│   Verification: ✓ 8 passed | ○ 2 pending | ✗ 0 failed│
│   Code Review: ✓ 7 passed | ○ 3 pending              │
│   Security: ✓ 8 scanned | ○ 2 pending               │
│   UI Review: ✓ 4 passed | ○ 1 pending               │
├─────────────────────────────────────────────────────┤
│ RISK INDICATORS                                      │
│   ⚠ Phase 7: High complexity (dependency chain)     │
│   ⚠ Track 2: Blocked on Phase 4 completion         │
│   ✓ All security scans passing                       │
└─────────────────────────────────────────────────────┘

 Recent Events:
   [14:32] ✓ Phase 6 complete - Track 3 proceeding
   [14:28] ✓ Phase 4 complete - Track 1 unblocked
   [14:25] ⚠ Phase 7 retry 1/2 - verification gap found
   [14:20] ✓ Security scan passed - Phase 3
```

### Step 6: Intelligent Error Recovery

**Automatic recovery strategies:**

1. **Verification Gaps:**
   - Auto-spawn gap closure planning
   - Re-execute with gap plans
   - Max 2 retries before escalation

2. **Code Review Issues:**
   - Auto-invoke code-review-fix
   - Re-verify after fixes
   - Continue if issues are non-blocking

3. **Security Threats:**
   - Block immediately (configurable)
   - Generate threat report
   - Wait for user decision (auto-mode: skip phase)

4. **Dependency Delays:**
   - Exponential backoff (10s, 30s, 90s)
   - Pre-fetch dependencies when possible
   - Re-schedule if delay exceeds threshold

5. **File Conflicts:**
   - Detect cross-track file modifications
   - Auto-serialize conflicting phases
   - Re-parallelize after conflict resolved

### Step 7: Quality Gates Execution

**Comprehensive gate sequence per phase:**

```bash
# After execute-phase completes, run all quality gates

# 1. Verification
Skill(skill="gsd-verify-work", args="${PHASE}")

# 2. Code Review
Skill(skill="gsd-code-review", args="${PHASE}")

# 3. Auto-fix if issues found
if [ "$REVIEW_STATUS" != "clean" ]; then
  Skill(skill="gsd-code-review-fix", args="${PHASE} --auto")
fi

# 4. Security Scan (if enabled)
if [ "$SECURITY_ENABLED" = "true" ]; then
  Skill(skill="gsd-secure-phase", args="${PHASE}")
fi

# 5. UI Review (if frontend phase)
if [ "$HAS_UI" = "true" ]; then
  Skill(skill="gsd-ui-review", args="${PHASE}")
fi

# 6. Integration Test (if dependent phases complete)
Skill(skill="gsd-integration-check", args="${PHASE}")
```

### Step 8: Milestone Completion

**When all tracks complete:**

```bash
# Run milestone-level quality gates
Skill(skill="gsd-audit-milestone")
Skill(skill="gsd-verify-work")  # Full system verification

# Generate completion report
REPORT=$(node "$HOME/.codeium/windsurf/get-shit-done/bin/gsd-tools.cjs" nuclear-report)

# Display final summary
```

**Final dashboard:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 ☢ NUCLEAR MODE COMPLETE ☢
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 Milestone: {version} — {name}
 Duration: 4h 12m | Phases: 13/13 complete
 
┌─────────────────────────────────────────────────────┐
│ EXECUTION SUMMARY                                     │
├─────────────────────────────────────────────────────┤
│ Total Phases: 13                                     │
│ Successful: 13                                        │
│ Retries: 3 (auto-recovered)                          │
│ Escalations: 0                                        │
├─────────────────────────────────────────────────────┤
│ QUALITY GATES SUMMARY                                 │
│   Verification: 13/13 passed ✓                       │
│   Code Review: 13/13 passed ✓                        │
│   Security: 13/13 scanned ✓                           │
│   UI Review: 5/5 passed ✓                            │
│   Integration: 13/13 passed ✓                        │
├─────────────────────────────────────────────────────┤
│ RESOURCE UTILIZATION                                 │
│   Total Agent Hours: 24.3                            │
│   Token Usage: 1.2M tokens                           │
│   Parallel Efficiency: 87% (vs sequential)          │
│   Cost Savings: ~$42 (vs sequential execution)       │
├─────────────────────────────────────────────────────┤
│ NEXT STEPS                                           │
│   → /gsd-ship (create PR)                            │
│   → /gsd-complete-milestone (archive)                 │
│   → Manual deployment verification                   │
└─────────────────────────────────────────────────────┘

 Report saved to: .planning/nuclear-report-{timestamp}.md
```

## Advanced Features

### Adaptive Parallelism

- **Dynamic track allocation**: Add/remove tracks based on phase complexity
- **Resource-aware scheduling**: Larger models for complex phases
- **Load balancing**: Redistribute phases if track imbalance detected

### Predictive Scheduling

- **Pre-fetch dependencies**: Start dependent phases early when safe
- **Risk-based prioritization**: Execute high-risk phases when more resources available
- **Bottleneck prediction**: Identify and pre-empt potential delays

### Multi-Agent Coordination Patterns

1. **Handoff Protocol**: Clean state transfer between agents
2. **Shared State Management**: Coordinated STATE.md updates
3. **Conflict Resolution**: File modification arbitration
4. **Deadlock Prevention**: Dependency cycle detection and breaking

### Observability

- **Detailed logs**: Per-agent execution logs with timestamps
- **Performance metrics**: Token usage, duration, efficiency
- **Risk dashboard**: Real-time risk indicators and mitigation
- **Replay capability**: Reconstruct execution sequence for debugging

## Configuration

**Enable nuclear mode in `.planning/config.json`:**

```json
{
  "nuclear_mode": {
    "enabled": true,
    "max_parallel_tracks": 4,
    "max_agents_per_track": 2,
    "quality_gates": {
      "verification": true,
      "code_review": true,
      "security": true,
      "ui_review": true,
      "integration_check": true
    },
    "error_recovery": {
      "max_retries": 2,
      "retry_backoff": "exponential",
      "escalation_threshold": 3
    },
    "adaptive_scheduling": {
      "enabled": true,
      "pre_fetch_dependencies": true,
      "risk_based_prioritization": true
    },
    "observability": {
      "log_level": "detailed",
      "metrics_collection": true,
      "dashboard_refresh_interval": 30
    }
  }
}
```

## Usage

```bash
# Run nuclear mode for entire milestone
/gsd-nuclear-mode

# Run with specific track configuration
/gsd-nuclear-mode --tracks 3 --max-agents 8

# Run with quality gate customization
/gsd-nuclear-mode --skip-security --skip-ui-review

# Run in dry-run mode (simulation only)
/gsd-nuclear-mode --dry-run

# Resume from checkpoint
/gsd-nuclear-mode --resume
```

## Safety Features

- **Checkpoint system**: Save state after each phase for resume capability
- **Rollback capability**: Revert to last known good state on critical failure
- **Manual override**: Pause execution at any point for human intervention
- **Resource limits**: Token budget and time limits to prevent runaway execution
- **Conflict detection**: Prevent data corruption from parallel writes

## Comparison to Standard GSD

| Feature | Standard GSD | Nuclear Mode |
|---------|-------------|--------------|
| Phase Execution | Sequential | Parallel tracks |
| Quality Gates | Manual/opt-in | All gates automatic |
| Error Recovery | Manual | Auto-retry with escalation |
| Progress Tracking | Basic | Real-time dashboard |
| Resource Utilization | Single agent | Multi-agent pool |
| Scheduling | Fixed | Adaptive |
| Observability | Limited | Comprehensive |
| Execution Speed | Baseline | 2-4x faster (parallel) |
| Token Efficiency | Baseline | 1.5-2x better (shared context) |

## Best Practices

1. **Start with dry-run**: Use `--dry-run` to preview execution plan
2. **Monitor dashboard**: Watch for risk indicators and adjust as needed
3. **Review reports**: Check nuclear-report.md for insights and optimization opportunities
3. **Tune configuration**: Adjust parallelism and quality gates based on project needs
4. **Use checkpoints**: Enable checkpoint system for long-running milestones
5. **Test incrementally**: Run nuclear mode on smaller milestones first

## Troubleshooting

**Track stuck waiting:**
- Check dependency status in dashboard
- Verify dependent phases actually completed
- Manual intervention: `/gsd-nuclear-mode --force-phase N`

**Quality gate failures:**
- Review specific gate logs in `.planning/nuclear-logs/`
- Adjust gate configuration if too strict
- Manual fix: Run individual gate command with `--force`

**Resource exhaustion:**
- Reduce `max_parallel_tracks` in config
- Enable `token_budget` limits
- Switch to smaller models for non-critical phases

**File conflicts:**
- Check dashboard conflict detection
- Review conflict resolution strategy
- Manual resolution: Edit conflicting files, resume

## Integration with Other GSD Commands

Nuclear mode orchestrates these GSD commands:
- `/gsd-discuss-phase` (per phase, if context needed)
- `/gsd-plan-phase` (with `--auto` flag)
- `/gsd-execute-phase` (with `--no-transition`)
- `/gsd-verify-work` (verification gate)
- `/gsd-code-review` (code quality gate)
- `/gsd-code-review-fix` (auto-fix)
- `/gsd-secure-phase` (security gate)
- `/gsd-ui-review` (UI quality gate)
- `/gsd-audit-milestone` (milestone-level audit)
- `/gsd-ship` (optional PR creation)

## Future Enhancements

- **ML-based scheduling**: Learn optimal execution patterns from history
- **Predictive risk assessment**: ML model to predict phase failures
- **Dynamic resource scaling**: Auto-scale agent pool based on workload
- **Cross-milestone optimization**: Plan multiple milestones together
- **Integration with CI/CD**: Direct deployment pipeline integration
