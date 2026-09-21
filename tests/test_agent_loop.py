import copy

from src.agents import (
    CandidateProvider,
    ContextManagerAgent,
    Finding,
    HarnessCase,
    RAGReranker,
    ValidatorAgent,
    RepairAgent,
    WorkflowHarness,
    WorkflowLoop,
    WorkflowState,
    classify_validation_failure,
)


def test_workflow_loop_runs_multiple_agents():
    loop = WorkflowLoop(max_steps=4, max_repair_iterations=1)
    state = loop.run("Create E MS Installatie FP")

    assert state.status == "ready"
    assert state.workflow["total_steps"] == 4
    assert len(state.workflow["steps"]) == 4
    assert not state.error_findings()

    trace_agents = {trace.agent for trace in state.traces}
    assert "PlannerAgent" in trace_agents
    assert "GeneratorAgent" in trace_agents
    assert "ValidatorAgent" in trace_agents
    assert "ReviewerAgent" in trace_agents


def test_repair_agent_fixes_recoverable_schema_errors():
    loop = WorkflowLoop(max_steps=2)
    state = loop.run("Create E MS Installatie FP")
    broken_workflow = copy.deepcopy(state.workflow)
    broken_workflow["total_steps"] = 99
    broken_workflow["steps"][0]["step_index"] = 42
    broken_workflow["steps"][0]["object_id"] = "Passed"

    broken_state = WorkflowState(prompt="repair", workflow=broken_workflow)
    validator = ValidatorAgent()
    repairer = RepairAgent()

    invalid_state = validator.run(broken_state)
    assert invalid_state.error_findings()

    repaired_state = repairer.run(invalid_state)
    repaired_state.findings = []
    validated_state = validator.run(repaired_state)

    assert validated_state.status == "validated"
    assert not validated_state.error_findings()
    assert validated_state.workflow["total_steps"] == len(validated_state.workflow["steps"])
    assert validated_state.workflow["steps"][0]["step_index"] == 0
    assert validated_state.workflow["steps"][0]["object_id"] != "Passed"


def test_workflow_harness_reports_pass_rate():
    harness = WorkflowHarness(WorkflowLoop(max_steps=3))
    summary = harness.run_cases(
        [
            HarnessCase(
                name="substation cascade",
                prompt="Create E MS Installatie FP",
                min_steps=3,
                required_objects=["E MS Installatie FP", "E MS Rail FP"],
                required_methods=["Create"],
            )
        ]
    )

    assert summary["total"] == 1
    assert summary["passed"] == 1
    assert summary["pass_rate"] == 1.0


def test_candidate_provider_uses_planning_specialists():
    provider = CandidateProvider()
    candidates = provider.get_candidates("E MS Installatie FP", "Create")

    by_type = {candidate["type"]: candidate for candidate in candidates}
    assert by_type["physical_cascade"]["planner"] == "TopologyCascadePlanner"
    assert by_type["lifecycle_update"]["planner"] == "CrudLifecyclePlanner"
    assert by_type["datamodel_check"]["planner"] == "ValidationPlanner"
    assert by_type["switch_view"]["planner"] == "UiNavigationPlanner"

    history_candidates = [
        candidate for candidate in candidates if candidate["source"] == "history"
    ]
    assert history_candidates
    assert history_candidates[0]["planner"] == "HistoricalPatternPlanner"


def test_planner_trace_records_specialist_metadata():
    loop = WorkflowLoop(max_steps=2)
    state = loop.run("Create E MS Installatie FP")

    planner_trace = [trace for trace in state.traces if trace.agent == "PlannerAgent"][-1]
    first_menu = planner_trace.metadata["decisions"][0]["menu"]

    assert any(item.get("planner") == "TopologyCascadePlanner" for item in first_menu)
    assert any(item.get("planning_category") == "crud_lifecycle" for item in first_menu)


def test_context_manager_keeps_only_true_gis_instruction_from_long_prompt():
    prompt = (
        "Please summarize the weekly report for tomorrow. "
        "Also send an email to the team. "
        "For the GIS validation, create E MS Kabel in elektra. "
        "Finally prepare a slide for the meeting."
    )
    state = WorkflowState(prompt=prompt)

    state = ContextManagerAgent().run(state)

    assert state.condensed_prompt == "Create E MS Kabel"
    assert len(state.context_intents) == 1
    assert state.context_intents[0].method == "Create"
    assert state.context_intents[0].object == "E MS Kabel"


def test_context_manager_preserves_multiple_gis_intents():
    prompt = (
        "Create E MS Installatie FP. "
        "Then update E MS Installatie FP. "
        "Ignore the presentation notes."
    )
    state = WorkflowState(prompt=prompt)

    state = ContextManagerAgent().run(state)

    assert [intent.method for intent in state.context_intents] == ["Create", "Update"]
    assert [intent.object for intent in state.context_intents] == [
        "E MS Installatie FP",
        "E MS Installatie FP",
    ]


def test_noisy_single_gis_instruction_does_not_expand_to_default_cascade():
    prompt = "Hello model. Now I want to test the Agent framework by generating a MS cable"
    state = WorkflowLoop(max_steps=5).run(prompt)

    assert state.status == "ready"
    assert state.workflow["total_steps"] == 1
    assert state.workflow["steps"][0]["method"] == "Create"
    assert state.workflow["steps"][0]["object"] == "E MS Kabel"


def test_context_manager_uses_configured_method_and_object_synonyms():
    cases = [
        ("Please scaffold a MV cable", "Create", "E MS Kabel"),
        ("Open the station building", "Open Object", "E Station Gebouw"),
        ("Remove the low voltage joint", "Delete", "E LS Mof"),
    ]

    for prompt, expected_method, expected_object in cases:
        state = ContextManagerAgent().run(WorkflowState(prompt=prompt))

        assert len(state.context_intents) == 1
        assert state.context_intents[0].method == expected_method
        assert state.context_intents[0].object == expected_object


def test_validation_failure_classifier_routes_by_recoverability():
    assert classify_validation_failure(
        [Finding("error", "missing_step_key", "Step is missing command.", 0)]
    ) == "repair"
    assert classify_validation_failure(
        [Finding("error", "unknown_method", "Unknown method: Build.", 0)]
    ) == "replan"
    assert classify_validation_failure(
        [Finding("error", "step_not_object", "Step is not a dict.", 0)]
    ) == "human_review"


def test_rag_reranker_prefers_structurally_compatible_template():
    from src.agents import StepIntent

    candidates = [
        {
            "instruction": "Verify Status of E MS Kabel in elektra",
            "method": "Verify Field",
            "object": "E MS Kabel",
            "score": 0.92,
            "test_data": {"editor": {"Status": "In Bedrijf"}},
        },
        {
            "instruction": "Create E MS Installatie FP where Status have In Bedrijf in elektra",
            "method": "Create",
            "object": "E MS Installatie FP",
            "score": 0.88,
            "test_data": {"create": {"FLD_CSTM0_0": {"Status": "In Bedrijf"}}},
        },
        {
            "instruction": "Create E MS Kabel where Status have In Bedrijf in elektra",
            "method": "Create",
            "object": "E MS Kabel",
            "score": 0.7,
            "test_data": {"create": {"FLD_CSTM0_0": {"Status": "In Bedrijf"}}},
        },
    ]

    selected = RAGReranker().select(
        StepIntent(method="Create", object="E MS Kabel"),
        candidates,
        query="Create E MS Kabel with Status = In Bedrijf",
    )

    assert selected["object"] == "E MS Kabel"
    assert selected["method"] == "Create"
    assert selected["rerank_reasons"]["fields"]["matched"] == ["Status"]


def test_rag_reranker_uses_field_coverage_for_parameterized_prompts():
    from src.agents import StepIntent

    candidates = [
        {
            "instruction": "Create E MS Kabel where Ligging, ID have x, 1 in elektra",
            "method": "Create",
            "object": "E MS Kabel",
            "score": 0.9,
            "test_data": {"create": {"FLD_CSTM0_0": {"Ligging": "x", "ID": "1"}}},
        },
        {
            "instruction": "Create E MS Kabel where Status, Case Nummer have In Bedrijf, 1234 in elektra",
            "method": "Create",
            "object": "E MS Kabel",
            "score": 0.75,
            "test_data": {
                "create": {
                    "FLD_CSTM0_0": {
                        "Status": "In Bedrijf",
                        "Case Nummer": "1234",
                    }
                }
            },
        },
    ]

    selected = RAGReranker().select(
        StepIntent(method="Create", object="E MS Kabel"),
        candidates,
        query="Create E MS Kabel with Status = In Bedrijf and Case Nummer = 1234",
    )

    assert selected["instruction"].startswith("Create E MS Kabel where Status")
    assert selected["rerank_reasons"]["fields"]["coverage"] == 1.0


def test_rag_reranker_structural_compatibility_does_not_require_high_rag_score():
    from src.agents import StepIntent

    reranker = RAGReranker()
    intent = StepIntent(method="Create", object="E MS Installatie FP")
    low_score_candidate = {
        "instruction": "Create E MS Installatie FP where Nummer have 6 in elektra",
        "method": "Create",
        "object": "E MS Installatie FP",
        "score": 0.31,
        "test_data": {"create": {"FLD_CSTM0_0": {"Nummer": "6"}}},
    }

    assert reranker.is_structurally_compatible(intent, low_score_candidate)


def test_reviewer_preserves_human_review_status():
    from src.agents import ReviewerAgent

    state = WorkflowState(
        prompt="review",
        status="needs_human_review",
        workflow={"total_steps": 1, "steps": [{}]},
        findings=[Finding("error", "step_not_object", "Step is not a dict.", 0)],
    )

    state = ReviewerAgent().run(state)

    assert state.status == "needs_human_review"
