import { Checkpoint, Message } from "@langchain/langgraph-sdk";
import { useEffect, useState, memo } from "react";
import { getContentString } from "../utils";
import { cn } from "@/lib/utils";
import { Textarea } from "@/components/ui/textarea";
import { BranchSwitcher, CommandBar } from "./shared";
import { MultimodalPreview } from "@/components/thread/MultimodalPreview";
import { isBase64ContentBlock } from "@/lib/multimodal-utils";

function EditableContent({
  value,
  setValue,
  onSubmit,
}: {
  value: string;
  setValue: React.Dispatch<React.SetStateAction<string>>;
  onSubmit: () => void;
}) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <Textarea
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={handleKeyDown}
      className="focus-visible:ring-0"
    />
  );
}

function HumanMessageImpl({
  message,
  isLoading,
  parentCheckpoint,
  firstSeenValues,
  branch,
  branchOptions,
  onSelectBranch,
  onSubmitEdit,
}: {
  message: Message;
  isLoading: boolean;
  parentCheckpoint: Checkpoint | null | undefined;
  firstSeenValues: Record<string, unknown> | undefined;
  branch: string | undefined;
  branchOptions: string[] | undefined;
  onSelectBranch: (branch: string) => void;
  onSubmitEdit: (
    message: Message,
    checkpoint: Checkpoint | null | undefined,
    values: Record<string, unknown> | undefined,
  ) => void;
}) {
  useEffect(() => {
    if (!message.id) return;
    const target = window as typeof window & {
      __messageRenders?: Record<string, number>;
    };
    if (target.__messageRenders) {
      target.__messageRenders[message.id] =
        (target.__messageRenders[message.id] ?? 0) + 1;
    }
  });
  const [isEditing, setIsEditing] = useState(false);
  const [value, setValue] = useState("");
  const contentString = getContentString(message.content);

  const handleSubmitEdit = () => {
    setIsEditing(false);

    const newMessage: Message = { type: "human", content: value };
    onSubmitEdit(newMessage, parentCheckpoint, firstSeenValues);
  };

  return (
    <div
      data-message-id={message.id}
      className={cn(
        "group ml-auto flex items-center gap-2",
        isEditing && "w-full max-w-xl",
      )}
    >
      <div className={cn("flex flex-col gap-2", isEditing && "w-full")}>
        {isEditing ? (
          <EditableContent
            value={value}
            setValue={setValue}
            onSubmit={handleSubmitEdit}
          />
        ) : (
          <div className="flex flex-col gap-2">
            {/* Render images and files if no text */}
            {Array.isArray(message.content) && message.content.length > 0 && (
              <div className="flex flex-wrap items-end justify-end gap-2">
                {message.content.reduce<React.ReactNode[]>(
                  (acc, block, idx) => {
                    if (isBase64ContentBlock(block)) {
                      acc.push(
                        <MultimodalPreview
                          key={idx}
                          block={block}
                          size="md"
                        />,
                      );
                    }
                    return acc;
                  },
                  [],
                )}
              </div>
            )}
            {/* Render text if present, otherwise fallback to file/image name */}
            {contentString ? (
              <p className="bg-muted ml-auto w-fit rounded-3xl px-4 py-2 text-right whitespace-pre-wrap">
                {contentString}
              </p>
            ) : null}
          </div>
        )}

        <div
          className={cn(
            "ml-auto flex items-center gap-2 transition-opacity",
            "opacity-0 group-focus-within:opacity-100 group-hover:opacity-100",
            isEditing && "opacity-100",
          )}
        >
          <BranchSwitcher
            branch={branch}
            branchOptions={branchOptions}
            onSelect={onSelectBranch}
            isLoading={isLoading}
          />
          <CommandBar
            isLoading={isLoading}
            content={contentString}
            isEditing={isEditing}
            setIsEditing={(c) => {
              if (c) {
                setValue(contentString);
              }
              setIsEditing(c);
            }}
            handleSubmitEdit={handleSubmitEdit}
            isHumanMessage={true}
          />
        </div>
      </div>
    </div>
  );
}

export const HumanMessage = memo(HumanMessageImpl);
