import { useRef, useState } from "react";
import { Interrupt } from "@langchain/langgraph-sdk";
import { useQueryState } from "nuqs";
import { Button } from "@/components/ui/button";
import { useStreamContext } from "@/providers/Stream";
import { HITLRequest } from "../types";
import {
  HostLifecycleState,
  HostOperationPlan,
  HostStatusResponse,
  normalizeHostOperationPlan,
  isHostStatusResponse,
  isMatchingSignedReceipt,
  isTerminalHostState,
} from "@/lib/macos-host-operation";

const confirmationUrl =
  process.env.NEXT_PUBLIC_MACOS_HOST_EXECUTOR_URL ??
  "http://127.0.0.1:8765/v1/confirmations";
const pollDelayMs = 500;
const executorRequestTimeoutMs = 10_000;

type CoderApprovalState =
  | "awaiting_decision"
  | "waiting_for_mac"
  | "resuming"
  | "blocked"
  | "finished";

const coderStatusLanguage: Record<CoderApprovalState, string> = {
  awaiting_decision: "Paused — waiting for your approval decision.",
  waiting_for_mac:
    "Paused — waiting for Mac confirmation and a verified receipt. Coder has not resumed.",
  resuming: "Resuming — your decision is being sent to Coder.",
  blocked:
    "Paused — approval did not complete. Coder is not working on this task.",
  finished: "Finished — this approval card no longer blocks Coder.",
};

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid gap-1 border-b py-2 last:border-b-0 sm:grid-cols-[12rem_1fr]">
      <dt className="text-muted-foreground text-sm font-medium">{label}</dt>
      <dd className="min-w-0 font-mono text-sm break-words">{value}</dd>
    </div>
  );
}

function BooleanValue({ value }: { value: boolean }) {
  return <>{value ? "Yes" : "No"}</>;
}

function OptionalValue({ value }: { value: string | null }) {
  return <>{value ?? "None"}</>;
}

function ActionFields({ plan }: { plan: HostOperationPlan }) {
  const action = plan.action;
  switch (action.category) {
    case "host_inspection":
      return (
        <>
          <Field
            label="Inspection query"
            value={action.query}
          />
          <Field
            label="Target path"
            value={<OptionalValue value={action.target_path} />}
          />
          <Field
            label="Application ID"
            value={<OptionalValue value={action.application_id} />}
          />
        </>
      );
    case "https_download":
      return (
        <>
          <Field
            label="Download URL"
            value={action.url}
          />
          <Field
            label="Destination path"
            value={action.destination}
          />
          <Field
            label="Expected SHA-256"
            value={action.sha256}
          />
          <Field
            label="Maximum download bytes"
            value={action.max_bytes.toLocaleString()}
          />
          <Field
            label="Redirect limit"
            value={action.redirect_limit}
          />
          <Field
            label="Archive type"
            value={action.archive}
          />
        </>
      );
    case "homebrew":
      return (
        <>
          <Field
            label="Homebrew operation"
            value={action.operation}
          />
          <Field
            label="Package kind"
            value={action.package_kind}
          />
          <Field
            label="Exact package"
            value={action.package}
          />
        </>
      );
    case "application_install":
      return (
        <>
          <Field
            label="Artifact path"
            value={action.artifact_path}
          />
          <Field
            label="Artifact SHA-256"
            value={action.artifact_sha256}
          />
          <Field
            label="Artifact kind"
            value={action.artifact_kind}
          />
          <Field
            label="Application ID"
            value={action.application_id}
          />
          <Field
            label="Destination path"
            value={action.destination}
          />
          <Field
            label="Mode"
            value={action.mode}
          />
          <Field
            label="Required team ID"
            value={action.require_team_id}
          />
          <Field
            label="Require notarization"
            value={<BooleanValue value={action.require_notarization} />}
          />
        </>
      );
    case "native_application":
      return (
        <>
          <Field
            label="Application ID"
            value={action.application_id}
          />
          <Field
            label="Native operation"
            value={action.operation}
          />
          <Field
            label="Working directory"
            value={action.working_directory}
          />
          <Field
            label="Input path"
            value={<OptionalValue value={action.input_path} />}
          />
          <Field
            label="Output path"
            value={<OptionalValue value={action.output_path} />}
          />
          <Field
            label="Script path / SHA-256"
            value={
              action.script
                ? `${action.script.path} / ${action.script.sha256}`
                : "None"
            }
          />
          <Field
            label="Configuration hashes"
            value={
              action.configuration.length ? (
                <ul className="space-y-1">
                  {action.configuration.map((item) => (
                    <li key={`${item.path}:${item.sha256}`}>
                      {item.path} / {item.sha256}
                    </li>
                  ))}
                </ul>
              ) : (
                "None"
              )
            }
          />
        </>
      );
  }
}

function plainActionSummary(plan: HostOperationPlan): string {
  const action = plan.action;
  switch (action.category) {
    case "host_inspection": {
      const subject = action.application_id ?? action.target_path ?? "the Mac";
      return `Read ${action.query.replaceAll("_", " ")} information for ${subject}. This request declares no Mac changes.`;
    }
    case "https_download":
      return `Download one verified file to ${action.destination}.`;
    case "homebrew":
      return `${action.operation === "install" ? "Install" : "Uninstall"} the Homebrew ${action.package_kind} ${action.package}.`;
    case "application_install":
      return `${action.mode === "install" ? "Install" : "Stage"} ${action.application_id} at ${action.destination}.`;
    case "native_application":
      return `Run ${action.operation.replaceAll("_", " ")} in ${action.application_id}.`;
  }
}

function PlanDetails({
  plan,
  digest,
}: {
  plan: HostOperationPlan;
  digest: string | null;
}) {
  return (
    <dl className="rounded-lg border px-3">
      <Field
        label="Action category"
        value={plan.action.category}
      />
      <ActionFields plan={plan} />
      <Field
        label="Expected mutations"
        value={
          plan.expected_mutations.length ? (
            <ul className="space-y-2">
              {plan.expected_mutations.map((mutation, index) => (
                <li key={`${mutation.path}:${index}`}>
                  {mutation.operation}: {mutation.path} — {mutation.detail}
                </li>
              ))}
            </ul>
          ) : (
            "None (no declared mutation)"
          )
        }
      />
      <Field
        label="Privilege"
        value={plan.privilege}
      />
      <Field
        label="Timeout"
        value={`${plan.timeout_seconds} seconds`}
      />
      <Field
        label="Bounded output"
        value={`${plan.output_limit_bytes.toLocaleString()} bytes`}
      />
      <Field
        label="Rollback strategy"
        value={plan.rollback.strategy}
      />
      <Field
        label="Rollback removes only request-created paths"
        value={
          <BooleanValue
            value={plan.rollback.removes_only_request_created_paths}
          />
        }
      />
      <Field
        label="Rollback may require human inspection"
        value={
          <BooleanValue value={plan.rollback.may_require_human_inspection} />
        }
      />
      <Field
        label="Approval expires"
        value={`${plan.expiry_seconds} seconds after executor acceptance`}
      />
      <Field
        label="Deterministic plan digest"
        value={
          digest ??
          "Assigned and displayed by the Mac executor after review starts"
        }
      />
    </dl>
  );
}

const statusLanguage: Record<HostLifecycleState, string> = {
  requested: "The immutable request is waiting for native confirmation.",
  confirming:
    "Confirm this exact digest in the native macOS prompt. Do not enter passwords or credentials here.",
  confirmed:
    "Native confirmation is recorded; host execution has not yet completed.",
  running:
    "The approved operation is running on the Mac host within its reviewed timeout.",
  succeeded: "The signed receipt reports verified success on the Mac host.",
  failed:
    "The signed receipt reports failure. No installation or mutation is claimed as successful.",
  rejected:
    "The native macOS confirmation was rejected. The signed receipt records no success claim.",
  expired: "The approval expired. A new immutable request is required.",
  cancelled:
    "The host operation was cancelled. Known effects are reported only by the signed receipt.",
  partial:
    "The operation left a partial mutation. Inspect the signed receipt and complete any stated manual recovery step.",
  uncertain:
    "The final Mac-host state or rollback is uncertain. Human inspection is required before claiming success.",
};

type ApprovalFailure = {
  detail: string;
  nextStep: string;
  retryAllowed: boolean;
};

class ExecutorHttpError extends Error {
  constructor(
    readonly status: number,
    detail: string,
  ) {
    super(`Mac executor returned HTTP ${status}${detail ? `: ${detail}` : ""}`);
  }
}

function failureGuidance(error: unknown): ApprovalFailure {
  const detail =
    error instanceof Error ? error.message : "Unknown executor error";
  const normalized = detail.toLowerCase();
  const useAnotherRoute =
    "Reject this Mac request. Coder will be told to continue through an allowed autonomous tool, including the Docker broker for Docker work, or report one specific blocker.";

  if (
    normalized.includes("not allowlisted") ||
    normalized.includes("policy denied") ||
    normalized.includes("not permitted")
  ) {
    return {
      detail,
      nextStep: `Repeating approval will not change this policy decision. ${useAnotherRoute}`,
      retryAllowed: false,
    };
  }
  if (
    normalized.includes("not pending") ||
    normalized.includes("bound to another interrupt")
  ) {
    return {
      detail,
      nextStep: `This approval is stale and must not be retried. ${useAnotherRoute}`,
      retryAllowed: false,
    };
  }
  if (
    normalized.includes("signed receipt") ||
    normalized.includes("receipt unavailable") ||
    normalized.includes("digest changed") ||
    normalized.includes("malformed")
  ) {
    return {
      detail,
      nextStep: `The result could not be verified safely. ${useAnotherRoute}`,
      retryAllowed: false,
    };
  }
  if (
    normalized.includes("in progress") ||
    normalized.includes("operation is active") ||
    normalized.includes("rate limit") ||
    normalized.includes("timeout") ||
    normalized.includes("timed out") ||
    normalized.includes("failed to fetch") ||
    normalized.includes("polling ended") ||
    (error instanceof ExecutorHttpError && error.status >= 500)
  ) {
    return {
      detail,
      nextStep:
        "This may be temporary. Wait for the current Mac operation or connection to settle, then choose Try approval again. The same reviewed request will be used.",
      retryAllowed: true,
    };
  }
  return {
    detail,
    nextStep: useAnotherRoute,
    retryAllowed: false,
  };
}

async function executorJson(url: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(url, {
    ...init,
    signal: AbortSignal.timeout(executorRequestTimeoutMs),
  });
  if (!response.ok) {
    const rawBody = (await response.text()).trim().slice(0, 1_024);
    let detail = rawBody;
    try {
      const parsed: unknown = JSON.parse(rawBody);
      if (
        parsed &&
        typeof parsed === "object" &&
        "detail" in parsed &&
        typeof parsed.detail === "string"
      ) {
        detail = parsed.detail;
      }
    } catch {
      detail = rawBody;
    }
    throw new ExecutorHttpError(
      response.status,
      detail.replaceAll(/\s+/g, " ").slice(0, 512),
    );
  }
  return response.json();
}

function endpoint(path: string): string {
  const url = new URL(confirmationUrl);
  url.pathname = path;
  url.search = "";
  url.hash = "";
  return url.toString();
}

export function MalformedMacHostInterrupt() {
  return (
    <section
      className="border-destructive/50 bg-destructive/5 rounded-lg border p-4"
      role="alert"
    >
      <h2 className="font-semibold">Mac host operation blocked</h2>
      <p className="text-muted-foreground mt-2 text-sm">
        This request cannot be reviewed safely because it is malformed or mixed
        with another action. Nothing was sent to the Mac executor. Next step:
        start a new thread with the same task so Coder can create one valid
        request or choose an autonomous route.
      </p>
    </section>
  );
}

export function MacosHostOperationCard({
  interrupt,
}: {
  interrupt: Interrupt<HITLRequest>;
}) {
  const stream = useStreamContext();
  const [threadId] = useQueryState("threadId");
  const lock = useRef(false);
  const [busy, setBusy] = useState(false);
  const [digest, setDigest] = useState<string | null>(null);
  const [state, setState] = useState<HostLifecycleState | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [manualStep, setManualStep] = useState<string | null>(null);
  const [retryAllowed, setRetryAllowed] = useState(true);
  const [coderApprovalState, setCoderApprovalState] =
    useState<CoderApprovalState>("awaiting_decision");

  const actionRequest = interrupt.value?.action_requests[0];
  const plan = normalizeHostOperationPlan(actionRequest?.args);
  if (!plan) return <MalformedMacHostInterrupt />;
  const requestDescription =
    typeof actionRequest?.description === "string" &&
    actionRequest.description.trim()
      ? actionRequest.description.trim()
      : "Coder requested an operation that cannot run inside its Linux container.";
  const correlationReady =
    typeof threadId === "string" &&
    threadId.length > 0 &&
    typeof interrupt.id === "string" &&
    interrupt.id.length > 0;

  const resume = async (
    decision: { type: "approve" } | { type: "reject"; message: string },
  ) => {
    await stream.submit(null, {
      command: { resume: { decisions: [decision] } },
      multitaskStrategy: "reject",
    });
  };

  const reject = async () => {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setCoderApprovalState("resuming");
    setMessage(
      "Sending your rejection to Coder. No new Mac operation will start.",
    );
    try {
      await resume({
        type: "reject",
        message:
          "The human rejected this Mac-host operation. Do not retry the same Mac tool call. Continue through an allowed autonomous tool, using request_docker_compose_operation for Docker work. If no allowed route can complete the task, report one specific blocker and the simplest next step. Treat any earlier Mac attempt as unverified.",
      });
      setCoderApprovalState("finished");
      setMessage(
        "Rejected. Coder received instructions not to retry this Mac request and to continue through an allowed autonomous route. This rejection makes no claim about any earlier Mac attempt.",
      );
    } catch (error) {
      const detail =
        error instanceof Error ? error.message : "Unknown LangGraph error";
      setCoderApprovalState("blocked");
      setMessage(
        `The rejection did not reach Coder: ${detail}. No new Mac operation was started. Next step: try Reject again; if it still fails, refresh this thread to restore its saved interrupt.`,
      );
    } finally {
      lock.current = false;
      setBusy(false);
    }
  };

  const reviewAndApprove = async () => {
    if (lock.current || !correlationReady || !retryAllowed) return;
    lock.current = true;
    setBusy(true);
    setCoderApprovalState("waiting_for_mac");
    const maximumWaitSeconds = plan.expiry_seconds + plan.timeout_seconds + 30;
    setMessage(
      `Opening native macOS confirmation. Use Reject in the native prompt to stop. This card will wait for at most ${maximumWaitSeconds.toLocaleString()} seconds before reporting a blocker.`,
    );
    try {
      const initialStatus = await executorJson(confirmationUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: threadId,
          interrupt_id: interrupt.id,
          plan,
        }),
      });
      if (!isHostStatusResponse(initialStatus))
        throw new Error("Malformed executor status response");
      let statusValue: HostStatusResponse = initialStatus;
      const expectedDigest = statusValue.plan_digest;
      setDigest(expectedDigest);
      setState(statusValue.state);
      const maxPollAttempts = Math.ceil(
        ((plan.expiry_seconds + plan.timeout_seconds + 30) * 1_000) /
          pollDelayMs,
      );

      for (let attempt = 0; attempt < maxPollAttempts; attempt += 1) {
        if (
          isTerminalHostState(statusValue.state) &&
          statusValue.receipt_available
        ) {
          const receiptValue = await executorJson(
            endpoint(`/v1/receipts/${expectedDigest}`),
          );
          if (
            !isMatchingSignedReceipt(receiptValue, expectedDigest) ||
            receiptValue.receipt.terminal_status !== statusValue.state
          ) {
            throw new Error(
              "Signed receipt does not match the reviewed plan and terminal status",
            );
          }
          setManualStep(receiptValue.receipt.remaining_human_step);
          setCoderApprovalState("resuming");
          setMessage(
            `${statusLanguage[statusValue.state]} Resuming Coding with the matching signed terminal receipt so it can report the truth.`,
          );
          await resume({ type: "approve" });
          setCoderApprovalState("finished");
          setMessage(
            `${statusLanguage[statusValue.state]} Coder received the verified receipt, and this card no longer blocks the task. Approval alone is not a success claim.${receiptValue.receipt.message ? ` ${receiptValue.receipt.message}` : ""}`,
          );
          return;
        }
        await new Promise((resolve) => window.setTimeout(resolve, pollDelayMs));
        const nextValue = await executorJson(
          endpoint(`/v1/status/${expectedDigest}`),
        );
        if (
          !isHostStatusResponse(nextValue) ||
          nextValue.plan_digest !== expectedDigest
        ) {
          throw new Error("Executor status digest changed or was malformed");
        }
        statusValue = nextValue;
        setState(statusValue.state);
        setMessage(statusLanguage[statusValue.state]);
      }
      throw new Error(
        "Bounded receipt polling ended before a matching signed terminal receipt was available",
      );
    } catch (error) {
      const failure = failureGuidance(error);
      setRetryAllowed(failure.retryAllowed);
      setCoderApprovalState("blocked");
      setMessage(
        `Approval did not complete: ${failure.detail}. Coder remains paused, and no Mac outcome is being claimed. Next step: ${failure.nextStep}`,
      );
    } finally {
      lock.current = false;
      setBusy(false);
    }
  };

  return (
    <section
      className="flex flex-col gap-4"
      aria-label="Mac host operation approval"
    >
      <header className="rounded-lg border border-amber-500/50 bg-amber-500/10 p-4">
        <p className="text-xs font-semibold tracking-wider text-amber-800 uppercase dark:text-amber-200">
          Physical Mac host — separate explicit approval
        </p>
        <h2 className="mt-1 text-lg font-semibold">Mac approval needed</h2>
        <p className="mt-3 text-sm font-medium">Requested action</p>
        <p className="text-muted-foreground mt-1 text-sm">
          {plainActionSummary(plan)}
        </p>
        <p className="mt-3 text-sm font-medium">Why approval is needed</p>
        <p className="text-muted-foreground mt-1 text-sm">
          {requestDescription} This reaches the physical Mac rather than Coder's
          Linux container. Approval grants one attempt and is not proof of
          success.
        </p>
        <p className="mt-3 text-sm font-medium">If you reject</p>
        <p className="text-muted-foreground mt-1 text-sm">
          The Mac action will not start from this decision. Coder will be told
          not to retry it and to continue through an allowed autonomous tool or
          report one specific blocker.
        </p>
      </header>

      <details className="rounded-lg border p-3">
        <summary className="cursor-pointer text-sm font-medium">
          Technical plan details
        </summary>
        <div className="mt-3">
          <PlanDetails
            plan={plan}
            digest={digest}
          />
        </div>
      </details>

      <div
        className="bg-muted/50 rounded-lg border p-3"
        aria-atomic="true"
        aria-live="polite"
        role="status"
      >
        <p className="font-medium">Coder status</p>
        <p className="mt-1 text-sm">
          {coderStatusLanguage[coderApprovalState]}
        </p>
        {state && (
          <p className="text-muted-foreground mt-2 text-sm">
            Mac executor status: {state}
          </p>
        )}
        {message && (
          <p className="text-muted-foreground mt-1 text-sm">{message}</p>
        )}
        {manualStep && (
          <p className="mt-2 text-sm font-medium">
            Required manual Mac step: {manualStep}. Complete it yourself; this
            UI will not automate or capture authorization, passwords, Touch ID,
            Gatekeeper, license acceptance, or GUI consent.
          </p>
        )}
      </div>

      {!correlationReady && (
        <p
          className="text-destructive text-sm"
          role="alert"
        >
          Approval cannot start because this saved request is missing its thread
          or interrupt identity. Next step: reject it so Coder can create a
          valid request or continue another way.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          variant="brand"
          onClick={reviewAndApprove}
          disabled={
            busy ||
            !correlationReady ||
            !retryAllowed ||
            coderApprovalState === "finished"
          }
        >
          {busy
            ? "Confirmation in progress…"
            : coderApprovalState === "blocked" && retryAllowed
              ? "Try approval again"
              : retryAllowed
                ? "Review on Mac and approve"
                : "Mac approval unavailable"}
        </Button>
        <Button
          variant="destructive"
          onClick={reject}
          disabled={busy || coderApprovalState === "finished"}
        >
          Reject Mac action and return to Coder
        </Button>
      </div>
      <p className="text-muted-foreground text-xs">
        Failure, cancellation, expiry, partial change, or uncertain rollback is
        not success. Coder receives only a verified receipt or your explicit
        rejection.
      </p>
    </section>
  );
}
