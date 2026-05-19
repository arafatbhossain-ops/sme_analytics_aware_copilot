# Focused Prototype Design Document

## Prototype name

Privacy-Safe SME Data Co-Pilot

## Specific problem

Small businesses often have operational data in spreadsheets, software exports, or transactional systems, but they may not have dedicated data teams to convert that data into reliable, privacy-safe business reports.

## Proposed solution

The prototype demonstrates a workflow that:

1. Ingests business data.
2. Lets the user choose a privacy scan mode such as PII Baseline, HIPAA-aware, GDPR-aware, PCI-aware, or Strict.
3. Detects and excludes sensitive fields before AI use.
4. Validates data quality.
5. Converts raw operational data into analytics-ready fact/dimension-style structures.
6. Computes business metrics locally.
7. Lets an analyst configure a repeatable reporting pipeline and schedule.
8. Generates an automated dashboard.
9. Sends only aggregated metrics to an AI report layer.
10. Produces a plain-English weekly operations report.

## Why it is different from generic GenAI

The system is not a chat-only interface. It combines secure data engineering, analytics modeling, data validation, and GenAI explanation. The GenAI layer is used after data has been cleaned, validated, aggregated, and stripped of sensitive fields.

## Security note

This prototype uses synthetic data by default. Privacy-standard modes are illustrative and are not legal compliance certifications.
