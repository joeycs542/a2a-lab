# Lab 7: Team lunch browser demo

## Goal

Follow one question through discovery, delegation, and the return path.
Compare two users with different access rules.
This exercise uses packaged lunch data without a model.
For generated answers, use the [local model setup](../../docs/guides/local-model-integration.md).

## Agents and users

The coordinator has the supervisor role.
It finds permitted specialists and sends the question to each selected specialist.
The specialists return separate answers.
The coordinator puts those answers together for the client.

| Specialist | Task | Permitted users |
| --- | --- | --- |
| Food | Give food options from the lunch notes. | Alice and Bob |
| Place | Give place options from the lunch notes. | Alice and Bob |
| Budget | Give the spending limits from the lunch notes. | Alice only |

Alice is the organizer.
Bob is an attendee.
They are simulated identities in one browser client.
The directory filters entries by user.
Each specialist independently applies its access rules.
The demo makes no purchases, reservations, or invitations.

## Start the demo

With Docker Desktop running, use a new named project:

```sh
docker compose -p a2a-lunch -f compose.yaml -f compose.discovery.yaml -f compose.web.yaml -f compose.lunch.yaml up --build -d --wait
```

Open http://127.0.0.1:8080/.
Use that exact address.
The gateway does checks of Host and Origin.
Only the browser relay has a published loopback port.
Agent ports remain private.

## Follow the request

1. Select Alice.
2. Ask `Suggest food for our team lunch.`
3. Find the coordinator's directory query in the execution view.
4. Examine the live Agent Card checks and Food selection.
5. Find the child task ID that confirms question receipt.
6. Read the returned Food answer.
7. Ask `Plan a team lunch: food, place, and budget.`
8. Follow the three specialist answers back through the coordinator.
9. Read the final result above the map.
10. Expand **Specialist work** to examine each agent's output.

A send event alone does not prove receipt.
A returned child task ID provides receipt evidence.
A compatible card describes an agent, but does not prove successful execution.

In fixture mode, the processing summary describes topic matching and reference notes.
In model mode, each selected specialist also makes a local inference request.
Available model text does not guarantee a complete record of internal reasoning.

## Compare access

1. Select Bob.
2. Ask `Plan a team lunch: food, place, and budget.`
3. Read the partial plan.
4. Compare it with Alice's result.

Bob receives Food and Place answers only.
The access rules exclude Budget.
The difference comes from application policy, not from a different model.
A completed coordinator task can contain a partial plan.
The task state describes completion of the coordinator's work.
It does not imply success for every specialist.

## Replay the events

After execution ends, select **Replay**.
Replay starts paused.
Use **Next step** to advance.
Use **Previous step** to return to an earlier event.
Use **Resume** for automatic playback.

Replay shows recorded event order at a teaching pace.
It does not reproduce the original timing or make new requests.
Later evidence remains hidden until the corresponding step.
The coordinator's return path and final result appear at delivery.

The lower disclosures show each observed specialist's task receipt, processing summary, and returned answer.
The execution evidence includes raw events and task IDs.
A page refresh can recover the latest task while its session and server records remain available.
A server restart or session expiry loses this recovery path.
Changing the user clears the current display.

## Unavailable specialist

The lunch scenario keeps the internal service ID `runbook` for Food.
To make Food unavailable, stop that service:

```sh
docker compose -p a2a-lunch -f compose.yaml -f compose.discovery.yaml -f compose.web.yaml -f compose.lunch.yaml stop runbook
```

Ask `Plan a team lunch: food, place, and budget.`
Expect a partial plan with Food unavailable.
The coordinator must not invent a Food answer or citation.

Restore the service after the exercise:

```sh
docker compose -p a2a-lunch -f compose.yaml -f compose.discovery.yaml -f compose.web.yaml -f compose.lunch.yaml start runbook
```

Use [Lab 6](../06-agent-discovery/README.md) for detailed selection, ambiguity, cancellation, and failure exercises.
That lab explicitly uses the original engineering scenario.

## Access controls and limits

The browser receives no bearer credentials.
The gateway applies Host, Origin, CSRF, and session ownership checks.
Task and trace APIs also apply verified owner scope.
The user selector is a teaching simulation rather than a production login system.

Answers render as Markdown with raw HTML and images disabled.
Links use HTTP, HTTPS, or mailto schemes only.
Questions, processing summaries, and execution events remain text-only.
The browser polls for results rather than using A2A streaming.

The coordinator sends work to at most three distinct specialists.
It applies a shared deadline and per-specialist limits.
Each accepted finding has at most 2,000 characters and one reference.
Missing, failed, invalid, or unknown results produce a partial plan.
A timeout does not prove that remote work stopped.
Model generation can continue after the application cancels its HTTP wait.

Read the [security guide](../../docs/security.md) for implemented controls and deployment limits.

## Verification and shutdown

For the locked verification, run:

```sh
docker build --target verify -t a2a-lab:verify .
```

For browser logic checks, run:

```sh
node scripts/web-ui-smoke.cjs
```

The integration suite includes lunch answers, Budget denial, and real A2A requests.
It also tests malformed cards, ownership, partial results, and cancellation.
These tests do not prove model answer quality.

To stop this project and keep its volumes, run:

```sh
docker compose -p a2a-lunch -f compose.yaml -f compose.discovery.yaml -f compose.web.yaml -f compose.lunch.yaml down
```

Teaching credentials expire after one hour.
For a new session, use a new, unused project name.
Use the same project name and files for every command within one session.
