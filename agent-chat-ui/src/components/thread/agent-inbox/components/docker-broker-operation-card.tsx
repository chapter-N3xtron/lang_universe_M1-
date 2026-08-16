import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Interrupt } from "@langchain/langgraph-sdk";
import { useQueryState } from "nuqs";
import { Button } from "@/components/ui/button";
import { useStreamContext } from "@/providers/Stream";
import { HITLRequest } from "../types";
import {
  DockerBrokerOperationState,
  DockerBrokerStatus,
  DockerComposeOperationPlan,
  isDockerBrokerResult,
  isDockerBrokerStatus,
  isTerminalDockerBrokerState,
  normalizeDockerComposeOperationPlan,
} from "@/lib/docker-broker-operation";

const confirmationUrl =
  process.env.NEXT_PUBLIC_DOCKER_BROKER_URL ??
  "http://127.0.0.1:8766/v1/coder/confirmations";
const pollDelayMs = 500;
const maxPollAttempts = 2_400;
const requestTimeoutMs = 10_000;

function endpoint(path: string): string {
  const url = new URL(confirmationUrl);
  url.pathname = path;
  url.search = "";
  url.hash = "";
  return url.toString();
}

async function brokerJson(url: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(url, {
    ...init,
    signal: AbortSignal.timeout(requestTimeoutMs),
  });
  if (!response.ok) {
    throw new Error(`Docker broker returned HTTP ${response.status}`);
  }
  return response.json();
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid gap-1 border-b py-2 last:border-b-0 sm:grid-cols-[11rem_1fr]">
      <dt className="text-muted-foreground text-sm font-medium">{label}</dt>
      <dd className="min-w-0 font-mono text-sm break-words">{value}</dd>
    </div>
  );
}

function ListValue({ values }: { values: string[] }) {
  return values.length ? (
    <ul className="space-y-1">
      {values.map((value, index) => (
        <li key={`${value}:${index}`}>{value}</li>
      ))}
    </ul>
  ) : (
    <>All declared services / none specified</>
  );
}

function PlanDetails({ plan }: { plan: DockerComposeOperationPlan }) {
  return (
    <dl className="rounded-lg border px-3">
      <Field
        label="Request ID"
        value={plan.request_id}
      />
      <Field
        label="Project directory"
        value={plan.project_directory}
      />
      <Field
        label="Compose file"
        value={plan.compose_files[0]}
      />
      <Field
        label="Operation"
        value={plan.operation}
      />
      <Field
        label="Services"
        value={<ListValue values={plan.services} />}
      />
      <Field
        label="Profiles"
        value={
          plan.profiles.length ? <ListValue values={plan.profiles} /> : "None"
        }
      />
    </dl>
  );
}

export function MalformedDockerBrokerInterrupt() {
  return (
    <section
      className="border-destructive/50 bg-destructive/5 rounded-lg border p-4"
      role="alert"
    >
      <h2 className="font-semibold">Docker Compose operation blocked</h2>
      <p className="text-muted-foreground mt-2 text-sm">
        This request must be the sole Docker broker action with one matching
        approve/reject review configuration and an exact immutable Compose plan.
        Nothing was sent to the broker or resumed in LangGraph.
      </p>
    </section>
  );
}

export function DockerBrokerOperationCard({
  interrupt,
}: {
  interrupt: Interrupt<HITLRequest>;
}) {
  const stream = useStreamContext();
  const [threadId] = useQueryState("threadId");
  const lock = useRef(false);
  const [busy, setBusy] = useState(false);
  const [digest, setDigest] = useState<string | null>(null);
  const [state, setState] = useState<DockerBrokerOperationState | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const plan = useMemo(
    () =>
      normalizeDockerComposeOperationPlan(
        interrupt.value?.action_requests[0]?.args,
      ),
    [interrupt.value],
  );
  const autonomous = stream.values.execution_mode === "autonomous";
  const correlationReady =
    typeof threadId === "string" &&
    threadId.length > 0 &&
    typeof interrupt.id === "string" &&
    interrupt.id.length > 0;

  const resume = useCallback(
    async (decision: { type: "approve" } | { type: "reject" }) => {
      await stream.submit(
        {},
        {
          command: { resume: { decisions: [decision] } },
          multitaskStrategy: "reject",
        },
      );
    },
    [stream],
  );

  const reject = useCallback(async () => {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setMessage("Rejecting without contacting the Docker broker…");
    try {
      await resume({ type: "reject" });
      setMessage("Rejected. No broker request was made.");
    } catch {
      setMessage(
        "The reject resume could not be confirmed. No broker request was made.",
      );
    } finally {
      setBusy(false);
    }
  }, [resume]);

  const reviewAndApprove = useCallback(async () => {
    if (lock.current || !correlationReady || !plan) return;
    lock.current = true;
    setBusy(true);
    setMessage("Requesting native Docker confirmation…");
    try {
      const initialValue = await brokerJson(confirmationUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: threadId,
          interrupt_id: interrupt.id,
          plan,
        }),
      });
      if (!isDockerBrokerStatus(initialValue)) {
        throw new Error("Malformed broker status response");
      }

      let status: DockerBrokerStatus = initialValue;
      const expectedDigest = status.operation_digest;
      const expectedPlanDigest = status.plan_digest;
      setDigest(expectedDigest);
      setState(status.state);

      for (let attempt = 0; attempt < maxPollAttempts; attempt += 1) {
        if (
          isTerminalDockerBrokerState(status.state) &&
          status.result_available
        ) {
          const resultValue = await brokerJson(
            endpoint(`/v1/coder/results/${expectedDigest}`),
          );
          if (
            !isDockerBrokerResult(resultValue) ||
            resultValue.operation_digest !== expectedDigest ||
            resultValue.plan_digest !== expectedPlanDigest ||
            resultValue.state !== status.state
          ) {
            throw new Error(
              "Terminal result does not match the reviewed operation",
            );
          }

          setMessage(
            `Matching terminal result received (${resultValue.state}). Resuming the tool with ordinary approval so it can report the broker result truthfully.`,
          );
          await resume({ type: "approve" });
          setMessage(
            `Tool resumed after the matching ${resultValue.state} result. Approval is not a success claim.`,
          );
          return;
        }

        await new Promise((resolve) => window.setTimeout(resolve, pollDelayMs));
        const nextValue = await brokerJson(
          endpoint(`/v1/coder/status/${expectedDigest}`),
        );
        if (
          !isDockerBrokerStatus(nextValue) ||
          nextValue.operation_digest !== expectedDigest ||
          nextValue.plan_digest !== expectedPlanDigest
        ) {
          throw new Error(
            "Broker status does not match the reviewed operation",
          );
        }
        status = nextValue;
        setState(status.state);
        setMessage(`Docker broker status: ${status.state}.`);
      }
      throw new Error(
        "Polling ended before a matching terminal result was available",
      );
    } catch (error) {
      const detail =
        error instanceof Error ? error.message : "Unknown broker error";
      setMessage(
        `Blocked without LangGraph approval: ${detail}. No matching terminal result was available.`,
      );
    } finally {
      setBusy(false);
    }
  }, [correlationReady, interrupt.id, plan, resume, threadId]);

  useEffect(() => {
    if (autonomous && correlationReady && plan && !lock.current) {
      void reviewAndApprove();
    }
  }, [autonomous, correlationReady, plan, reviewAndApprove]);

  if (!plan) return <MalformedDockerBrokerInterrupt />;

  return (
    <section
      className="flex flex-col gap-4"
      aria-label="Docker broker operation approval"
    >
      <header className="rounded-lg border border-amber-500/50 bg-amber-500/10 p-4">
        <p className="text-xs font-semibold tracking-wider text-amber-800 uppercase dark:text-amber-200">
          Host Docker broker — verified Compose authority
        </p>
        <h2 className="mt-1 text-lg font-semibold">
          Review immutable Compose request
        </h2>
        <p className="text-muted-foreground mt-2 text-sm">
          Native confirmation occurs once per active scoped lease. Autonomous
          mode submits the exact request automatically; approval mode waits for
          manual review.
        </p>
      </header>

      <PlanDetails plan={plan} />

      {(digest || state || message) && (
        <div
          className="bg-muted/50 rounded-lg border p-3"
          aria-live="polite"
        >
          {digest && (
            <p className="font-mono text-sm break-all">
              Operation digest: {digest}
            </p>
          )}
          {state && <p className="mt-1 font-medium">Broker status: {state}</p>}
          {message && (
            <p className="text-muted-foreground mt-1 text-sm">{message}</p>
          )}
        </div>
      )}

      {!correlationReady && (
        <p
          className="text-destructive text-sm"
          role="alert"
        >
          Approval is blocked because the query thread ID or SDK interrupt ID is
          unavailable.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          variant="brand"
          className={autonomous ? "hidden" : undefined}
          onClick={reviewAndApprove}
          disabled={busy || !correlationReady}
        >
          {busy
            ? "Confirmation in progress…"
            : "Confirm with broker and approve"}
        </Button>
        <Button
          variant="destructive"
          onClick={reject}
          disabled={busy}
        >
          Reject without broker call
        </Button>
      </div>
      <p className="text-muted-foreground text-xs">
        The UI never requests or retains broker client secrets or lease tokens.
        A succeeded, failed, or rejected state resumes the tool only after a
        matching terminal result is fetched.
      </p>
    </section>
  );
}
