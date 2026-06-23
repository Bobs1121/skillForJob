# Requirement-to-code comparison rules

Compare independently:

1. Enablement and preconditions.
2. Entry and exit thresholds, including hysteresis.
3. State transitions and priority.
4. Geometry or algorithm conditions.
5. Input signals and validity handling.
6. Output values, encoding, and destinations.
7. Fault, degradation, and suppression behavior.
8. Timing and persistence.
9. Configuration and build variants.
10. Test evidence.

Evidence strength:

- Strong: literal or constant, explicit branch, signal write, test assertion.
- Medium: call path and named configuration strongly imply behavior.
- Weak: comment, similar symbol, another product variant, semantic match.

Only strong evidence can establish `matched` or `mismatch`. Medium evidence is `candidate`; weak evidence is supporting context.

