export type TodoStatus = "pending" | "in_progress" | "completed";

export interface Todo {
  id: string;
  content: string;
  status: TodoStatus;
  agent: string | null;
  completed_by_model: string | null;
  completed_at: string | null;
  notes: string;
}

export interface TodoSection {
  id: string;
  title: string;
  created_at: string;
  planned_by_model: string;
  planned_by_agent: string;
  todos: Todo[];
}

export interface TodoFile {
  version: number;
  updated_at: string;
  updated_by: string;
  sections: TodoSection[];
}
