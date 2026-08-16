"use client";

type TaskStatus = "pending" | "in_progress" | "completed";

type ProgressTask = {
  task: string;
  status: TaskStatus;
  note: string;
};

type ProgressReport = {
  elapsedMinutes: number;
  tasks: ProgressTask[];
  blockers: string[];
};

const STATUS_LABELS: Record<TaskStatus, string> = {
  pending: "Pending",
  in_progress: "In progress",
  completed: "Completed",
};

function readProgressReport(value: unknown): ProgressReport | null {
  if (!value || typeof value !== "object") return null;
  const props = value as Record<string, unknown>;
  if (
    typeof props.elapsed_minutes !== "number" ||
    !Number.isFinite(props.elapsed_minutes) ||
    props.elapsed_minutes < 0 ||
    !Array.isArray(props.tasks) ||
    !Array.isArray(props.blockers)
  ) {
    return null;
  }

  const tasks: ProgressTask[] = [];
  for (const item of props.tasks.slice(0, 100)) {
    if (!item || typeof item !== "object") return null;
    const task = item as Record<string, unknown>;
    if (
      typeof task.task !== "string" ||
      typeof task.note !== "string" ||
      !["pending", "in_progress", "completed"].includes(String(task.status))
    ) {
      return null;
    }
    tasks.push({
      task: task.task,
      note: task.note,
      status: task.status as TaskStatus,
    });
  }

  const blockers = props.blockers
    .slice(0, 20)
    .filter((blocker): blocker is string => typeof blocker === "string");
  return { elapsedMinutes: props.elapsed_minutes, tasks, blockers };
}

export function CoderProgressReport({ props }: { props: unknown }) {
  const report = readProgressReport(props);
  if (!report) return null;

  return (
    <section
      aria-live="polite"
      aria-label="Coder progress report"
      className="mx-auto w-full max-w-3xl rounded-lg border border-blue-200 bg-blue-50/70 px-4 py-3 text-sm text-slate-800 shadow-xs dark:border-blue-900 dark:bg-blue-950/30 dark:text-slate-200"
      role="status"
    >
      <h2 className="font-semibold">
        Coder progress — {report.elapsedMinutes} minutes
      </h2>
      <ul className="mt-2 space-y-2">
        {report.tasks.map((task, index) => (
          <li key={`${task.task}-${index}`}>
            <span className="font-medium">{STATUS_LABELS[task.status]}:</span>{" "}
            {task.task}
            <p className="text-muted-foreground mt-0.5">Note: {task.note}</p>
          </li>
        ))}
      </ul>
      <div className="mt-3 border-t border-blue-200 pt-2 dark:border-blue-900">
        <span className="font-medium">Blockers:</span>{" "}
        {report.blockers.length > 0
          ? report.blockers.join("; ")
          : "No blocker reported."}
      </div>
      <p className="text-muted-foreground mt-2">
        Coder is continuing with the unfinished tasks.
      </p>
    </section>
  );
}
