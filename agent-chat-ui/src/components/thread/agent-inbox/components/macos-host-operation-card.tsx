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

async function executorJson(url: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(url, {
    ...init,
    signal: AbortSignal.timeout(executorRequestTimeoutMs),
  });
  if (!response.ok)
    throw new Error(`Mac executor returned HTTP ${response.status}`);
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
        This interrupt is malformed or mixed with another action. A Mac-host
        request must be the sole action, have one matching approve/reject review
        configuration, and contain an exact immutable plan. Nothing was sent to
        the Mac executor or resumed in LangGraph.
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

  const planValue = interrupt.value?.action_requests[0]?.args;
  const plan = normalizeHostOperationPlan(planValue);
  if (!plan) return <MalformedMacHostInterrupt />;
  const correlationReady =
    typeof threadId === "string" &&
    threadId.length > 0 &&
    typeof interrupt.id === "string" &&
    interrupt.id.length > 0;

  const resume = async (decision: { type: "approve" } | { type: "reject" }) => {
    await stream.submit(
      {},
      {
        command: { resume: { decisions: [decision] } },
        multitaskStrategy: "reject",
      },
    );
  };

  const reject = async () => {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setMessage("Rejecting without contacting or executing on the Mac host…");
    try {
      await resume({ type: "reject" });
      setMessage(
        "Rejected. No executor request was made and no Mac-host success is claimed.",
      );
    } catch {
      setMessage(
        "The reject resume could not be confirmed. No executor request was made; refresh the thread before taking another action.",
      );
    } finally {
      setBusy(false);
    }
  };

  const reviewAndApprove = async () => {
    if (lock.current || !correlationReady) return;
    lock.current = true;
    setBusy(true);
    setMessage(
      "Opening native macOS confirmation while the LangGraph interrupt remains pending…",
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
          setMessage(
            `${statusLanguage[statusValue.state]} Resuming Coding with the matching signed terminal receipt so it can report the truth.`,
          );
          await resume({ type: "approve" });
          setMessage(
            `${statusLanguage[statusValue.state]} Coding received the ordinary approve decision for this receipt; approval alone is not a success claim.${receiptValue.receipt.message ? ` ${receiptValue.receipt.message}` : ""}`,
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
      const detail =
        error instanceof Error ? error.message : "Unknown executor error";
      setMessage(
        `Blocked without LangGraph approval: ${detail}. No matching signed terminal receipt was available, so the tool was not resumed. Refresh to inspect durable status; do not assume the Mac changed.`,
      );
    } finally {
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
        <h2 className="mt-1 text-lg font-semibold">
          Review immutable macOS operation
        </h2>
        <p className="text-muted-foreground mt-2 text-sm">
          Ordinary Coding work runs in the <strong>Linux container</strong>{" "}
          against the selected Mac-host repository mount. This card is
          different: it may affect the <strong>physical Mac host</strong>{" "}
          through a separate non-agent executor. Approval grants one attempt
          only and never verifies success by itself.
        </p>
      </header>

      <PlanDetails
        plan={plan}
        digest={digest}
      />

      {(state || message || manualStep) && (
        <div
          className="bg-muted/50 rounded-lg border p-3"
          aria-live="polite"
        >
          {state && <p className="font-medium">Executor status: {state}</p>}
          {message && (
            <p className="text-muted-foreground mt-1 text-sm">{message}</p>
          )}
          {manualStep && (
            <p className="mt-2 text-sm font-medium">
              Required manual Mac step: {manualStep}. Complete it yourself; this
              UI will not automate or capture authorization, passwords, Touch
              ID, Gatekeeper, license acceptance, or GUI consent.
            </p>
          )}
        </div>
      )}

      {!correlationReady && (
        <p
          className="text-destructive text-sm"
          role="alert"
        >
          Approval is blocked because the exact thread ID or interrupt ID is
          unavailable.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          variant="brand"
          onClick={reviewAndApprove}
          disabled={busy || !correlationReady}
        >
          {busy ? "Confirmation in progress…" : "Review on Mac and approve"}
        </Button>
        <Button
          variant="destructive"
          onClick={reject}
          disabled={busy}
        >
          Reject without Mac execution
        </Button>
      </div>
      <p className="text-muted-foreground text-xs">
        Cancellation, expiry, timeout, failure, partial mutation, and uncertain
        rollback are not success. They resume Coding only when the executor
        provides a matching signed terminal receipt, allowing the resumed tool
        to report the exact known state and any manual step.
      </p>
    </section>
  );
}
