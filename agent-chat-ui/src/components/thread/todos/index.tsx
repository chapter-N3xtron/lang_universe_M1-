import { useState, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";
import { type TodoSection, type Todo, type TodoStatus } from "@/lib/types/todo";

const STATUS_ICONS: Record<TodoStatus, string> = {
  pending: "○",
  in_progress: "◉",
  completed: "✓",
};

const STATUS_COLORS: Record<TodoStatus, string> = {
  pending: "text-gray-400",
  in_progress: "text-amber-500",
  completed: "text-green-500",
};

function ProgressBar({
  completed,
  total,
}: {
  completed: number;
  total: number;
}) {
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
  return (
    <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
        <div
          className="h-full rounded-full bg-green-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="whitespace-nowrap tabular-nums">
        {completed}/{total} ({pct}%)
      </span>
    </div>
  );
}

function TodoItem({ todo }: { todo: Todo }) {
  const color = STATUS_COLORS[todo.status];
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-md px-2 py-1.5 text-sm",
        todo.status === "in_progress" && "animate-pulse",
      )}
    >
      <span className={cn("mt-0.5 flex-shrink-0", color)}>
        {STATUS_ICONS[todo.status]}
      </span>
      <div className="min-w-0 flex-1">
        <span
          className={cn(
            "text-gray-800 dark:text-gray-200",
            todo.status === "completed" &&
              "text-gray-400 line-through dark:text-gray-500",
          )}
        >
          {todo.content}
        </span>
        <div className="mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5 text-xs text-gray-400 dark:text-gray-500">
          {todo.agent && <span>[{todo.agent}]</span>}
          {todo.completed_by_model && <span>by {todo.completed_by_model}</span>}
        </div>
      </div>
    </div>
  );
}

function TodoSectionCard({ section }: { section: TodoSection }) {
  const total = section.todos.length;
  const completed = section.todos.filter(
    (t) => t.status === "completed",
  ).length;
  return (
    <div className="rounded-lg border bg-white p-3 shadow-xs dark:bg-gray-900">
      <div className="mb-2">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
          {section.title}
        </h3>
        <p className="text-xs text-gray-400 dark:text-gray-500">
          planned by {section.planned_by_model}
        </p>
      </div>
      <ProgressBar
        completed={completed}
        total={total}
      />
      <div className="mt-2 space-y-0.5">
        {section.todos.map((todo) => (
          <TodoItem
            key={todo.id}
            todo={todo}
          />
        ))}
      </div>
    </div>
  );
}

export function TodoList({ todosOpen }: { todosOpen?: boolean }) {
  const [sections, setSections] = useState<TodoSection[]>([]);
  const [error, setError] = useState(false);

  const fetchTodos = useCallback(() => {
    fetch("http://127.0.0.1:8000/api/todos")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: { sections: TodoSection[] }) => {
        setSections(data.sections ?? []);
        setError(false);
      })
      .catch(() => {
        setError(true);
      });
  }, []);

  useEffect(() => {
    if (!todosOpen) return;
    fetchTodos();
    const interval = setInterval(fetchTodos, 3000);
    return () => clearInterval(interval);
  }, [fetchTodos, todosOpen]);

  if (error) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <p className="text-sm text-gray-400 dark:text-gray-500">
          Could not load todos
        </p>
      </div>
    );
  }

  if (sections.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <p className="text-sm text-gray-400 dark:text-gray-500">No todos yet</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex-shrink-0 border-b border-gray-200 px-4 py-3 dark:border-gray-700">
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
          Todo List
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        <div className="space-y-3">
          {sections.map((section) => (
            <TodoSectionCard
              key={section.id}
              section={section}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
