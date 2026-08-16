export const DOCKER_BROKER_ACTION_NAME =
  "request_docker_compose_operation" as const;

export type DockerComposeOperation =
  | "pull"
  | "build"
  | "up"
  | "start"
  | "stop"
  | "restart"
  | "down";

export interface DockerComposeOperationPlan {
  request_id: string;
  project_directory: string;
  compose_files: [string];
  operation: DockerComposeOperation;
  services: string[];
  profiles: string[];
}

export type DockerBrokerTerminalState =
  | "succeeded"
  | "failed"
  | "rejected"
  | "cancelled"
  | "expired";

export type DockerBrokerOperationState =
  | "requested"
  | "confirming"
  | "confirmed"
  | "running"
  | DockerBrokerTerminalState;

export interface DockerBrokerStatus {
  operation_digest: string;
  plan_digest: string;
  state: DockerBrokerOperationState;
  result_available: boolean;
}

export interface DockerBrokerResult {
  operation_digest: string;
  plan_digest: string;
  state: DockerBrokerTerminalState;
  result: Record<string, unknown>;
}

const requestIdPattern = /^[A-Za-z0-9_.:-]{1,128}$/;
const sha256Pattern = /^[0-9a-f]{64}$/;
const operations = new Set<DockerComposeOperation>([
  "pull",
  "build",
  "up",
  "start",
  "stop",
  "restart",
  "down",
]);
const operationStates = new Set<DockerBrokerOperationState>([
  "requested",
  "confirming",
  "confirmed",
  "running",
  "succeeded",
  "failed",
  "rejected",
  "cancelled",
  "expired",
]);
const terminalStates = new Set<DockerBrokerTerminalState>([
  "succeeded",
  "failed",
  "rejected",
  "cancelled",
  "expired",
]);

function record(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function exactKeys(
  value: Record<string, unknown>,
  expected: string[],
): boolean {
  const actual = Object.keys(value).sort();
  const sortedExpected = [...expected].sort();
  return (
    actual.length === sortedExpected.length &&
    actual.every((key, index) => key === sortedExpected[index])
  );
}

function hasOnlyKeys(
  value: Record<string, unknown>,
  expected: string[],
): boolean {
  return Object.keys(value).every((key) => expected.includes(key));
}

function targetText(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value === value.trim() &&
    value.length >= 1 &&
    value.length <= 1024
  );
}

function targetList(value: unknown, maximum: number): value is string[] {
  return (
    Array.isArray(value) && value.length <= maximum && value.every(targetText)
  );
}

/**
 * Applies only the two empty-list defaults declared by the broker plan schema.
 * Every other field is required, and unknown fields are rejected.
 */
export function normalizeDockerComposeOperationPlan(
  value: unknown,
): DockerComposeOperationPlan | null {
  if (
    !record(value) ||
    !hasOnlyKeys(value, [
      "request_id",
      "project_directory",
      "compose_files",
      "operation",
      "services",
      "profiles",
    ])
  ) {
    return null;
  }

  const candidate: Record<string, unknown> = {
    services: [],
    profiles: [],
    ...value,
  };
  if (
    !exactKeys(candidate, [
      "request_id",
      "project_directory",
      "compose_files",
      "operation",
      "services",
      "profiles",
    ]) ||
    typeof candidate.request_id !== "string" ||
    !requestIdPattern.test(candidate.request_id) ||
    !targetText(candidate.project_directory) ||
    !Array.isArray(candidate.compose_files) ||
    candidate.compose_files.length !== 1 ||
    !targetText(candidate.compose_files[0]) ||
    typeof candidate.operation !== "string" ||
    !operations.has(candidate.operation as DockerComposeOperation) ||
    !targetList(candidate.services, 40) ||
    !targetList(candidate.profiles, 20)
  ) {
    return null;
  }

  return {
    request_id: candidate.request_id,
    project_directory: candidate.project_directory,
    compose_files: [candidate.compose_files[0]],
    operation: candidate.operation as DockerComposeOperation,
    services: candidate.services,
    profiles: candidate.profiles,
  };
}

export function isDockerBrokerStatus(
  value: unknown,
): value is DockerBrokerStatus {
  return (
    record(value) &&
    exactKeys(value, [
      "operation_digest",
      "plan_digest",
      "state",
      "result_available",
    ]) &&
    typeof value.operation_digest === "string" &&
    sha256Pattern.test(value.operation_digest) &&
    typeof value.plan_digest === "string" &&
    sha256Pattern.test(value.plan_digest) &&
    typeof value.state === "string" &&
    operationStates.has(value.state as DockerBrokerOperationState) &&
    typeof value.result_available === "boolean"
  );
}

export function isDockerBrokerResult(
  value: unknown,
): value is DockerBrokerResult {
  return (
    record(value) &&
    exactKeys(value, ["operation_digest", "plan_digest", "state", "result"]) &&
    typeof value.operation_digest === "string" &&
    sha256Pattern.test(value.operation_digest) &&
    typeof value.plan_digest === "string" &&
    sha256Pattern.test(value.plan_digest) &&
    typeof value.state === "string" &&
    terminalStates.has(value.state as DockerBrokerTerminalState) &&
    record(value.result)
  );
}

export function isTerminalDockerBrokerState(
  value: DockerBrokerOperationState,
): value is DockerBrokerTerminalState {
  return terminalStates.has(value as DockerBrokerTerminalState);
}
