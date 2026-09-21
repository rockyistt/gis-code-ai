# Planner Specialist Architecture

## Goal

The Planner Agent is now split into multiple planning specialists. The Planner Agent still owns the final planning loop, but candidate generation is delegated to smaller strategy components.

This keeps planning explainable without turning every sub-planner into a full LangGraph node too early.

## Current Structure

```text
PlannerAgent
  |
  |-- Intent parsing
  |
  |-- CandidateProvider
        |
        |-- TopologyCascadePlanner
        |-- CrudLifecyclePlanner
        |-- ValidationPlanner
        |-- UiNavigationPlanner
        |-- HistoricalPatternPlanner
  |
  |-- Candidate merge/ranking
  |
  |-- Auto selection or human choice
  |
  |-- StepIntent plan
```

## Planning Specialists

### TopologyCascadePlanner

Focus:

```text
Create parent object -> Create downstream child object
```

Example:

```text
Create E MS Installatie FP
-> Create E MS Rail FP
```

This planner is responsible for physical or spatial topology paths.

### CrudLifecyclePlanner

Focus:

```text
Create -> Update -> Delete
```

Example:

```text
Create E MS Installatie FP
-> Update E MS Installatie FP
-> Delete E MS Installatie FP
```

This planner is responsible for lifecycle-completion test cases.

### ValidationPlanner

Focus:

```text
Run consistency check / datamodel check
```

Example:

```text
Datamodel Check Elektra;Catalogus
```

This planner recommends validation/check steps.

### UiNavigationPlanner

Focus:

```text
Switch view / UI navigation / screen context movement
```

Example:

```text
Switch Stationsschema
```

This planner is the home for UI-level actions. Future examples include tab selection and button operations.

### HistoricalPatternPlanner

Focus:

```text
Use real adjacent-step transitions mined from historical workflows
```

Example:

```text
After Create E MS Installatie FP:
  Datamodel Check Elektra;Catalogus support=8
  Open Object E MS Rail FP support=4
  Click Oneshot Button delete support=3
```

This planner gives data-driven evidence from the original workflow corpus.

## Why This Is Better

Before:

```text
CandidateProvider = topology rules + history mixed together
```

After:

```text
CandidateProvider = planning specialists + merge/ranking
```

Benefits:

- each candidate has a clear planning owner
- planning behavior is easier to explain
- future harness metrics can measure specialist quality separately
- we can later promote a specialist into a LangGraph sub-agent if needed
- UI actions and CRUD actions no longer look like the same kind of decision

## Example Menu Output

```text
1. [Create] E MS Rail FP
   source=topology_cascade planner=TopologyCascadePlanner

2. [Update] E MS Installatie FP
   source=crud_lifecycle planner=CrudLifecyclePlanner

4. [Run] datamodel_check
   source=validation_check planner=ValidationPlanner

5. [Switch] Stationsschema
   source=ui_navigation planner=UiNavigationPlanner

10. [Click Oneshot Button] delete
    source=history planner=HistoricalPatternPlanner support=3
```

## Future Direction

For now, specialists are strategy classes inside the Planner Agent. This is intentionally lightweight.

Later, if one specialist becomes complex enough, it can become a full sub-agent or LangGraph node:

```text
PlannerAgent
  -> CrudPlanningAgent
  -> TopologyPlanningAgent
  -> UiPlanningAgent
  -> ValidationPlanningAgent
  -> CandidateRankerAgent
```

The current implementation keeps that path open without adding unnecessary graph complexity today.
