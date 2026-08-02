import type {
  ControlElementsProp,
  FullField,
  QueryBuilderContextProvider,
} from "react-querybuilder";
import { getCompatContextProvider } from "react-querybuilder";
import { ShadcnActionElement } from "./shadcn-action-element";
import { ShadcnNotToggle } from "./shadcn-not-toggle";
import { ShadcnShiftActions } from "./shadcn-shift-actions";
import { ShadcnValueEditor } from "./shadcn-value-editor";
import { ShadcnValueSelector } from "./shadcn-value-selector";

export const shadcnControlElements: ControlElementsProp<FullField, string> = {
  actionElement: ShadcnActionElement,
  notToggle: ShadcnNotToggle,
  shiftActions: ShadcnShiftActions,
  valueEditor: ShadcnValueEditor,
  valueSelector: ShadcnValueSelector,
};

export const QueryBuilderShadcn: QueryBuilderContextProvider =
  getCompatContextProvider({ controlElements: shadcnControlElements });
