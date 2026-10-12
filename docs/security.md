<figure class="shot" markdown>
![An approval card for running a command, with Deny and Approve buttons](media/screens/en/approval-command.png)
</figure>

```mermaid
flowchart TB
  A["The AI wants to change something"] --> B["✋ Card with exactly what will happen"]
  B --> C{"Your click?"}
  C -- Approve --> D["Done"]
  C -- "Deny · Esc · nothing" --> E["Not done"]
```

--8<-- "SECURITY.md"
