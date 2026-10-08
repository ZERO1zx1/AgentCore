import { z } from 'zod'
import type {
  BridgeConfig,
  RetryPolicy,
  BudgetLimitConfig
} from '@agentcore/types'

/**
 * Assistant configuration
 */
export const AssistantConfigSchema = z.object({
  // Agent loop limits
  maxIterations: z.number().int().positive().default(50),
  maxToolCalls: z.number().int().positive().default(100),
  iterationTimeoutMs: z.number().int().positive().default(300000), // 5 min
  toolTimeoutMs: z.number().int().positive().default(120000), // 2 min

  // Retry policy
  retryPolicy: z
    .object({
      maxRetries: z.number().int().nonnegative().default(2),
      baseDelayMs: z.number().int().positive().default(1000),
      maxDelayMs: z.number().int().positive().default(30000),
      exponentialBase: z.number().default(2),
      jitter: z.boolean().default(true),
      retryableCategories: z
        .array(
          z.enum([
            'transient',
            'permanent',
            'budget',
            'security',
            'user_action'
          ])
        )
        .default(['transient', 'budget']),
      retryableCodes: z
        .array(z.string())
        .default([
          'RATE_LIMITED',
          'TIMEOUT',
          'TOOL_TIMEOUT',
          'BRIDGE_TIMEOUT',
          'PROVIDER_ERROR',
          'DEPENDENCY_UNAVAILABLE',
          'BUDGET_EXCEEDED'
        ])
    })
    .default({
      maxRetries: 2,
      baseDelayMs: 1000,
      maxDelayMs: 30000,
      exponentialBase: 2,
      jitter: true,
      retryableCategories: ['transient', 'budget'],
      retryableCodes: [
        'RATE_LIMITED',
        'TIMEOUT',
        'TOOL_TIMEOUT',
        'BRIDGE_TIMEOUT',
        'PROVIDER_ERROR',
        'DEPENDENCY_UNAVAILABLE',
        'BUDGET_EXCEEDED'
      ]
    }),

  // Budget limits
  budgetLimits: z
    .object({
      maxTotalCost: z.string().optional(),
      maxCostPerTool: z.string().optional(),
      reserveRatio: z.number().default(0.15),
      warnAtPercentage: z.number().default(0.5),
      criticalAtPercentage: z.number().default(0.25),
      emergencyAtPercentage: z.number().default(0.1)
    })
    .default({}),

  // Context limits
  maxContextChars: z.number().int().positive().default(50000),
  maxContextTokens: z.number().int().positive().default(128000),

  // Bridge configuration
  bridge: z
    .object({
      transport: z.enum(['stdio', 'http', 'websocket']).default('stdio'),
      pythonExecutable: z.string().default('python'),
      engineModule: z.string().default('-m src.core.engine'),
      workingDirectory: z.string().default('.'),
      env: z.record(z.string()).optional(),
      timeoutMs: z.number().int().positive().default(120000),
      maxBuffer: z
        .number()
        .int()
        .positive()
        .default(10 * 1024 * 1024),
      heartbeatIntervalMs: z.number().int().positive().default(30000)
    })
    .default({}),

  // Approval settings
  approval: z
    .object({
      defaultTimeoutSeconds: z.number().int().positive().default(300),
      autoApproveRead: z.boolean().default(true),
      autoApproveWrite: z.boolean().default(false),
      requireApprovalFor: z
        .array(z.enum(['read', 'write', 'external', 'dangerous']))
        .default(['write', 'external', 'dangerous'])
    })
    .default({}),

  // Security settings
  security: z
    .object({
      allowedPaths: z.array(z.string()).default(['.']),
      blockedPaths: z
        .array(z.string())
        .default(['.git', '.env', 'node_modules', '.agentcore', '__pycache__']),
      allowedCommands: z.array(z.string()).default([]),
      blockedCommands: z
        .array(z.string())
        .default(['rm -rf', 'sudo', 'chmod 777', 'format', 'mkfs']),
      secretRedaction: z.boolean().default(true),
      promptInjectionDetection: z.boolean().default(true),
      untrustedOutputMarking: z.boolean().default(true)
    })
    .default({}),

  // Session settings
  session: z
    .object({
      persistDirectory: z.string().default('.agentcore/sessions'),
      maxSessions: z.number().int().positive().default(100),
      sessionTimeoutMs: z.number().int().positive().default(86400000) // 24 hours
    })
    .default({}),

  // Logging
  logging: z
    .object({
      level: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
      auditLog: z.boolean().default(true),
      eventLog: z.boolean().default(true)
    })
    .default({})
})

export type AssistantConfig = z.infer<typeof AssistantConfigSchema>

/**
 * Default assistant configuration
 */
export const DEFAULT_ASSISTANT_CONFIG: AssistantConfig = {
  maxIterations: 50,
  maxToolCalls: 100,
  iterationTimeoutMs: 300000,
  toolTimeoutMs: 120000,
  retryPolicy: {
    maxRetries: 2,
    baseDelayMs: 1000,
    maxDelayMs: 30000,
    exponentialBase: 2,
    jitter: true,
    retryableCategories: ['transient', 'budget'],
    retryableCodes: [
      'RATE_LIMITED',
      'TIMEOUT',
      'TOOL_TIMEOUT',
      'BRIDGE_TIMEOUT',
      'PROVIDER_ERROR',
      'DEPENDENCY_UNAVAILABLE',
      'BUDGET_EXCEEDED'
    ]
  },
  budgetLimits: {
    reserveRatio: 0.15,
    warnAtPercentage: 0.5,
    criticalAtPercentage: 0.25,
    emergencyAtPercentage: 0.1
  },
  maxContextChars: 50000,
  maxContextTokens: 128000,
  bridge: {
    transport: 'stdio',
    pythonExecutable: 'python',
    engineModule: '-m src.core.engine',
    workingDirectory: '.',
    timeoutMs: 120000,
    maxBuffer: 10 * 1024 * 1024,
    heartbeatIntervalMs: 30000
  },
  approval: {
    defaultTimeoutSeconds: 300,
    autoApproveRead: true,
    autoApproveWrite: false,
    requireApprovalFor: ['write', 'external', 'dangerous']
  },
  security: {
    allowedPaths: ['.'],
    blockedPaths: ['.git', '.env', 'node_modules', '.agentcore', '__pycache__'],
    allowedCommands: [],
    blockedCommands: ['rm -rf', 'sudo', 'chmod 777', 'format', 'mkfs'],
    secretRedaction: true,
    promptInjectionDetection: true,
    untrustedOutputMarking: true
  },
  session: {
    persistDirectory: '.agentcore/sessions',
    maxSessions: 100,
    sessionTimeoutMs: 86400000
  },
  logging: {
    level: 'info',
    auditLog: true,
    eventLog: true
  }
}

/**
 * Merge user config with defaults
 */
export function mergeConfig (
  userConfig: Partial<AssistantConfig>
): AssistantConfig {
  return AssistantConfigSchema.parse({
    ...DEFAULT_ASSISTANT_CONFIG,
    ...userConfig,
    retryPolicy: {
      ...DEFAULT_ASSISTANT_CONFIG.retryPolicy,
      ...userConfig.retryPolicy
    },
    budgetLimits: {
      ...DEFAULT_ASSISTANT_CONFIG.budgetLimits,
      ...userConfig.budgetLimits
    },
    bridge: {
      ...DEFAULT_ASSISTANT_CONFIG.bridge,
      ...userConfig.bridge
    },
    approval: {
      ...DEFAULT_ASSISTANT_CONFIG.approval,
      ...userConfig.approval
    },
    security: {
      ...DEFAULT_ASSISTANT_CONFIG.security,
      ...userConfig.security,
      allowedPaths: [
        ...DEFAULT_ASSISTANT_CONFIG.security.allowedPaths,
        ...(userConfig.security?.allowedPaths || [])
      ],
      blockedPaths: [
        ...DEFAULT_ASSISTANT_CONFIG.security.blockedPaths,
        ...(userConfig.security?.blockedPaths || [])
      ]
    },
    session: {
      ...DEFAULT_ASSISTANT_CONFIG.session,
      ...userConfig.session
    },
    logging: {
      ...DEFAULT_ASSISTANT_CONFIG.logging,
      ...userConfig.logging
    }
  })
}

/**
 * Validate assistant configuration
 */
export function validateConfig (config: unknown): {
  ok: boolean
  config?: AssistantConfig
  errors: string[]
} {
  const result = AssistantConfigSchema.safeParse(config)
  if (result.success) {
    return { ok: true, config: result.data, errors: [] }
  }
  return {
    ok: false,
    errors: result.error.issues.map(
      issue => `${issue.path.join('.')}: ${issue.message}`
    )
  }
}
