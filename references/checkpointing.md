# Checkpointing and Resumability

Manus Mini ensures that all progress is persistent and resumable, preventing the need to repeat expensive paid operations.

## Checkpoint Invariants

Checkpoints are triggered after every meaningful atomic unit of work:
- **Code**: After repository discovery, implementation units, and successful critical tests.
- **Documents**: After processing page groups, chapters, or extraction stages.
- **Multimodal**: After scene detection, keyframe analysis, or UI specification generation.

## Task Manifest

The task manifest tracks:
- **Source Fingerprints**: SHA-256 hashes of input files to detect changes.
- **Work Units**: List of completed and pending tasks.
- **Budget Tracking**: Real-time usage and remaining balance.
- **Artifact Map**: Pointers to all generated files and intermediate results.

## Resumption Workflow

1. The engine loads the existing manifest using the `task_id`.
2. Fingerprints are verified against current inputs.
3. Completed work units are skipped.
4. Execution resumes from the exact next pending unit.
