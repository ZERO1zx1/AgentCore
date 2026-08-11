# Output Contract

Every AgentCore task concludes with a factual execution report and a defined status.

## Task Statuses

- **COMPLETED**: The primary deliverable is finished and validated.
- **PARTIALLY_COMPLETED**: Useful work was produced, but some tasks remain (often due to budget exhaustion).
- **BLOCKED**: Execution cannot proceed due to missing requirements (tools, inputs, or credentials).
- **FAILED**: An unrecoverable error occurred, and no useful output was produced.

## Execution Report

The final report includes:
- **Completed Work**: A summary of all finished units.
- **Saved Outputs**: Links to implementation files, reports, and artifacts.
- **Validation Summary**: PASS/FAIL/NOT_RUN status for all planned validation steps.
- **Budget Summary**: Total initial budget, used credits, and final state.
- **Resume Instructions**: Precise steps to continue the task if partially completed.

## Code-First Policy

When the requested deliverable is software, AgentCore prioritizes the production of actual source files, configuration, and tests over long-form conversational explanations.
