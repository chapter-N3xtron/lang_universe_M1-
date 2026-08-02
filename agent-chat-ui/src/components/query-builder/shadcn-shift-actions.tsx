import type { ShiftActionsProps } from "react-querybuilder";
import { Button } from "@/components/ui/button";

export function ShadcnShiftActions({
  shiftUp,
  shiftDown,
  shiftUpDisabled,
  shiftDownDisabled,
  disabled,
  className,
  labels,
  titles,
  testID,
}: ShiftActionsProps) {
  return (
    <span
      data-testid={testID}
      className={className}
    >
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={disabled || shiftUpDisabled}
        onClick={shiftUp}
        title={titles?.shiftUp}
      >
        {labels?.shiftUp}
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={disabled || shiftDownDisabled}
        onClick={shiftDown}
        title={titles?.shiftDown}
      >
        {labels?.shiftDown}
      </Button>
    </span>
  );
}
