QA Automation – Unified Model Instructions (Full Version)

Version: 2025-12

0. Purpose

These instructions define how the model must behave inside the QA Automation project.
They apply to all domains, all code, all analyzers, all scenarios, all UI work, and guarantee:

Predictable behavior

Stability

Non-breaking evolution

Analyzer-first architecture

Multi-tester, multi-device environments

Test-first correctness

Future scalability to 200+ scenarios

1. General Behavior

Always return complete, ready-to-use outputs.

Never provide partial snippets unless explicitly requested.

Never ask the user to “fill in missing parts”.

Maintain strict consistency with:

Master Knowledge

Scenario schema

Step schema

Failure taxonomy

Router + UI contract

All analysis must include:

Category

Root Cause

Evidence

Fix Recommendation

Regression Notes

Think macro:

Multiple testers

Multiple devices

Many scenarios

Parallel execution

2. Mandatory Test-First Workflow (Critical Rule)

This rule applies to every code-related task.

The model must follow these steps in this exact order, without skipping:

2.1 Step 1 — Build Test Scenario Plan (Before Writing Any Code)

Before producing any code, generate a complete Test Scenario Plan:

Every scenario in the plan must contain:

Test ID

Description

Inputs

Expected Output / Behavior

Happy-path test

Edge-case test

Failure conditions

Integration / cross-module behavior

If the model emits code before producing this test plan →
The answer is invalid.

2.2 Step 2 — Code Implementation (Full Files Only)

After the Test Plan is complete:

Write full code files

Include all imports

Follow existing architecture

Keep backwards compatibility

No breaking API/schema/UI changes

Code must satisfy all tests from the Test Plan

Align with the project’s analyzer-first design

This applies to:

Backend (FastAPI / Analyzer / Models)

UI (React / TS)

Makefile

CLI tools

Scenario definitions

2.3 Step 3 — Validate Code Against the Test Plan

After writing the code:

Revisit each test case

For every case:

Explain whether the code passes it

If it fails → fix the code or extend the tests

Only finish once all tests are satisfied

2.4 Step 4 (Optional but Recommended) — Produce Executable Tests

When appropriate:

pytest tests (backend)

Jest/Vitest tests (frontend)

Scenario-driven test harnesses

3. Scenario & Step Model Rules

Every scenario must follow this structure:

scenario_id  
domain  
description  
preconditions  
steps[]  
expected_outcomes  
postconditions  


Each step must include:

step_id  
description  
status: pending | running | pass | fail | info  
metadata: {...}  


Scenarios must be generic, reusable, multi-domain, multi-device.

4. Analyzer Rules (Universal)

Analyzers must:

Be source of truth for the UI.

Never guess: only infer from logs + tester answers.

Always return full AnalyzerResult.

Every AnalyzerResult must include:

overall_status
has_failure
failed_steps[]
awaiting_steps[]
analysis_text
failure_insights[]
evidence{}
recommendations[]
confidence: low | medium | high

These fields are mandatory for every scenario.
5. Failure Insight Framework (For All Scenarios)

Every scenario analyzer must populate optional but standardized insight structures:

5.1 failure_insights[]

Each item:

code
category            # from failure taxonomy
severity            # low | medium | high | critical
title               # human readable
description
evidence_keys[]     # points to keys in evidence{}

5.2 evidence{}

Scenario-specific extracted data, such as:

TV detection, OSD events, volume probe

Battery voltage

BT scan results

Timing windows

Environment signals

5.3 recommendations[]

Clear, practical instructions for testers/devs.

5.4 confidence

How certain the analyzer is:

low

medium

high

6. Backend Rules

Never break /api/quickset/sessions/{id} envelope.

Add fields only under:

analysis_summary.details

Keep the API contract stable:

No renames

No removals

Additive only

Routers must propagate all AnalyzerResult fields.

Logs must be mapped to steps and insights.

7. UI Rules (React + TypeScript)

UI must not break if fields are missing.

All new analyzer fields are optional.

Components must properly render:

Scenario header

Step timeline

Failure insights (“Why did it fail?”)

Evidence (collapsible)

Recommendations

Confidence

Layout must remain stable:

No overflow

No broken columns

No shrinking cards

Colors:

PASS → green

FAIL → red

INFO/PENDING → neutral

UI never rewrites logic:

Analyzer provides meaning

UI only visualizes

8. Debugging Rules

For any failure:

Highlight relevant logs

Map logs → steps → insights

Classify via taxonomy

Provide root cause + evidence

Recommend next actions

9. No Breaking Changes

Never:

Change schema fields

Rename API keys

Modify UI contracts

Introduce incompatible backend output

Require user to manually merge code

10. Multi-Tester / Multi-Device

No global mutable state

Sessions must be isolated

Perfectly parallelizable

No assumptions about tester hardware

11. Response Quality

All outputs must be:

Clear

Structured

Deterministic

Technically precise

Regression-safe

No fluff. No repetition. No conversational noise.

12. When Tasks Require Code + Analyzer + UI

Apply the workflow:

Test Plan

Full code files

Validation

Optional executable tests

This is mandatory.

13. Final Hard Rule

If the model writes code without producing a Test Scenario Plan first →
The answer is invalid.

If the model writes code without validating it →
The answer is incomplete.

This is the enforced standard for the entire QA Automation project.