import json
import random
import time
from pathlib import Path

import numpy as np
import torch
import yaml
from datasets import Dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer


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


def prompt_format(row: dict) -> str:
    return (
        "<|im_start|>system\nYou are a strict JSON generator. Return only JSON.\n<|im_end|>\n"
        f"<|im_start|>user\nInstruction: {row['instruction']}\nInput: {row['input']}\n<|im_end|>\n"
        f"<|im_start|>assistant\n{row['output']}<|im_end|>"
    )


def main() -> None:
    seed = int(CONFIG["seed"])
    set_seed(seed)

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for QLoRA training.")

    train_rows = read_jsonl(ROOT / CONFIG["dataset"]["train_path"])
    train_texts = [prompt_format(r) for r in train_rows]
    train_ds = Dataset.from_dict({"text": train_texts})
    print("train samples:", len(train_ds))

    model_name = CONFIG["model_name"]
    revision = CONFIG.get("base_model_revision", "main")
    bnb_config = BitsAndBytesConfig(
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

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        revision=revision,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )

    peft_config = LoraConfig(
        r=CONFIG["lora"]["r"],
        lora_alpha=CONFIG["lora"]["lora_alpha"],
        lora_dropout=CONFIG["lora"]["lora_dropout"],
        target_modules=CONFIG["lora"]["target_modules"],
        bias="none",
        task_type="CAUSAL_LM",
    )

    args = SFTConfig(
        output_dir=CONFIG["training"]["output_dir"],
        learning_rate=float(CONFIG["training"]["learning_rate"]),
        num_train_epochs=CONFIG["training"]["num_train_epochs"],
        per_device_train_batch_size=CONFIG["training"]["batch_size"],
        gradient_accumulation_steps=CONFIG["training"]["gradient_accumulation_steps"],
        warmup_steps=CONFIG["training"]["warmup_steps"],
        logging_steps=CONFIG["training"]["logging_steps"],
        max_seq_length=CONFIG["training"]["max_seq_length"],
        save_strategy=CONFIG["training"]["save_strategy"],
        report_to="none",
        seed=seed,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_ds,
        peft_config=peft_config,
        args=args,
        dataset_text_field="text",
    )

    start = time.time()
    train_result = trainer.train()
    elapsed_min = (time.time() - start) / 60

    out_dir = ROOT / CONFIG["training"]["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))

    print(f"Training completed in {elapsed_min:.2f} minutes")
    print("Final training loss:", train_result.training_loss)
    print("Adapters saved to:", out_dir)


if __name__ == "__main__":
    main()
