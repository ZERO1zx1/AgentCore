import type { Session } from './session.js'
import type { TaskManifest, WorkUnit, AgentEvent } from '@agentcore/types'
import type { BridgeClient } from '@agentcore/types'

/**
 * Agent loop options
 */
export interface LoopOptions {
  maxIterations: number
  maxToolCalls: number
  iterationTimeoutMs: number
  toolTimeoutMs: number
  onIteration?: (iteration: number, session: Session) => Promise<void>
  onEvent?: (event: AgentEvent) => void
  onError?: (error: Error) => void
}

/**
 * Run agent loop with session
 */
export async function runAgentLoop (
  session: Session,
  options: LoopOptions
): Promise<TaskManifest> {
  const startTime = Date.now()

  try {
    // Initialize session
    await session.initialize()

    // Run session
    const manifest = await session.run()

    return manifest
  } catch (error) {
    if (options.onError) {
      options.onError(error as Error)
    }
    throw error
  }
}

/**
 * Run agent loop with streaming events
 */
export async function runAgentLoopStreaming (
  session: Session,
  options: LoopOptions & {
    eventHandler: (event: AgentEvent) => Promise<void>
  }
): Promise<TaskManifest> {
  const handler = (event: AgentEvent) => {
    options.eventHandler(event).catch(console.error)
  }

  session.on('event', handler)

  try {
    return await runAgentLoop(session, options)
  } finally {
    session.off('event', handler)
  }
}

/**
 * Create agent loop controller
 */
export function createLoopController (session: Session) {
  let cancelled = false
  let paused = false

  return {
    cancel: () => {
      cancelled = true
      session.cancel('Cancelled by controller').catch(console.error)
    },
    pause: () => {
      paused = true
      session.pause()
    },
    resume: () => {
      paused = false
      session.resume()
    },
    isCancelled: () => cancelled,
    isPaused: () => paused,
    getState: () => session.state,
    getManifest: () => session.manifest,
    getIteration: () => session.currentIteration,
    getToolCallsCount: () => session.toolCallsCount
  }
}

/**
 * Agent loop state machine
 */
export enum LoopState {
  INITIALIZING = 'initializing',
  PLANNING = 'planning',
  SELECTING_TOOL = 'selecting_tool',
  VALIDATING_TOOL = 'validating_tool',
  CHECKING_PERMISSION = 'checking_permission',
  REQUESTING_APPROVAL = 'requesting_approval',
  EXECUTING_TOOL = 'executing_tool',
  OBSERVING_RESULT = 'observing_result',
  CLASSIFYING_ERROR = 'classifying_error',
  RETRYING = 'retrying',
  CHECKPOINTING = 'checkpointing',
  COMPLETING = 'completing',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

/**
 * Loop step result
 */
export interface LoopStepResult {
  state: LoopState
  continue: boolean
  manifest?: TaskManifest
  error?: Error
}

/**
 * Execute single loop step
 */
export async function executeLoopStep (
  session: Session,
  bridge: BridgeClient,
  step: LoopState
): Promise<LoopStepResult> {
  switch (step) {
    case LoopState.PLANNING:
      return await executePlanningStep(session, bridge)
    case LoopState.SELECTING_TOOL:
      return await executeToolSelectionStep(session)
    case LoopState.VALIDATING_TOOL:
      return await executeValidationStep(session)
    case LoopState.CHECKING_PERMISSION:
      return await executePermissionStep(session)
    case LoopState.REQUESTING_APPROVAL:
      return await executeApprovalStep(session)
    case LoopState.EXECUTING_TOOL:
      return await executeToolStep(session, bridge)
    case LoopState.OBSERVING_RESULT:
      return await executeObservationStep(session)
    case LoopState.CLASSIFYING_ERROR:
      return await executeErrorClassificationStep(session)
    case LoopState.RETRYING:
      return await executeRetryStep(session)
    case LoopState.CHECKPOINTING:
      return await executeCheckpointStep(session, bridge)
    case LoopState.COMPLETING:
      return await executeCompletionStep(session)
    default:
      return {
        state: LoopState.FAILED,
        continue: false,
        error: new Error(`Unknown step: ${step}`)
      }
  }
}

// Step implementations (simplified - actual logic in Session.run)
async function executePlanningStep (
  session: Session,
  bridge: BridgeClient
): Promise<LoopStepResult> {
  // Planning is done by Python engine via initialize_task
  return { state: LoopState.SELECTING_TOOL, continue: true }
}

async function executeToolSelectionStep (
  session: Session
): Promise<LoopStepResult> {
  // Tool selection is done by Python engine via run_next_unit
  return { state: LoopState.VALIDATING_TOOL, continue: true }
}

async function executeValidationStep (
  session: Session
): Promise<LoopStepResult> {
  // Validation is done by Python engine
  return { state: LoopState.CHECKING_PERMISSION, continue: true }
}

async function executePermissionStep (
  session: Session
): Promise<LoopStepResult> {
  // Permission check is done by TypeScript policy
  return { state: LoopState.REQUESTING_APPROVAL, continue: true }
}

async function executeApprovalStep (session: Session): Promise<LoopStepResult> {
  // Approval is handled by ApprovalManager
  return { state: LoopState.EXECUTING_TOOL, continue: true }
}

async function executeToolStep (
  session: Session,
  bridge: BridgeClient
): Promise<LoopStepResult> {
  // Tool execution is done by Python engine
  return { state: LoopState.OBSERVING_RESULT, continue: true }
}

async function executeObservationStep (
  session: Session
): Promise<LoopStepResult> {
  // Observation is done via events
  return { state: LoopState.CLASSIFYING_ERROR, continue: true }
}

async function executeErrorClassificationStep (
  session: Session
): Promise<LoopStepResult> {
  // Error classification is done by error handling
  return { state: LoopState.CHECKPOINTING, continue: true }
}

async function executeRetryStep (session: Session): Promise<LoopStepResult> {
  // Retry is handled by Session.run
  return { state: LoopState.SELECTING_TOOL, continue: true }
}

async function executeCheckpointStep (
  session: Session,
  bridge: BridgeClient
): Promise<LoopStepResult> {
  // Checkpoint is done by Python engine
  return { state: LoopState.SELECTING_TOOL, continue: true }
}

async function executeCompletionStep (
  session: Session
): Promise<LoopStepResult> {
  return { state: LoopState.COMPLETED, continue: false }
}
