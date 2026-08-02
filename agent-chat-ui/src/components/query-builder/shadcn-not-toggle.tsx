import { useId } from "react";
import type { NotToggleProps } from "react-querybuilder";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

export function ShadcnNotToggle({
  className,
  handleOnChange,
  label,
  checked,
  title,
  disabled,
  testID,
  path: _path,
  level: _level,
  context: _context,
  validation: _validation,
  schema: _schema,
  ruleGroup: _ruleGroup,
  ...otherProps
}: NotToggleProps) {
  const id = useId();
  return (
    <span className="flex items-center gap-2">
      <Switch
        {...otherProps}
        id={id}
        data-testid={testID}
        className={className}
        title={title}
        checked={Boolean(checked)}
        disabled={disabled}
        onCheckedChange={handleOnChange}
      />
      <Label htmlFor={id}>{label}</Label>
    </span>
  );
}
