# Build An Adapter In 30 Minutes

This guide shows the smallest useful adapter path.

Simple version: start with a dry-run adapter. Do not call a live API first. Make
the adapter prove its inputs, outputs, ledger events, and evidence. Live
execution can come later.

## The Shape

Every adapter needs four pieces:

1. A contract in `delegation_bot/adapters.py`
2. A dry-run implementation in `delegation_bot/builtin_adapters.py`
3. Tests that validate the contract and adapter result
4. Docs or an example Harnessfile showing how to call it

The no-network example is `sample.echo`. It is intentionally tiny:

- inputs: `message`, `label`
- output: `sample.echo`
- evidence: `echo_hash`
- events: `adapter.sample.echo.prepare`, `sample.echo.planned`

## Step 1: Add A Contract

Add an `AdapterContract` entry:

```python
"sample.echo": AdapterContract(
    id="sample.echo",
    kind="tool",
    description="Plan a no-network echo adapter.",
    risk="low",
    approval_required_for=(),
    inputs=("message", "label"),
    outputs=("sample.echo", "run_ledger"),
    planned_event_types=("adapter.sample.echo.prepare", "sample.echo.planned"),
    required_evidence=("echo_hash",),
)
```

The contract is the promise. Keep it small and specific.

## Step 2: Implement Dry-Run Planning

Subclass `ContractBackedDryRunAdapter`:

```python
class SampleEchoDryRunAdapter(ContractBackedDryRunAdapter):
    def __init__(self) -> None:
        super().__init__(_contract_or_raise("sample.echo"))
```

Return outputs and evidence without network calls:

```python
def build_outputs(self, request, missing_inputs):
    return {
        "sample.echo": {
            "message": request.inputs.get("message"),
            "dry_run": True,
        }
    }

def build_evidence(self, request, missing_inputs):
    return {"echo_hash": self.echo_hash(request)}
```

Then register it:

```python
BUILT_IN_DRY_RUN_ADAPTERS = {
    "sample.echo": SampleEchoDryRunAdapter(),
}
```

## Step 3: Add Tests

At minimum, test:

- the contract exists
- the dry-run adapter returns `planned`
- all required outputs exist
- all required evidence exists
- planned event types appear in the result
- missing required inputs produce `blocked`

Use:

```python
validate_adapter_result(contract, result)
```

If it returns an empty list, the adapter kept its contract.

## Step 4: Add A Harnessfile Example

```yaml
executors:
  - id: sample_echo
    kind: tool
    adapter: sample.echo
    purpose: Demonstrate the adapter SDK without network calls.
    inputs:
      label: contributor-demo
      message: "A no-network adapter can still leave useful ledger evidence."
```

Run:

```bash
python scripts/delegation.py plan examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl
python scripts/delegation.py ledger .delegation/latest.jsonl --adapter sample.echo
python scripts/delegation.py eval examples/ai-harness-control-plane.yaml --ledger .delegation/latest.jsonl
```

## Step 5: Run QA

```bash
python scripts/qa.py
```

Before opening a pull request, make sure:

- the adapter is dry-run first
- no secrets are required
- no network calls happen in tests
- required evidence can be inspected in the ledger
- `required_adapter_evidence` passes

## What Comes Later

Live execution should only come after:

- dry-run planning is useful
- evidence is stable
- policy gates are clear
- approval requirements are declared
- evals can catch missing or bad evidence
