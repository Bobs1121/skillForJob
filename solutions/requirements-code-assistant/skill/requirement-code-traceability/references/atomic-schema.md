# Atomic requirement schema

Each Markdown note contains YAML frontmatter and one fenced `requirement-json` object.

Required frontmatter:

```yaml
requirement_id: SYS-FEATURE-001
feature: FEATURE
source_document: SPEC-KEY
source_version: A/1
source_pages: [12]
source_sections: ["4.2.1"]
review_status: reviewed
implementation_status: unknown
verification_status: unverified
```

Recommended JSON:

```json
{
  "requirement_id": "SYS-FEATURE-001",
  "feature": "FEATURE",
  "kind": "activation",
  "preconditions": {},
  "conditions": {},
  "outputs": {},
  "exceptions": [],
  "source": {
    "document": "SPEC-KEY",
    "version": "A/1",
    "pages": [12],
    "sections": ["4.2.1"]
  },
  "code_candidates": [],
  "test_evidence": []
}
```

Use stable IDs. If the source has no ID, assign a namespaced local ID and never silently change it.

