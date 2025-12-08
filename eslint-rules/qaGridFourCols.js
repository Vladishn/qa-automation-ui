// eslint-rules/qaGridFourCols.js
/**
 * Rule: qa-grid-4cols-row must have exactly 4 children (STEP, STATUS, TIMESTAMP, INFO)
 * Applies to JSX elements whose className contains BOTH:
 *   - "qa-grid-4cols"
 *   - "qa-grid-4cols-row"
 */

"use strict";

function classNameLiteralValue(attr) {
  if (!attr || !attr.value) return null;
  if (attr.value.type === "Literal") return attr.value.value;
  if (attr.value.type === "JSXExpressionContainer" &&
      attr.value.expression.type === "Literal") {
    return attr.value.expression.value;
  }
  return null;
}

function hasQaGridFourCols(classAttr) {
  const value = classNameLiteralValue(classAttr);
  if (typeof value !== "string") return false;
  return value.includes("qa-grid-4cols") && value.includes("qa-grid-4cols-row");
}

module.exports = {
  meta: {
    type: "problem",
    docs: {
      description:
        "qa-grid-4cols-row must have exactly 4 child elements (STEP, STATUS, TIMESTAMP, INFO)",
      category: "Best Practices",
    },
    schema: [],
  },

  create(context) {
    return {
      JSXElement(node) {
        const opening = node.openingElement;
        if (!opening || !opening.attributes) return;

        const classAttr = opening.attributes.find(
          (attr) =>
            attr.type === "JSXAttribute" &&
            attr.name &&
            attr.name.name === "className"
        );

        if (!classAttr || !hasQaGridFourCols(classAttr)) return;

        // Count "real" children (ignore whitespace-only text nodes)
        const children = node.children.filter((child) => {
          if (child.type === "JSXText") {
            return child.value.trim().length > 0;
          }
          return true;
        });

        if (children.length !== 4) {
          context.report({
            node,
            message:
              "qa-grid-4cols-row must have exactly 4 child elements (STEP, STATUS, TIMESTAMP, INFO). Found {{count}}.",
            data: {
              count: children.length,
            },
          });
        }
      },
    };
  },
};
