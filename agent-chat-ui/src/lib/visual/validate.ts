import Ajv, { type ErrorObject, type ValidateFunction } from "ajv";
import schema from "./jasper-response.schema.json";
import type { JasperResponse } from "./jasper-response.generated";

const ajv = new Ajv({ allErrors: true, strict: true });
const validateResponse = ajv.compile(
  schema,
) as ValidateFunction<JasperResponse>;

function semanticError(message: string): ErrorObject {
  return {
    keyword: "visualGraph",
    instancePath: "/artifacts",
    schemaPath: "#/visualGraph",
    params: {},
    message,
  };
}

export type VisualValidationResult =
  | { valid: true; value: JasperResponse }
  | { valid: false; errors: ErrorObject[] };

export function validateJasperResponse(
  candidate: unknown,
): VisualValidationResult {
  if (validateResponse(candidate)) {
    for (const artifact of candidate.artifacts ?? []) {
      const sourceIds = new Set(
        artifact.payload.sources.map((source) => source.id),
      );
      if (sourceIds.size !== artifact.payload.sources.length) {
        return {
          valid: false,
          errors: [semanticError("concept-map source IDs must be unique")],
        };
      }
      const ids = new Set(artifact.payload.nodes.map((node) => node.id));
      if (ids.size !== artifact.payload.nodes.length) {
        return {
          valid: false,
          errors: [semanticError("concept-map node IDs must be unique")],
        };
      }
      const narrationIds = new Set(artifact.payload.narration_order);
      if (
        narrationIds.size !== artifact.payload.narration_order.length ||
        narrationIds.size !== ids.size ||
        [...ids].some((id) => !narrationIds.has(id))
      ) {
        return {
          valid: false,
          errors: [
            semanticError(
              "concept-map narration order must contain every node exactly once",
            ),
          ],
        };
      }
      for (const node of artifact.payload.nodes) {
        if (node.evidence_refs.some((ref) => !sourceIds.has(ref))) {
          return {
            valid: false,
            errors: [
              semanticError("concept-map nodes must cite known sources"),
            ],
          };
        }
      }
      for (const edge of artifact.payload.edges ?? []) {
        if (!ids.has(edge.source) || !ids.has(edge.target)) {
          return {
            valid: false,
            errors: [
              semanticError("concept-map edge endpoints must reference nodes"),
            ],
          };
        }
        if (edge.evidence_refs.some((ref) => !sourceIds.has(ref))) {
          return {
            valid: false,
            errors: [
              semanticError("concept-map edges must cite known sources"),
            ],
          };
        }
      }
      if (ids.size > 1) {
        const adjacency = new Map(
          [...ids].map((id) => [id, new Set<string>()]),
        );
        for (const edge of artifact.payload.edges ?? []) {
          adjacency.get(edge.source)?.add(edge.target);
          adjacency.get(edge.target)?.add(edge.source);
        }
        const firstId = ids.values().next().value as string;
        const visited = new Set<string>();
        const pending = [firstId];
        while (pending.length) {
          const current = pending.pop()!;
          if (visited.has(current)) continue;
          visited.add(current);
          pending.push(
            ...[...(adjacency.get(current) ?? [])].filter(
              (neighbor) => !visited.has(neighbor),
            ),
          );
        }
        if (visited.size !== ids.size) {
          return {
            valid: false,
            errors: [
              semanticError("concept map must be a single connected graph"),
            ],
          };
        }
      }
      if (
        new TextEncoder().encode(JSON.stringify(artifact)).length >
        256 * 1024
      ) {
        return {
          valid: false,
          errors: [semanticError("visual artifact exceeds 256 KiB")],
        };
      }
    }
    return { valid: true, value: candidate };
  }
  return { valid: false, errors: [...(validateResponse.errors ?? [])] };
}
