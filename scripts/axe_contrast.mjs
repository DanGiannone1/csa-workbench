export function axeColorContrastOptions() {
  return {
    runOnly: { type: "rule", values: ["color-contrast"] },
    resultTypes: ["violations", "incomplete"],
  };
}

function compactGroup(findings = []) {
  return findings.map(({ id, nodes }) => ({
    id,
    nodes: nodes.map((node) => ({
      target: node.target,
      checks: ["any", "all", "none"].flatMap((group) =>
        (node[group] ?? []).map(({ message, data }) => ({ group, message, data }))),
      failureSummary: node.failureSummary,
    })),
  }));
}

export function compactAxeContrastResults(result) {
  return {
    violations: compactGroup(result.violations),
    incomplete: compactGroup(result.incomplete),
  };
}

export function axeColorContrastPasses({ violations, incomplete }) {
  return violations.length === 0 && incomplete.length === 0;
}
