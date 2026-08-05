import { AIMessage, ToolMessage } from "@langchain/langgraph-sdk";
import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp } from "lucide-react";

function isComplexValue(value: any): boolean {
  return Array.isArray(value) || (typeof value === "object" && value !== null);
}

export function ToolCalls({
  toolCalls,
}: {
  toolCalls: AIMessage["tool_calls"];
}) {
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="mx-auto grid max-w-2xl grid-rows-[1fr_auto] gap-1.5">
      {toolCalls.map((tc, idx) => {
        const args = tc.args as Record<string, any>;
        const hasArgs = Object.keys(args).length > 0;
        return (
          <div
            key={idx}
            className="activity-card overflow-hidden rounded-md border"
          >
            <div className="activity-card-header border-b px-3 py-1.5">
              <h3 className="text-sm font-medium">
                {tc.name}
                {tc.id && (
                  <code className="ml-2 rounded bg-black/10 px-1.5 py-0.5 text-xs">
                    {tc.id}
                  </code>
                )}
              </h3>
            </div>
            {hasArgs ? (
              <table className="min-w-full divide-y divide-[var(--activity-card-border)]">
                <tbody className="divide-y divide-[var(--activity-card-border)]">
                  {Object.entries(args).map(([key, value], argIdx) => (
                    <tr key={argIdx}>
                      <td className="px-3 py-1.5 text-xs font-medium whitespace-nowrap">
                        {key}
                      </td>
                      <td className="activity-card-muted px-3 py-1.5 text-xs">
                        {isComplexValue(value) ? (
                          <code className="rounded bg-black/10 px-1.5 py-0.5 font-mono text-xs break-all">
                            {JSON.stringify(value, null, 2)}
                          </code>
                        ) : (
                          String(value)
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <code className="block px-3 py-1.5 text-xs">{"{}"}</code>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function ToolResult({ message }: { message: ToolMessage }) {
  const [isExpanded, setIsExpanded] = useState(false);

  const [parsedContent, isJsonContent] = useMemo(() => {
    try {
      if (typeof message.content === "string") {
        const parsed = JSON.parse(message.content);
        return [parsed, isComplexValue(parsed)] as const;
      }
    } catch {
      // Content is not JSON, use as is
    }
    return [message.content, false] as const;
  }, [message.content]);

  const contentStr = isJsonContent
    ? JSON.stringify(parsedContent, null, 2)
    : String(message.content);
  const contentLines = contentStr.split("\n");
  const shouldTruncate = contentLines.length > 4 || contentStr.length > 500;
  const displayedContent =
    shouldTruncate && !isExpanded
      ? contentStr.length > 500
        ? contentStr.slice(0, 500) + "..."
        : contentLines.slice(0, 4).join("\n") + "\n..."
      : contentStr;

  return (
    <div className="mx-auto grid max-w-2xl grid-rows-[1fr_auto] gap-1.5">
      <div className="activity-card overflow-hidden rounded-md border">
        <div className="activity-card-header border-b px-3 py-1.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            {message.name ? (
              <h3 className="text-sm font-medium">
                Tool Result:{" "}
                <code className="rounded bg-black/10 px-1.5 py-0.5 text-xs">
                  {message.name}
                </code>
              </h3>
            ) : (
              <h3 className="text-sm font-medium">Tool Result</h3>
            )}
            {message.tool_call_id && (
              <code className="ml-2 rounded bg-black/10 px-1.5 py-0.5 text-xs">
                {message.tool_call_id}
              </code>
            )}
          </div>
        </div>
        <motion.div
          className="min-w-full"
          initial={false}
          animate={{ height: "auto" }}
          transition={{ duration: 0.3 }}
        >
          <div className="p-2.5">
            <AnimatePresence
              mode="wait"
              initial={false}
            >
              <motion.div
                key={isExpanded ? "expanded" : "collapsed"}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.2 }}
              >
                {isJsonContent ? (
                  <table className="min-w-full divide-y divide-[var(--activity-card-border)]">
                    <tbody className="divide-y divide-[var(--activity-card-border)]">
                      {(Array.isArray(parsedContent)
                        ? isExpanded
                          ? parsedContent
                          : parsedContent.slice(0, 5)
                        : Object.entries(parsedContent)
                      ).map((item, argIdx) => {
                        const [key, value] = Array.isArray(parsedContent)
                          ? [argIdx, item]
                          : [item[0], item[1]];
                        return (
                          <tr key={argIdx}>
                            <td className="px-3 py-1.5 text-xs font-medium whitespace-nowrap">
                              {key}
                            </td>
                            <td className="activity-card-muted px-3 py-1.5 text-xs">
                              {isComplexValue(value) ? (
                                <code className="rounded bg-black/10 px-1.5 py-0.5 font-mono text-xs break-all">
                                  {JSON.stringify(value, null, 2)}
                                </code>
                              ) : (
                                String(value)
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                ) : (
                  <code className="block text-xs">{displayedContent}</code>
                )}
              </motion.div>
            </AnimatePresence>
          </div>
          {((shouldTruncate && !isJsonContent) ||
            (isJsonContent &&
              Array.isArray(parsedContent) &&
              parsedContent.length > 5)) && (
            <motion.button
              onClick={() => setIsExpanded(!isExpanded)}
              className="activity-card-muted flex w-full cursor-pointer items-center justify-center border-t border-[var(--activity-card-border)] py-1.5 transition-colors hover:bg-black/10"
              initial={{ scale: 1 }}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              {isExpanded ? <ChevronUp /> : <ChevronDown />}
            </motion.button>
          )}
        </motion.div>
      </div>
    </div>
  );
}
