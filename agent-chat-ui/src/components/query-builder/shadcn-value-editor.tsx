import { useId } from "react";
import type { ValueEditorProps } from "react-querybuilder";
import {
  getFirstOption,
  parseNumber,
  useValueEditor,
} from "react-querybuilder";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

interface ShadcnValueEditorProps extends ValueEditorProps {
  extraProps?: Record<string, unknown>;
}

export function ShadcnValueEditor(
  allProps: ShadcnValueEditorProps,
): React.JSX.Element | null {
  const {
    fieldData,
    operator,
    value,
    handleOnChange,
    title,
    className,
    type,
    values = [],
    listsAsArrays,
    separator,
    valueSource: _valueSource,
    disabled,
    testID,
    selectorComponent: SelectorComponent = allProps.schema.controls
      .valueSelector,
    validation: _validation,
    extraProps,
    inputType,
    parseNumbers: _parseNumbers,
    skipHook: _skipHook,
    ...propsForValueSelector
  } = allProps;
  const {
    valueAsArray,
    multiValueHandler,
    valueListItemClassName,
    inputTypeCoerced,
    bigIntValueHandler,
    parseNumberMethod,
  } = useValueEditor(allProps);

  if (operator === "null" || operator === "notNull") return null;
  const placeholder = fieldData?.placeholder ?? "";
  if (
    (operator === "between" || operator === "notBetween") &&
    (type === "select" || type === "text")
  ) {
    const editors = ["from", "to"].map((key, index) =>
      type === "text" ? (
        <Input
          key={key}
          type={inputTypeCoerced}
          placeholder={placeholder}
          value={valueAsArray[index] ?? ""}
          className={valueListItemClassName}
          disabled={disabled}
          onChange={(event) => multiValueHandler(event.target.value, index)}
          {...extraProps}
        />
      ) : (
        <SelectorComponent
          key={key}
          {...propsForValueSelector}
          className={valueListItemClassName}
          handleOnChange={(nextValue) => multiValueHandler(nextValue, index)}
          disabled={disabled}
          value={valueAsArray[index] ?? getFirstOption(values)}
          options={values}
          listsAsArrays={listsAsArrays}
        />
      ),
    );
    return (
      <span
        data-testid={testID}
        className={className}
        title={title}
      >
        {editors[0]}
        {separator}
        {editors[1]}
      </span>
    );
  }

  if (type === "select" || type === "multiselect") {
    return (
      <SelectorComponent
        {...propsForValueSelector}
        schema={allProps.schema}
        testID={testID}
        className={className}
        title={title}
        handleOnChange={handleOnChange}
        disabled={disabled}
        value={value}
        options={values}
        multiple={type === "multiselect"}
        listsAsArrays={listsAsArrays}
      />
    );
  }
  if (type === "textarea") {
    return (
      <Textarea
        data-testid={testID}
        className={className}
        value={value}
        title={title}
        placeholder={placeholder}
        disabled={disabled}
        onChange={(event) => handleOnChange(event.target.value)}
        {...extraProps}
      />
    );
  }
  if (type === "switch") {
    return (
      <Switch
        data-testid={testID}
        className={className}
        title={title}
        checked={Boolean(value)}
        disabled={disabled}
        onCheckedChange={handleOnChange}
        {...extraProps}
      />
    );
  }
  if (type === "checkbox") {
    return (
      <Checkbox
        data-testid={testID}
        className={className}
        title={title}
        checked={Boolean(value)}
        disabled={disabled}
        onCheckedChange={handleOnChange}
        {...extraProps}
      />
    );
  }
  if (type === "radio") {
    return (
      <RadioGroup
        data-testid={testID}
        className={className}
        title={title}
        value={value}
        onValueChange={handleOnChange}
        {...extraProps}
      >
        {values.map((choice) => (
          <RadioItem
            key={choice.name}
            value={choice.name}
            label={choice.label}
            disabled={disabled}
          />
        ))}
      </RadioGroup>
    );
  }
  return (
    <Input
      data-testid={testID}
      type={inputTypeCoerced}
      placeholder={placeholder}
      value={value ?? ""}
      title={title}
      className={className}
      disabled={disabled}
      onChange={(event) =>
        inputType === "bigint"
          ? bigIntValueHandler(event.target.value)
          : handleOnChange(
              parseNumber(event.target.value, {
                parseNumbers: parseNumberMethod,
              }),
            )
      }
      {...extraProps}
    />
  );
}

function RadioItem({
  value,
  label,
  disabled,
}: {
  value: string;
  label: string;
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <span className="flex items-center gap-2">
      <RadioGroupItem
        id={id}
        value={value}
        disabled={disabled}
      />
      <Label htmlFor={id}>{label}</Label>
    </span>
  );
}
