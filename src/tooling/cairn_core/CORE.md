# Cairn process-description core

Version **1.0.0**. Language specification **v0.15**. Plan conformance **1.7**.

This directory is the process description: the vocabulary a Cairn document is
checked against, and the Python that parses and validates it. Render, the
interpreter, the web composer, and the rest of the Deborah package are not
part of this core.

The core version moves when this contract moves. It does not follow the
Deborah package version.

## What a consumer takes

Copy this directory. Import `cairn_core`. Do not install the `deborah`
package. Nothing in this directory imports `deborah`.

```python
from cairn_core import DEFAULT_METAMODEL, parse_document, validate_document

document = parse_document(text)
errors = validate_document(document)
```

## Extending and overriding

`DEFAULT_METAMODEL` is the v0.15 contract.

`extend` adds constructs, annotation keywords, statuses, cognition values,
aliases, and checks. A later annotation rule for the same keyword replaces
the earlier check. Adding a construct puts it in the parser and in plan
validation.

`override` replaces a field. Replacing `annotation_rules` or
`cognition_values` drops what you do not pass back. `dropped_constructs`
removes a default construct from parsing and from plan validation when you
`extend` with that set.

```python
from cairn_core import AnnotationRule, DEFAULT_METAMODEL, parse_document, validate_document

def links(text, lineno, model):
    if text.strip() != "ok":
        return [f"line {lineno}: LINKS must be ok"]
    return []

model = DEFAULT_METAMODEL.extend(
    extension_constructs=frozenset({"AUDIT"}),
    annotation_surfaces=("LINKS",),
    annotation_rules=(AnnotationRule("LINKS", links),),
)
document = parse_document(source, model=model)
errors = validate_document(document, model=model)
```

`require_step_names=True` on an overridden model demands a name on every
step. `validate_document(..., require_step_names=True)` does the same for
one call.

Plan dicts use `validate_plan(plan, profile="full", model=model)`. Profiles
remain `full`, `core`, and `strict` unless the model adds one.
