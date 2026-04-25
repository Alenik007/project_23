import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


ROOT = Path(__file__).resolve().parent
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


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
        "<|im_start|>system\nYou are a strict JSON generator. Return only JSON.\n<|im_end|>\n"
        f"<|im_start|>user\nInstruction: {item['instruction']}\nInput: {item['input']}\n<|im_end|>\n"
        "<|im_start|>assistant\n"
    )


def parse_json(text: str):
    # Handle extra wrappers/code fences and keep first JSON object.
    stripped = text.strip()
    if "```" in stripped:
        stripped = stripped.replace("```json", "```").replace("```JSON", "```")
        parts = [p.strip() for p in stripped.split("```") if p.strip()]
        for part in parts:
            if part.startswith("{") and part.endswith("}"):
                stripped = part
                break
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        stripped = stripped[start : end + 1]
    try:
        return json.loads(stripped), True
    except Exception:
        return None, False


def generate(model, tokenizer, item: dict, gen_cfg: dict) -> str:
    prompt = build_prompt(item)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, **gen_cfg)
    gen_tokens = out[0][inputs["input_ids"].shape[1] :]
    return tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()


def main() -> None:
    set_seed(int(CONFIG["seed"]))
    model_name = CONFIG["model_name"]
    revision = CONFIG.get("base_model_revision", "main")
    adapter_path = ROOT / CONFIG["training"]["output_dir"]
    if not adapter_path.exists():
        raise FileNotFoundError(f"Adapter path not found: {adapter_path}")

    use_bnb_4bit = torch.cuda.is_available()
    bnb = None
    if use_bnb_4bit:
        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )

    tokenizer = AutoTokenizer.from_pretrained(
        model_name, revision=revision, trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        model_name,
        revision=revision,
        quantization_config=bnb if use_bnb_4bit else None,
        device_map="auto" if use_bnb_4bit else "cpu",
        trust_remote_code=True,
    )
    tuned_model = AutoModelForCausalLM.from_pretrained(
        model_name,
        revision=revision,
        quantization_config=bnb if use_bnb_4bit else None,
        device_map="auto" if use_bnb_4bit else "cpu",
        trust_remote_code=True,
    )
    tuned_model = PeftModel.from_pretrained(tuned_model, adapter_path)

    gen_cfg = {
        "max_new_tokens": CONFIG["inference"]["max_new_tokens"],
        "temperature": CONFIG["inference"]["temperature"],
        "top_p": CONFIG["inference"]["top_p"],
        "do_sample": CONFIG["inference"]["do_sample"],
    }

    test_rows = read_jsonl(ROOT / CONFIG["dataset"]["test_path"])

    rows = []
    for idx, ex in enumerate(test_rows, 1):
        expected = json.loads(ex["output"])
        b_raw = generate(base_model, tokenizer, ex, gen_cfg)
        t_raw = generate(tuned_model, tokenizer, ex, gen_cfg)

        b_obj, b_valid = parse_json(b_raw)
        t_obj, t_valid = parse_json(t_raw)

        def exact(obj):
            return int(obj == expected) if obj is not None else 0

        def field_acc(obj):
            if obj is None:
                return 0.0
            keys = ["task_type", "label", "confidence", "evidence"]
            return float(sum(1 for k in keys if obj.get(k) == expected.get(k)) / len(keys))

        rows.append(
            {
                "input": ex["input"],
                "expected": expected,
                "base_raw": b_raw,
                "tuned_raw": t_raw,
                "base_output": b_obj,
                "tuned_output": t_obj,
                "base_valid_json": b_valid,
                "tuned_valid_json": t_valid,
                "base_exact": exact(b_obj),
                "tuned_exact": exact(t_obj),
                "base_field_acc": field_acc(b_obj),
                "tuned_field_acc": field_acc(t_obj),
            }
        )
        print(f"[{idx}/{len(test_rows)}] done")

    df = pd.DataFrame(rows)
    metrics = pd.DataFrame(
        [
            {
                "metric": "exact_match",
                "base": float(df["base_exact"].mean()),
                "fine_tuned": float(df["tuned_exact"].mean()),
            },
            {
                "metric": "field_level_accuracy",
                "base": float(df["base_field_acc"].mean()),
                "fine_tuned": float(df["tuned_field_acc"].mean()),
            },
            {
                "metric": "json_validity",
                "base": float(df["base_valid_json"].mean()),
                "fine_tuned": float(df["tuned_valid_json"].mean()),
            },
        ]
    )

    improved = df[
        (df["tuned_exact"] > df["base_exact"]) | (df["tuned_field_acc"] > df["base_field_acc"])
    ].head(5).copy()
    errors = df[(df["tuned_exact"] == 0)].head(5).copy()

    def make_comment(row):
        if row["tuned_exact"] > row["base_exact"]:
            return "fine-tuned reached exact match"
        if row["tuned_field_acc"] > row["base_field_acc"]:
            return "fine-tuned improved field-level match"
        if row["tuned_valid_json"] and not row["base_valid_json"]:
            return "fine-tuned improved JSON validity"
        return "no improvement"

    improved["comment"] = improved.apply(make_comment, axis=1)
    errors["comment"] = "fine-tuned output does not exactly match expected JSON"

    out_dir = ROOT / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(out_dir / "metrics.csv", index=False)
    improved[
        ["input", "expected", "base_output", "tuned_output", "comment"]
    ].to_json(out_dir / "improved_cases.json", orient="records", force_ascii=False, indent=2)
    errors[
        ["input", "expected", "base_output", "tuned_output", "comment"]
    ].to_json(out_dir / "error_cases.json", orient="records", force_ascii=False, indent=2)

    print("\nMetrics:")
    print(metrics.to_string(index=False))
    print("\nSaved artifacts to:", out_dir)


if __name__ == "__main__":
    main()
