# Documentation language and review

The [constitution](../constitution.md#documentation-language) requires ASD-STE100 Simplified Technical English, Issue 9.
Use the [official standard and dictionary](https://www.asd-ste100.org/STE_downloads.html) for the language review.
This guide supports that review. It does not replace the standard.

## Scope

Apply the requirement to all maintained project documentation.
This includes the README, labs, guides, skills, API documentation, comments, docstrings, and runtime instructions.
Keep private discussions outside Git.
Do not copy private design records into a public guide.

## Project terms

Use these names for the specified project objects.
These are project technical nouns. Use them only within the technical-noun rules of the standard.
Do not use a technical noun as a verb unless the standard permits that verb.

| Term | Meaning in this project |
| --- | --- |
| A2A | The Agent2Agent protocol. |
| Agent Card | The published A2A description of an agent and its capabilities. |
| agent | A service that accepts A2A requests. |
| artifact | An output object in an A2A task. |
| client | The application that sends a request. |
| coordinator | The agent that selects and calls an approved specialist. |
| credential | Data that the server uses to verify a caller. |
| directory | The service that returns approved agent entries. |
| fixture | Packaged synthetic data used for a repeatable exercise. |
| owner | The user whose permission scope applies to a task. |
| prompt | An instruction or input supplied to a model. |
| runtime task guide | Instructions that the application loads for the model. |
| coding skill | Instructions for an agent that maintains the source code. |
| Agent Card skill | A capability advertised in an Agent Card. |
| specialist | An agent with a specific task type, such as food advice. |
| supervisor | The coordinator role that selects specialists and returns their answers. |
| Food | The lunch specialist for food advice. Its internal service ID is `runbook`. |
| Place | The lunch specialist for places. Its internal service ID is `release`. |
| Budget | The lunch specialist for spending limits. Its internal service ID is `security`. |
| task | The A2A work object with an ID and lifecycle state. |
| trace | A record of selected execution events. |

Keep official product names, command names, and wire values exact.
For example, do not change `TASK_STATE_CANCELED` to match a preferred prose term.

## Review procedure

1. Identify procedural text and descriptive text.
2. Check the sentence structure against the standard.
3. Check the word count with the standard's counting rules.
4. Check general vocabulary against the dictionary.
5. Check technical terms against the standard and the table above.
6. Check that each term has one meaning in the document.
7. Check commands and identifiers against the implementation.
8. Check that all links work in a standalone clone.
9. Correct text that fails these checks.

Use automated checks to find possible errors.
Do not use a word-count check as proof of full compliance.
Record unresolved language issues in private review notes.
Do not label text as compliant until the review is complete.
