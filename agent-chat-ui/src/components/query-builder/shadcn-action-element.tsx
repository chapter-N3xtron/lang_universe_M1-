import type { ActionProps } from "react-querybuilder";
import { Button } from "@/components/ui/button";

export function ShadcnActionElement({
  className,
  handleOnClick,
  label,
  title,
  disabled,
  disabledTranslation,
  testID,
  rules: _rules,
  ruleOrGroup: _ruleOrGroup,
  path: _path,
  level: _level,
  context: _context,
  validation: _validation,
  schema: _schema,
  ...otherProps
}: ActionProps) {
  return (
    <Button
      {...otherProps}
      data-testid={testID}
      type="button"
      size="sm"
      variant="outline"
      className={className}
      title={
        disabledTranslation && disabled ? disabledTranslation.title : title
      }
      disabled={disabled && !disabledTranslation}
      onClick={(event) => handleOnClick(event)}
    >
      {disabledTranslation && disabled ? disabledTranslation.label : label}
    </Button>
  );
}
