export const MACOS_HOST_ACTION_NAME = "request_macos_host_operation";

export type Sha256 = string;

export interface Mutation {
  operation: "create" | "replace" | "remove" | "inspect";
  path: string;
  detail: string;
}

export interface RollbackLimits {
  strategy: "none" | "remove_created_destination" | "detach_only";
  removes_only_request_created_paths: boolean;
  may_require_human_inspection: boolean;
}

export interface InputHash {
  path: string;
  sha256: Sha256;
}

export interface HostInspectionAction {
  category: "host_inspection";
  query:
    | "macos_version"
    | "architecture"
    | "disk_space"
    | "path_metadata"
    | "application_presence"
    | "application_version";
  target_path: string | null;
  application_id: string | null;
}

export interface DownloadAction {
  category: "https_download";
  url: string;
  destination: string;
  sha256: Sha256;
  max_bytes: number;
  redirect_limit: number;
  archive: "none" | "dmg" | "zip" | "tar_gz";
}

export interface HomebrewAction {
  category: "homebrew";
  operation: "install" | "uninstall";
  package_kind: "formula" | "cask";
  package: string;
}

export interface ApplicationInstallAction {
  category: "application_install";
  artifact_path: string;
  artifact_sha256: Sha256;
  artifact_kind: "dmg" | "zip";
  application_id: string;
  destination: string;
  mode: "stage" | "install";
  require_team_id: string;
  require_notarization: boolean;
}

export interface NativeApplicationAction {
  category: "native_application";
  application_id: string;
  operation: "blender_background_render" | "blender_version";
  working_directory: string;
  input_path: string | null;
  output_path: string | null;
  script: InputHash | null;
  configuration: InputHash[];
}

export type HostAction =
  | HostInspectionAction
  | DownloadAction
  | HomebrewAction
  | ApplicationInstallAction
  | NativeApplicationAction;

export interface HostOperationPlan {
  action: HostAction;
  expected_mutations: Mutation[];
  privilege: "user";
  timeout_seconds: number;
  output_limit_bytes: number;
  rollback: RollbackLimits;
  expiry_seconds: number;
}

/** The model-facing tool schema permits only these Pydantic-backed defaults. */
export type HostActionToolArgs =
  | (Omit<HostInspectionAction, "target_path" | "application_id"> & {
      target_path?: string | null;
      application_id?: string | null;
    })
  | (Omit<DownloadAction, "redirect_limit" | "archive"> & {
      redirect_limit?: number;
      archive?: DownloadAction["archive"];
    })
  | HomebrewAction
  | (Omit<ApplicationInstallAction, "require_notarization"> & {
      require_notarization?: boolean;
    })
  | (Omit<
      NativeApplicationAction,
      "input_path" | "output_path" | "script" | "configuration"
    > & {
      input_path?: string | null;
      output_path?: string | null;
      script?: InputHash | null;
      configuration?: InputHash[];
    });

export interface HostOperationPlanToolArgs {
  action: HostActionToolArgs;
  expected_mutations: Mutation[];
  privilege?: "user";
  timeout_seconds: number;
  output_limit_bytes?: number;
  rollback: Omit<RollbackLimits, "removes_only_request_created_paths"> & {
    removes_only_request_created_paths?: boolean;
  };
  expiry_seconds: number;
}

export type HostLifecycleState =
  | "requested"
  | "confirming"
  | "confirmed"
  | "running"
  | "succeeded"
  | "failed"
  | "rejected"
  | "expired"
  | "cancelled"
  | "partial"
  | "uncertain";

export interface HostStatusResponse {
  plan_digest: Sha256;
  state: HostLifecycleState;
  receipt_available: boolean;
}

export interface SignedHostReceipt {
  receipt: {
    request_digest: Sha256;
    terminal_status: Exclude<
      HostLifecycleState,
      "requested" | "confirming" | "confirmed" | "running"
    >;
    verified_outcome: boolean;
    remaining_human_step: string | null;
    message: string;
  };
  algorithm: "Ed25519";
  key_id: string;
  signature: string;
}

const sha256Pattern = /^[0-9a-f]{64}$/;
const packagePattern = /^[a-z0-9][a-z0-9@+._-]{0,127}$/;
const lifecycleStates = new Set<HostLifecycleState>([
  "requested",
  "confirming",
  "confirmed",
  "running",
  "succeeded",
  "failed",
  "rejected",
  "expired",
  "cancelled",
  "partial",
  "uncertain",
]);
const terminalStates = new Set<HostLifecycleState>([
  "succeeded",
  "failed",
  "rejected",
  "expired",
  "cancelled",
  "partial",
  "uncertain",
]);

function record(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function exactKeys(value: Record<string, unknown>, keys: string[]): boolean {
  const actual = Object.keys(value).sort();
  return (
    actual.length === keys.length &&
    actual.every((key, i) => key === [...keys].sort()[i])
  );
}

function text(value: unknown, max = 1024): value is string {
  return typeof value === "string" && value.length >= 1 && value.length <= max;
}

function absolutePath(value: unknown): value is string {
  return text(value, 4096) && value.startsWith("/");
}

function integer(value: unknown, min: number, max: number): value is number {
  return (
    Number.isInteger(value) &&
    (value as number) >= min &&
    (value as number) <= max
  );
}

function oneOf<T extends string>(
  value: unknown,
  values: readonly T[],
): value is T {
  return typeof value === "string" && values.includes(value as T);
}

function nullable<T>(
  value: unknown,
  guard: (item: unknown) => item is T,
): value is T | null {
  return value === null || guard(value);
}

function isInputHash(value: unknown): value is InputHash {
  return (
    record(value) &&
    exactKeys(value, ["path", "sha256"]) &&
    absolutePath(value.path) &&
    typeof value.sha256 === "string" &&
    sha256Pattern.test(value.sha256)
  );
}

function isMutation(value: unknown): value is Mutation {
  return (
    record(value) &&
    exactKeys(value, ["operation", "path", "detail"]) &&
    oneOf(value.operation, [
      "create",
      "replace",
      "remove",
      "inspect",
    ] as const) &&
    absolutePath(value.path) &&
    text(value.detail)
  );
}

function isRollback(value: unknown): value is RollbackLimits {
  return (
    record(value) &&
    exactKeys(value, [
      "strategy",
      "removes_only_request_created_paths",
      "may_require_human_inspection",
    ]) &&
    oneOf(value.strategy, [
      "none",
      "remove_created_destination",
      "detach_only",
    ] as const) &&
    typeof value.removes_only_request_created_paths === "boolean" &&
    typeof value.may_require_human_inspection === "boolean"
  );
}

function validHttpsUrl(value: unknown): value is string {
  if (!text(value)) return false;
  try {
    const url = new URL(value);
    return (
      url.protocol === "https:" &&
      !!url.hostname &&
      !url.username &&
      !url.password &&
      !url.search &&
      !url.hash
    );
  } catch {
    return false;
  }
}

function isHostAction(value: unknown): value is HostAction {
  if (!record(value) || typeof value.category !== "string") return false;
  switch (value.category) {
    case "host_inspection": {
      if (
        !exactKeys(value, [
          "category",
          "query",
          "target_path",
          "application_id",
        ])
      )
        return false;
      if (
        !oneOf(value.query, [
          "macos_version",
          "architecture",
          "disk_space",
          "path_metadata",
          "application_presence",
          "application_version",
        ] as const) ||
        !nullable(value.target_path, absolutePath) ||
        !nullable(value.application_id, text)
      )
        return false;
      const needsPath =
        value.query === "disk_space" || value.query === "path_metadata";
      const needsApplication = String(value.query).startsWith("application_");
      return (
        (needsPath ? value.target_path !== null : value.target_path === null) &&
        (!needsApplication || value.application_id !== null)
      );
    }
    case "https_download":
      return (
        exactKeys(value, [
          "category",
          "url",
          "destination",
          "sha256",
          "max_bytes",
          "redirect_limit",
          "archive",
        ]) &&
        validHttpsUrl(value.url) &&
        absolutePath(value.destination) &&
        typeof value.sha256 === "string" &&
        sha256Pattern.test(value.sha256) &&
        integer(value.max_bytes, 1, 2_147_483_648) &&
        integer(value.redirect_limit, 0, 3) &&
        oneOf(value.archive, ["none", "dmg", "zip", "tar_gz"] as const)
      );
    case "homebrew":
      return (
        exactKeys(value, [
          "category",
          "operation",
          "package_kind",
          "package",
        ]) &&
        oneOf(value.operation, ["install", "uninstall"] as const) &&
        oneOf(value.package_kind, ["formula", "cask"] as const) &&
        typeof value.package === "string" &&
        packagePattern.test(value.package)
      );
    case "application_install":
      return (
        exactKeys(value, [
          "category",
          "artifact_path",
          "artifact_sha256",
          "artifact_kind",
          "application_id",
          "destination",
          "mode",
          "require_team_id",
          "require_notarization",
        ]) &&
        absolutePath(value.artifact_path) &&
        typeof value.artifact_sha256 === "string" &&
        sha256Pattern.test(value.artifact_sha256) &&
        oneOf(value.artifact_kind, ["dmg", "zip"] as const) &&
        text(value.application_id) &&
        absolutePath(value.destination) &&
        oneOf(value.mode, ["stage", "install"] as const) &&
        text(value.require_team_id) &&
        typeof value.require_notarization === "boolean"
      );
    case "native_application": {
      if (
        !exactKeys(value, [
          "category",
          "application_id",
          "operation",
          "working_directory",
          "input_path",
          "output_path",
          "script",
          "configuration",
        ]) ||
        !text(value.application_id) ||
        !oneOf(value.operation, [
          "blender_background_render",
          "blender_version",
        ] as const) ||
        !absolutePath(value.working_directory) ||
        !nullable(value.input_path, absolutePath) ||
        !nullable(value.output_path, absolutePath) ||
        !nullable(value.script, isInputHash) ||
        !Array.isArray(value.configuration) ||
        value.configuration.length > 32 ||
        !value.configuration.every(isInputHash)
      )
        return false;
      return value.operation === "blender_background_render"
        ? value.input_path !== null && value.output_path !== null
        : value.input_path === null &&
            value.output_path === null &&
            value.script === null &&
            value.configuration.length === 0;
    }
    default:
      return false;
  }
}

export function isHostOperationPlan(
  value: unknown,
): value is HostOperationPlan {
  return (
    record(value) &&
    exactKeys(value, [
      "action",
      "expected_mutations",
      "privilege",
      "timeout_seconds",
      "output_limit_bytes",
      "rollback",
      "expiry_seconds",
    ]) &&
    isHostAction(value.action) &&
    Array.isArray(value.expected_mutations) &&
    value.expected_mutations.length <= 32 &&
    value.expected_mutations.every(isMutation) &&
    value.privilege === "user" &&
    integer(value.timeout_seconds, 1, 3600) &&
    integer(value.output_limit_bytes, 1024, 1_048_576) &&
    isRollback(value.rollback) &&
    integer(value.expiry_seconds, 1, 3600)
  );
}

function hasOnlyKeys(value: Record<string, unknown>, keys: string[]): boolean {
  return Object.keys(value).every((key) => keys.includes(key));
}

/**
 * Applies only defaults declared by HostOperationPlan's Pydantic schema, then
 * validates the resulting immutable executor wire plan with extra keys denied.
 */
export function normalizeHostOperationPlan(
  value: unknown,
): HostOperationPlan | null {
  if (
    !record(value) ||
    !hasOnlyKeys(value, [
      "action",
      "expected_mutations",
      "privilege",
      "timeout_seconds",
      "output_limit_bytes",
      "rollback",
      "expiry_seconds",
    ]) ||
    !record(value.action) ||
    !record(value.rollback)
  ) {
    return null;
  }

  const category = value.action.category;
  let action: Record<string, unknown> = { ...value.action };
  if (category === "host_inspection") {
    action = { target_path: null, application_id: null, ...action };
  } else if (category === "https_download") {
    action = { redirect_limit: 0, archive: "none", ...action };
  } else if (category === "application_install") {
    action = { require_notarization: true, ...action };
  } else if (category === "native_application") {
    action = {
      input_path: null,
      output_path: null,
      script: null,
      configuration: [],
      ...action,
    };
  }

  const candidate = {
    privilege: "user",
    output_limit_bytes: 65_536,
    ...value,
    action,
    rollback: {
      removes_only_request_created_paths: true,
      ...value.rollback,
    },
  };
  return isHostOperationPlan(candidate) ? candidate : null;
}

export function isHostStatusResponse(
  value: unknown,
): value is HostStatusResponse {
  return (
    record(value) &&
    exactKeys(value, ["plan_digest", "state", "receipt_available"]) &&
    typeof value.plan_digest === "string" &&
    sha256Pattern.test(value.plan_digest) &&
    typeof value.state === "string" &&
    lifecycleStates.has(value.state as HostLifecycleState) &&
    typeof value.receipt_available === "boolean"
  );
}

export function isTerminalHostState(state: HostLifecycleState): boolean {
  return terminalStates.has(state);
}

export function isMatchingSignedReceipt(
  value: unknown,
  digest: string,
): value is SignedHostReceipt {
  if (
    !record(value) ||
    !exactKeys(value, ["receipt", "algorithm", "key_id", "signature"]) ||
    value.algorithm !== "Ed25519" ||
    !text(value.key_id) ||
    !text(value.signature) ||
    !record(value.receipt)
  )
    return false;
  const receipt = value.receipt;
  return (
    receipt.request_digest === digest &&
    typeof receipt.terminal_status === "string" &&
    terminalStates.has(receipt.terminal_status as HostLifecycleState) &&
    typeof receipt.verified_outcome === "boolean" &&
    nullable(
      receipt.remaining_human_step,
      (item): item is string => typeof item === "string",
    ) &&
    typeof receipt.message === "string"
  );
}
