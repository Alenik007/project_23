import json
import urllib.request
from pathlib import Path

MODEL = "llama3:latest"
API = "http://localhost:11434/api/chat"
MAX_NEW_TOKENS = 160
TEMPERATURE = 0.1
TOP_P = 0.9


def read_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_prompt(item: dict) -> str:
    return (
        "You are a strict JSON generator. Return only JSON.\n\n"
        f"Instruction: {item['instruction']}\n"
        f"Input: {item['input']}\n"
        "Return JSON with keys: task_type, label, confidence, evidence."
    )


def call_ollama(prompt: str) -> str:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "num_predict": MAX_NEW_TOKENS,
        },
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    return out["message"]["content"].strip()


def parse_json(text: str):
    try:
        return json.loads(text), True
    except Exception:
        return None, False


def main():
    root = Path(".")
    rows = read_jsonl(root / "data" / "test.jsonl")

    results = []
    for idx, ex in enumerate(rows, 1):
        expected = json.loads(ex["output"])
        raw = call_ollama(build_prompt(ex))
        obj, valid = parse_json(raw)

        exact = int(obj == expected) if obj is not None else 0
        keys = ["task_type", "label", "confidence", "evidence"]
        field_acc = (
            0.0
            if obj is None
            else sum(1 for k in keys if obj.get(k) == expected.get(k)) / len(keys)
        )

        results.append(
            {
                "valid": 1 if valid else 0,
                "exact": exact,
                "field": field_acc,
                "raw": raw,
                "obj": obj,
                "expected": expected,
                "input": ex["input"],
            }
        )
        print(f"[{idx}/{len(rows)}] valid={valid} exact={exact} field={field_acc:.2f}")

    n = len(results)
    metrics = {
        "exact_match": sum(r["exact"] for r in results) / n,
        "field_level_accuracy": sum(r["field"] for r in results) / n,
        "json_validity": sum(r["valid"] for r in results) / n,
    }
    print("METRICS", json.dumps(metrics, ensure_ascii=False))

    sample_good = [r for r in results if r["field"] >= 0.5][:5]
    sample_errors = [r for r in results if r["exact"] == 0][:5]

    print("SAMPLE_GOOD", len(sample_good))
    for r in sample_good:
        print(
            json.dumps(
                {
                    "input": r["input"],
                    "expected": r["expected"],
                    "output": r["obj"],
                },
                ensure_ascii=False,
            )
        )

    print("SAMPLE_ERRORS", len(sample_errors))
    for r in sample_errors:
        print(
            json.dumps(
                {
                    "input": r["input"],
                    "expected": r["expected"],
                    "raw": r["raw"][:300],
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
