# Confirmation Helper

This AppKit executable is a display-and-decision boundary only. It reads one fixed,
server-produced JSON document from stdin, rejects missing or extra top-level fields,
and displays the plan digest, server request ID/timestamps, actual LangGraph thread
and interrupt IDs, complete immutable plan, and policy-derived execution details. It
writes only:

```json
{"decision":"approve|reject","plan_digest":"..."}
```

It never executes an operation, reads credentials, accepts command arguments, stores
approval, or accepts a client-authored executable/argv. Build on macOS with
`swift build -c release`. Production configuration must resolve and pin the resulting
absolute helper path; clients cannot select it.
