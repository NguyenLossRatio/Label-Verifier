# Business Requirements

## Business Goal

Build a standalone AI-powered prototype that helps TTB compliance agents verify alcohol label applications faster by comparing label artwork against expected application fields.

## Primary Users

- Compliance agents reviewing alcohol label applications
- Compliance managers responsible for throughput and quality
- IT stakeholders evaluating feasibility for future procurement or workflow integration

## Core Requirements

1. The app must allow users to upload alcohol label images.
2. The app must extract or identify key label information, including:
   - Brand name
   - Class/type designation
   - Alcohol content / ABV
   - Net contents
   - Bottler/producer name and address
   - Country of origin for imports
   - Government health warning statement
3. The app must compare label information against expected application data.
4. The app must flag mismatches between the label and application fields.
5. The app must verify that the government warning statement is present.
6. The government warning statement check must be strict, including exact wording and proper capitalization of `GOVERNMENT WARNING:`.
7. The app should tolerate minor human-readable differences where appropriate, such as capitalization differences in brand names.
8. The app should support batch uploads so agents can process many labels at once.
9. The app should provide results quickly, ideally within about 5 seconds per label.
10. The app must be simple enough for low-tech-comfort users to operate without training.

## User Experience Requirements

- The interface should be clean, obvious, and easy to navigate.
- Agents should not need to hunt for buttons or understand complex workflows.
- Results should be easy to scan.
- The tool should reduce manual verification effort rather than add extra steps.
- Error states should be clear, especially when an image cannot be read.

## Operational Requirements

- The prototype should be standalone and not directly integrated with the existing COLA system.
- The prototype should be suitable for evaluation as a proof of concept.
- The prototype should help demonstrate whether AI-assisted label review could improve future compliance workflows.

## Performance Requirements

- Label processing should return results in approximately 5 seconds or less.
- Batch processing should handle large importer submissions, potentially hundreds of labels.

## Security And Environment Constraints

- Production deployment would need to consider PII, retention policies, and federal compliance.
- For the prototype, sensitive data storage is not required.
- Cloud APIs may be unreliable in the target environment because outbound network access is restricted.
- The solution should avoid unnecessary external dependencies where possible.

## Nice-To-Have Requirements

- The app should handle imperfect label images, such as:
  - Angled photos
  - Poor lighting
  - Glare
  - Non-ideal image quality
- The project should support AI-generated or sourced test labels for validation.

## Explicit Non-Goals / Out Of Scope

- Direct integration with COLA
- Full modernization of the existing .NET COLA system
- Production-grade federal compliance implementation
- Long-term document retention or sensitive data storage

## Success Criteria

- The prototype accurately verifies the most important label fields.
- The prototype is faster than manual review for routine checks.
- The prototype is usable by agents with varying technical comfort.
- The prototype demonstrates clear value for high-volume and repetitive review work.
- The prototype favors a working, reliable core workflow over ambitious incomplete features.
